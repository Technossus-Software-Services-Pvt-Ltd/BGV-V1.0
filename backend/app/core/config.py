import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator, model_validator
from typing import List


def _generate_dev_secret() -> str:
    """Generate a random secret for development only."""
    return secrets.token_urlsafe(32)


class Settings(BaseSettings):
    # Environment
    environment: str = "development"
    debug: bool = False
    log_level: str = "WARNING"

    # Database — no hardcoded credentials; must be provided via .env or environment
    database_url: str = ""
    database_sync_url: str = ""

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
    max_concurrent_ocr: int = 2
    max_concurrent_ai: int = 1
    ocr_timeout_seconds: int = 120
    ai_timeout_seconds: int = 120

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
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
