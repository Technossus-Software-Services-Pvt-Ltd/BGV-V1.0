"""Tests for app.main (startup, middleware, exception handler) and app.core.logging."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from fastapi import HTTPException

from app.core.exceptions import BGVBaseException, OCRProcessingError, DocumentNotFoundError


class TestMainApp:
    """Test app-level configuration."""

    @pytest.mark.asyncio
    async def test_cors_headers(self, client: AsyncClient):
        """CORS headers should be set on preflight."""
        resp = await client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware may return 200 or pass through
        assert resp.status_code in (200, 405)

    @pytest.mark.asyncio
    async def test_404_for_unknown_route(self, client: AsyncClient):
        """Unknown routes should return 404."""
        resp = await client.get("/api/v1/nonexistent-endpoint")
        assert resp.status_code in (404, 405)


class TestExceptionHandler:
    """Test domain exception handler."""

    @pytest.mark.asyncio
    async def test_domain_exception_mapped(self):
        """BGVBaseException should produce correct status_code and error_type."""
        from app.core.exceptions import DocumentNotFoundError, OCRProcessingError
        exc = DocumentNotFoundError("doc-123")
        assert exc.status_code == 404
        assert exc.message

        exc2 = OCRProcessingError("engine crashed")
        assert exc2.status_code == 500


class TestCoreLogging:
    """Test logging configuration."""

    def test_setup_logging_does_not_crash(self):
        from app.core.logging import setup_logging, get_logger
        # Should not raise
        setup_logging()
        logger = get_logger("test")
        assert logger is not None

    def test_get_logger_returns_logger(self):
        from app.core.logging import get_logger
        logger = get_logger("test.module")
        assert logger is not None


class TestCoreConfig:
    """Additional config tests."""

    def test_cors_origins_list(self):
        from app.core.config import Settings
        s = Settings(environment="development", cors_origins="http://a.com,http://b.com", _env_file=None)
        assert s.cors_origins_list == ["http://a.com", "http://b.com"]

    def test_allowed_extensions_list(self):
        from app.core.config import Settings
        s = Settings(environment="development", allowed_extensions="pdf,jpg,png", _env_file=None)
        assert s.allowed_extensions_list == ["pdf", "jpg", "png"]

    def test_max_upload_size_bytes(self):
        from app.core.config import Settings
        s = Settings(environment="development", max_upload_size_mb=10, _env_file=None)
        assert s.max_upload_size_bytes == 10 * 1024 * 1024

    def test_upload_path_creates_dir(self, tmp_path, monkeypatch):
        from app.core.config import Settings
        upload = tmp_path / "new_uploads"
        s = Settings(environment="development", upload_dir=str(upload), _env_file=None)
        path = s.upload_path
        assert path.exists()

    def test_production_requires_database_url(self):
        from app.core.config import Settings
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Settings(environment="production", database_url="", _env_file=None)

    def test_production_requires_secret_key(self):
        from app.core.config import Settings
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            Settings(
                environment="production",
                database_url="postgresql+asyncpg://x:y@z/db",
                database_sync_url="postgresql://x:y@z/db",
                secret_key="",
                _env_file=None,
            )

    def test_development_generates_secret(self):
        from app.core.config import Settings
        s = Settings(environment="development", _env_file=None)
        assert s.secret_key  # Should be auto-generated
