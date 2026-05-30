import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    # Environment
    environment: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://bgv_user:bgv_secure_pass_change_me@localhost:5432/bgv_db"
    database_sync_url: str = "postgresql://bgv_user:bgv_secure_pass_change_me@localhost:5432/bgv_db"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:latest"

    # Upload
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50
    allowed_extensions: str = "pdf,jpg,jpeg,png,webp"

    # Security
    secret_key: str = "change-this-to-a-secure-random-string-in-production"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    # Google OAuth2 (from Google Cloud Console > OAuth 2.0 Client ID)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:3000/auth/callback"

    # Processing
    max_concurrent_ocr: int = 2
    max_concurrent_ai: int = 1
    ocr_timeout_seconds: int = 120
    ai_timeout_seconds: int = 60


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
