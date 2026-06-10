import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import List


def _generate_dev_secret() -> str:
    """Generate a random secret for development only."""
    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    # Environment
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Database — no hardcoded credentials; must be provided via .env or environment
    database_url: str = ""
    database_sync_url: str = ""
    db_pool_size: int = 20
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:latest"

    # Upload
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50
    allowed_extensions: str = "pdf,jpg,jpeg,png,webp"

    # Security — no hardcoded secrets
    secret_key: str = ""
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Google OAuth2 — must be configured via .env
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/auth/callback"

    # Processing
    max_concurrent_ocr: int = 4
    max_concurrent_ai: int = 2
    ocr_timeout_seconds: int = 120
    ocr_page_timeout_seconds: int = 30
    max_pdf_pages: int = 50
    ocr_process_workers: int = 4
    ai_timeout_seconds: int = 120
    ocr_max_dimension: int = 5120
    ocr_retry_confidence_threshold: float = 0.5

    # OpenAI Configuration
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_enabled: bool = False
    openai_max_retries: int = 2
    openai_timeout_seconds: int = 30

    # OpenAI Fallback Thresholds
    openai_fallback_min_ocr_confidence: float = 0.3
    openai_fallback_min_classification_confidence: float = 0.5
    openai_fallback_max_ownership_score: float = 80.0

    # Upload limits
    max_files_per_upload: int = 20

    # Task management concurrency
    max_document_concurrency: int = 4
    max_batch_concurrency: int = 2
    max_notification_concurrency: int = 4
    shutdown_timeout_seconds: int = 30

    # Ollama AI parameters
    ollama_connect_timeout: float = 10.0
    ollama_max_retries: int = 3
    ollama_num_predict: int = 1024
    ollama_num_ctx: int = 8192

    # Notifications
    email_max_retries: int = 3
    stuck_notification_max_age_minutes: int = 30

    # Google API I/O
    google_io_pool_size: int = 4

    # WebSocket
    ws_ticket_ttl_seconds: int = 30

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = True

    # Celery
    celery_enabled: bool = False
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Dashboard
    dashboard_cache_ttl_seconds: int = 30

    # Session cookie
    session_cookie_name: str = "bgv_session"
    session_cookie_secure: bool = True  # HTTPS only; override to False for local dev via .env
    session_cookie_samesite: str = "lax"  # "strict" for highest security; "lax" allows OAuth redirects
    session_cookie_domain: str = ""  # Empty = current domain only

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid:
            raise ValueError(f"log_level must be one of {valid}, got '{v}'")
        return v

    @model_validator(mode="after")
    def _validate_required_settings(self) -> "Settings":
        """Ensure critical settings are configured. In development, use safe defaults."""
        if not self.database_url:
            if self.environment == "development":
                self.database_url = "postgresql+asyncpg://bgv_user:bgv_dev_pass@localhost:5432/bgv_db"
            else:
                raise ValueError("DATABASE_URL must be set in production")

        if not self.database_sync_url:
            if self.environment == "development":
                self.database_sync_url = "postgresql://bgv_user:bgv_dev_pass@localhost:5432/bgv_db"
            else:
                raise ValueError("DATABASE_SYNC_URL must be set in production")

        if not self.secret_key:
            if self.environment == "development":
                self.secret_key = _generate_dev_secret()
            else:
                raise ValueError("SECRET_KEY must be set in production")

        if self.environment != "development":
            if not self.google_client_id or not self.google_client_secret:
                raise ValueError(
                    "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in production"
                )
        return self

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip().lower() for ext in self.allowed_extensions.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    def resolve_file_path(self, stored_path: str) -> Path:
        """Resolve a stored relative path to an absolute filesystem path.

        Handles both new relative paths (correlation_id/filename) and
        legacy absolute paths for backward compatibility.
        """
        p = Path(stored_path)
        if p.is_absolute():
            return p
        upload_path = self.upload_path
        if p.parts and p.parts[0].lower() == upload_path.name.lower():
            return upload_path.parent / p
        return upload_path / p

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
