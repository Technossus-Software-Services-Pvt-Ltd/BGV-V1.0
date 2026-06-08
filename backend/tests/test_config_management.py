"""Tests for Phase 6: Configuration Management.

Verifies that:
1. Settings class validates required production fields
2. Development defaults are applied correctly
3. New settings have correct default values
4. Properties compute correctly
5. Services read from settings (not hardcoded)
"""

import pytest
from unittest.mock import patch
from pydantic import ValidationError

from app.core.config import Settings


class TestSettingsDefaults:
    """Verify default values match previous hardcoded behavior."""

    def test_upload_defaults(self):
        s = Settings(environment="development")
        assert s.max_files_per_upload == 20
        assert s.max_upload_size_mb == 50

    def test_task_manager_defaults(self):
        s = Settings(environment="development")
        assert s.max_document_concurrency == 4
        assert s.max_batch_concurrency == 2
        assert s.max_notification_concurrency == 4
        assert s.shutdown_timeout_seconds == 30

    def test_ollama_defaults(self):
        s = Settings(environment="development")
        assert s.ollama_connect_timeout == 10.0
        assert s.ollama_max_retries == 3
        assert s.ollama_num_predict == 1024
        assert s.ollama_num_ctx == 4096

    def test_notification_defaults(self):
        s = Settings(environment="development")
        assert s.email_max_retries == 3
        assert s.stuck_notification_max_age_minutes == 30

    def test_google_io_defaults(self):
        s = Settings(environment="development")
        assert s.google_io_pool_size == 4

    def test_websocket_defaults(self):
        s = Settings(environment="development")
        assert s.ws_ticket_ttl_seconds == 30

    def test_dashboard_defaults(self):
        s = Settings(environment="development")
        assert s.dashboard_cache_ttl_seconds == 30

    def test_processing_defaults(self):
        s = Settings(environment="development", _env_file=None)
        assert s.max_concurrent_ocr == 2
        assert s.max_concurrent_ai == 1
        assert s.ocr_timeout_seconds == 120
        assert s.ai_timeout_seconds == 120


class TestSettingsOverride:
    """Verify settings can be overridden via environment variables."""

    @patch.dict("os.environ", {"MAX_FILES_PER_UPLOAD": "10"})
    def test_upload_limit_override(self):
        s = Settings(environment="development")
        assert s.max_files_per_upload == 10

    @patch.dict("os.environ", {"MAX_DOCUMENT_CONCURRENCY": "8"})
    def test_concurrency_override(self):
        s = Settings(environment="development")
        assert s.max_document_concurrency == 8

    @patch.dict("os.environ", {"OLLAMA_NUM_CTX": "8192"})
    def test_ollama_ctx_override(self):
        s = Settings(environment="development")
        assert s.ollama_num_ctx == 8192

    @patch.dict("os.environ", {"DASHBOARD_CACHE_TTL_SECONDS": "60"})
    def test_dashboard_cache_override(self):
        s = Settings(environment="development")
        assert s.dashboard_cache_ttl_seconds == 60

    @patch.dict("os.environ", {"EMAIL_MAX_RETRIES": "5"})
    def test_email_retries_override(self):
        s = Settings(environment="development")
        assert s.email_max_retries == 5

    @patch.dict("os.environ", {"GOOGLE_IO_POOL_SIZE": "8"})
    def test_google_pool_override(self):
        s = Settings(environment="development")
        assert s.google_io_pool_size == 8

    @patch.dict("os.environ", {"SHUTDOWN_TIMEOUT_SECONDS": "60"})
    def test_shutdown_timeout_override(self):
        s = Settings(environment="development")
        assert s.shutdown_timeout_seconds == 60


class TestSettingsValidation:
    """Verify production validation rules."""

    @patch.dict("os.environ", {
        "ENVIRONMENT": "production",
        "DATABASE_URL": "",
        "SECRET_KEY": "",
    }, clear=False)
    def test_production_requires_database_url(self):
        with pytest.raises(ValidationError, match="DATABASE_URL must be set"):
            Settings(environment="production", database_url="", secret_key="abc")

    @patch.dict("os.environ", {
        "ENVIRONMENT": "production",
    }, clear=False)
    def test_production_requires_secret_key(self):
        with pytest.raises(ValidationError, match="SECRET_KEY must be set"):
            Settings(
                environment="production",
                database_url="postgresql+asyncpg://u:p@h/d",
                database_sync_url="postgresql://u:p@h/d",
                secret_key="",
            )

    def test_development_auto_generates_secret(self):
        s = Settings(environment="development")
        assert len(s.secret_key) > 0


class TestSettingsProperties:
    """Verify computed properties work correctly."""

    def test_cors_origins_list(self):
        s = Settings(environment="development", cors_origins="http://a,http://b")
        assert s.cors_origins_list == ["http://a", "http://b"]

    def test_allowed_extensions_list(self):
        s = Settings(environment="development", allowed_extensions="pdf,PNG, jpg")
        assert s.allowed_extensions_list == ["pdf", "png", "jpg"]

    def test_max_upload_size_bytes(self):
        s = Settings(environment="development", max_upload_size_mb=10)
        assert s.max_upload_size_bytes == 10 * 1024 * 1024


class TestSettingsIntegration:
    """Verify the module-level settings singleton works."""

    def test_module_singleton_exists(self):
        from app.core.config import settings
        assert settings is not None
        assert settings.environment == "development"

    def test_task_manager_uses_settings(self):
        from app.services.task_manager import task_manager
        from app.core.config import settings
        # The task manager semaphores should match settings
        assert task_manager._semaphores[
            __import__("app.services.task_manager", fromlist=["TaskType"]).TaskType.DOCUMENT_PROCESSING
        ]._value == settings.max_document_concurrency
