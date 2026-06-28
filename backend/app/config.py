"""
EKOS Application Configuration
Loads environment variables with Pydantic Settings for type safety and validation.
"""

from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # === Application ===
    app_name: str = "EKOS"
    app_version: str = "1.0.0"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # === Groq LLM ===
    groq_api_key: str = Field(default="", description="Groq Cloud API key")
    groq_model_large: str = "llama-3.3-70b-versatile"
    groq_model_small: str = "llama-3.1-8b-instant"
    groq_model_fast: str = "mixtral-8x7b-32768"

    # === Google Embeddings ===
    google_api_key: str = Field(default="", description="Google AI Studio API key")
    embedding_model: str = "models/text-embedding-004"
    embedding_dimension: int = 768

    # === MySQL ===
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "ekos_db"

    # === JWT ===
    jwt_secret_key: str = "your-super-secret-jwt-key-change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # === File Upload ===
    upload_dir: str = "uploads"
    max_file_size_mb: int = 50

    # === RAG ===
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k_retrieval: int = 10
    top_k_rerank: int = 5
    dense_weight: float = 0.6
    sparse_weight: float = 0.4

    # === FAISS ===
    faiss_index_path: str = "vector_store/faiss_index"
    faiss_metadata_path: str = "vector_store/metadata.json"

    # === Knowledge Graph ===
    knowledge_graph_path: str = "knowledge_graph.json"

    # === MLflow ===
    mlflow_tracking_uri: str = "http://localhost:5000"
    mlflow_experiment_name: str = "ekos-evaluation"

    # === Rate Limiting ===
    rate_limit_requests: int = 60
    rate_limit_window_seconds: int = 60

    # === Logging ===
    log_level: str = "INFO"
    log_file: str = "logs/ekos.log"

    @property
    def mysql_url(self) -> str:
        """SQLAlchemy MySQL connection URL."""
        return (
            f"mysql+aiomysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def mysql_sync_url(self) -> str:
        """Synchronous MySQL connection URL for migrations."""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
        )

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def base_dir(self) -> Path:
        """Base directory of the backend application."""
        return Path(__file__).parent.parent

    @property
    def upload_path(self) -> Path:
        """Absolute path to upload directory."""
        path = self.base_dir / self.upload_dir
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def vector_store_dir(self) -> Path:
        """Absolute path to vector store directory."""
        path = self.base_dir / "vector_store"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_dir(self) -> Path:
        """Absolute path to logs directory."""
        path = self.base_dir / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
