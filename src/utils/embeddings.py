"""
Embedding service wrapping ChromaDB for vector storage & retrieval.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from config.settings import settings
from src.utils.llm_client import llm_client


class EmbeddingStore:
    """ChromaDB-backed vector store with Ollama embeddings."""

    def __init__(self, persist_dir: Optional[str] = None):
        self.persist_dir = persist_dir or str(settings.VECTOR_STORE_DIR)
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection = None

    def _get_client(self) -> chromadb.ClientAPI:
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        return self._client

    def get_collection(self, name: str = settings.CHROMA_COLLECTION):
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    async def add_documents(
        self,
        texts: list[str],
        metadatas: list[dict],
        ids: list[str],
        collection_name: str = settings.CHROMA_COLLECTION,
    ):
        collection = self.get_collection(collection_name)
        embeddings = await llm_client.embed_batch(texts)
        collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"Added {len(texts)} documents to collection '{collection_name}'")

    async def query(
        self,
        query_text: str,
        n_results: int = 5,
        collection_name: str = settings.CHROMA_COLLECTION,
        where: Optional[dict] = None,
    ) -> dict:
        collection = self.get_collection(collection_name)
        query_embedding = await llm_client.embed(query_text)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return results

    def delete_collection(self, name: str = settings.CHROMA_COLLECTION):
        client = self._get_client()
        client.delete_collection(name)
        self._collection = None
        logger.info(f"Deleted collection '{name}'")


# Singleton
embedding_store = EmbeddingStore()
