"""
Centralized configuration for BlackBox Regulatory Guardian.
Loads from environment variables / .env file with sensible defaults.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- LLM Configuration ---
    LLM_PROVIDER: str = "ollama"  # "ollama", "openai", "google"
    LLM_MODEL: str = "llama3"
    LLM_TEMPERATURE: float = 0.0
    LLM_BASE_URL: str = "http://localhost:11434"  # Ollama default
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    # --- Pinecone Vector DB ---
    PINECONE_API_KEY: Optional[str] = None
    PINECONE_INDEX_NAME: str = "regulatory-guardian-policies"
    PINECONE_ENVIRONMENT: Optional[str] = None
    EMBEDDING_PROVIDER: str = "local"  # "local", "openai", "google"
    LOCAL_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # e.g., "all-MiniLM-L6-v2" (384d) or "BAAI/bge-large-en-v1.5" (1024d)

    # --- LRR Monitoring Configuration ---
    LRR_POLL_INTERVAL_HOURS: int = 6
    RBI_RSS_URL: str = "https://www.rbi.org.in/pressreleases_rss.xml"
    RBI_CIRCULAR_URL: str = "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx"
    RBI_NOTIFICATION_URL: str = "https://www.rbi.org.in/Scripts/NotificationUser.aspx"
    LRR_ENABLED: bool = True
    LRR_MAX_RETRIES: int = 3
    LRR_RETRY_DELAY_SECONDS: int = 30

    # --- Guardrails Configuration ---
    GUARDRAILS_STRICT_MODE: bool = True
    GUARDRAILS_LOG_VIOLATIONS: bool = True
    GUARDRAILS_BLOCK_ON_FAILURE: bool = False  # If True, blocks output; else appends warning

    # --- MCP Server Configuration ---
    MCP_SERVER_HOST: str = "localhost"
    MCP_SERVER_PORT: int = 8001
    MCP_SERVER_NAME: str = "RegulatoryGuardianMCP"

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./sql_app.db"

    # --- Model Paths ---
    LEGAL_BERT_PATH: str = "models/legal_bert_cuad"
    LAYOUTLMV3_PATH: str = "models/layoutlmv3_doclaynet"

    # --- Scraping ---
    SCRAPER_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    SCRAPER_TIMEOUT_SECONDS: int = 30

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()
