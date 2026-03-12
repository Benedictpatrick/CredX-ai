"""
Titan-Credit Configuration — Single source of truth for all settings.
"""
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    # --- Project Paths ---
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = PROJECT_ROOT / "data"
    VECTOR_STORE_DIR: Path = DATA_DIR / "vector_store"
    EXPERIENCE_LIBRARY_DIR: Path = DATA_DIR / "experience_library"

    # --- LLM Configuration (Open-Source via Ollama) ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "llama3.1:8b"
    VISION_MODEL: str = "llava:13b"
    EMBEDDING_MODEL: str = "nomic-embed-text"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 4096
    OLLAMA_OPTIONAL_MODE: bool = True
    OLLAMA_PROBE_TIMEOUT_SEC: float = 1.5
    OLLAMA_AVAILABILITY_TTL_SEC: int = 30

    # --- FastAPI ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_TITLE: str = "Titan-Credit Decisioning Engine"
    API_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/titan_credit.db"

    # --- ChromaDB Vector Store ---
    CHROMA_COLLECTION: str = "titan_credit_docs"
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 128

    # --- Fraud Engine ---
    GNN_HIDDEN_DIM: int = 64
    GNN_NUM_LAYERS: int = 3
    CIRCULAR_TRADE_THRESHOLD: float = 0.75
    FRAUD_SCORE_THRESHOLD: float = 0.6

    # --- Research Agent ---
    MAX_SEARCH_RESULTS: int = 10
    NEWS_LOOKBACK_DAYS: int = 365
    ECOURTS_BASE_URL: str = "https://services.ecourts.gov.in"
    MCA_BASE_URL: str = "https://www.mca.gov.in"

    # --- Recommendation Engine ---
    BASE_LENDING_RATE: float = 8.5  # RBI repo rate baseline
    MAX_RISK_PREMIUM: float = 6.0
    MIN_RISK_PREMIUM: float = 0.5
    BULL_BEAR_ROUNDS: int = 5
    CONSENSUS_THRESHOLD: float = 0.15  # Max divergence for consensus

    # --- Guardian Safety ---
    MAX_SEMANTIC_DRIFT_SCORE: float = 0.3
    GUARDRAIL_ENABLED: bool = True

    # --- Streamlit Dashboard ---
    DASHBOARD_PORT: int = 8501

    # --- Databricks (Production) ---
    DATABRICKS_HOST: Optional[str] = None
    DATABRICKS_TOKEN: Optional[str] = None
    UNITY_CATALOG_NAME: str = "titan_credit"
    UNITY_SCHEMA_NAME: str = "credit_engine"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
