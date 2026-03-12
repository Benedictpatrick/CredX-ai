"""
Unified LLM client wrapping Ollama for text + vision inference.
Provides retry logic, structured JSON output, and streaming.
"""
from __future__ import annotations

import json
import base64
import time
from pathlib import Path
from typing import Optional, Any

import httpx
from loguru import logger
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.settings import settings


class LLMClient:
    """Thin async wrapper around the Ollama HTTP API."""

    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.LLM_MODEL,
        vision_model: str = settings.VISION_MODEL,
        temperature: float = settings.LLM_TEMPERATURE,
        max_tokens: int = settings.LLM_MAX_TOKENS,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.vision_model = vision_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client: Optional[httpx.AsyncClient] = None
        self._availability_cache: Optional[bool] = None
        self._availability_checked_at: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(300.0, connect=30.0),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _ensure_service_available(self):
        """Fail fast when Ollama is unavailable so deterministic fallbacks can run."""
        if not settings.OLLAMA_OPTIONAL_MODE:
            return

        now = time.monotonic()
        ttl = max(settings.OLLAMA_AVAILABILITY_TTL_SEC, 1)

        if (
            self._availability_cache is not None
            and (now - self._availability_checked_at) < ttl
        ):
            if not self._availability_cache:
                raise RuntimeError(
                    f"Ollama unavailable at {self.base_url}; using deterministic fallbacks"
                )
            return

        client = await self._get_client()
        try:
            resp = await client.get(
                "/api/tags",
                timeout=httpx.Timeout(
                    settings.OLLAMA_PROBE_TIMEOUT_SEC,
                    connect=settings.OLLAMA_PROBE_TIMEOUT_SEC,
                ),
            )
            resp.raise_for_status()
            self._availability_cache = True
        except Exception as exc:
            self._availability_cache = False
            self._availability_checked_at = now
            logger.warning(
                f"Ollama probe failed at {self.base_url}; deterministic fallbacks will be used: {exc}"
            )
            raise RuntimeError(
                f"Ollama unavailable at {self.base_url}; using deterministic fallbacks"
            ) from exc

        self._availability_checked_at = now

    # ── Text Generation ──────────────────────────────────────
    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
    )
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        await self._ensure_service_available()
        client = await self._get_client()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            },
        }

        resp = await client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    # ── Structured JSON Output ───────────────────────────────
    async def generate_json(
        self,
        prompt: str,
        system_prompt: str = "",
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        system = (system_prompt or "") + (
            "\n\nYou MUST respond with valid JSON only. No markdown, no explanation."
        )
        raw = await self.generate(prompt, system_prompt=system, model=model)
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON, attempting repair: {cleaned[:200]}")
            # Attempt to extract JSON from the response
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(cleaned[start:end])
            raise

    # ── Vision (Multimodal) ──────────────────────────────────
    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
    )
    async def vision_parse(
        self,
        image_path: str | Path,
        prompt: str = "Extract all text and tabular data from this document image. Preserve the structure.",
        system_prompt: str = "",
    ) -> str:
        await self._ensure_service_available()
        client = await self._get_client()
        image_path = Path(image_path)

        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({
            "role": "user",
            "content": prompt,
            "images": [image_b64],
        })

        payload = {
            "model": self.vision_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.05,
                "num_predict": self.max_tokens,
            },
        }

        resp = await client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]

    # ── Vision with JSON output ──────────────────────────────
    async def vision_parse_json(
        self,
        image_path: str | Path,
        prompt: str = "",
        system_prompt: str = "",
    ) -> dict[str, Any]:
        full_prompt = (
            prompt
            + "\n\nRespond ONLY with valid JSON. No markdown, no explanation."
        )
        raw = await self.vision_parse(image_path, full_prompt, system_prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                return json.loads(cleaned[start:end])
            raise

    # ── Embeddings ───────────────────────────────────────────
    @retry(
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
    )
    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        await self._ensure_service_available()
        client = await self._get_client()
        payload = {
            "model": model or settings.EMBEDDING_MODEL,
            "input": text,
        }
        resp = await client.post("/api/embed", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"][0]

    async def embed_batch(
        self, texts: list[str], model: Optional[str] = None
    ) -> list[list[float]]:
        await self._ensure_service_available()
        client = await self._get_client()
        payload = {
            "model": model or settings.EMBEDDING_MODEL,
            "input": texts,
        }
        resp = await client.post("/api/embed", json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"]


# Singleton
llm_client = LLMClient()
