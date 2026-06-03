"""Tests for Phase 4: Structured Error Handling.

Verifies that:
1. Exception hierarchy with status_code attributes is correct
2. Global exception handler maps domain exceptions to proper HTTP responses
3. Unhandled exception handler returns safe 500
4. ParseError inherits from BGVBaseException
5. Exception response shape is consistent
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.core.exceptions import (
    BGVBaseException,
    DocumentNotFoundError,
    CandidateNotFoundError,
    BatchNotFoundError,
    IntegrationNotFoundError,
    BatchParseError,
    ValidationError,
    FileStorageError,
    OCRProcessingError,
    AIClassificationError,
    OllamaConnectionError,
    IntegrationConnectionError,
    ProcessingTimeoutError,
)
from app.services.batch.parser import ParseError


class TestExceptionHierarchy:
    """Verify all domain exceptions have correct status_code and inherit from BGVBaseException."""

    @pytest.mark.parametrize("exc_class,expected_code", [
        (BGVBaseException, 500),
        (DocumentNotFoundError, 404),
        (CandidateNotFoundError, 404),
        (BatchNotFoundError, 404),
        (IntegrationNotFoundError, 404),
        (BatchParseError, 400),
        (ValidationError, 422),
        (FileStorageError, 500),
        (OCRProcessingError, 500),
        (AIClassificationError, 500),
        (OllamaConnectionError, 503),
        (IntegrationConnectionError, 503),
        (ProcessingTimeoutError, 504),
    ])
    def test_status_code_attribute(self, exc_class, expected_code):
        assert exc_class.status_code == expected_code

    @pytest.mark.parametrize("exc_class", [
        DocumentNotFoundError,
        CandidateNotFoundError,
        BatchNotFoundError,
        IntegrationNotFoundError,
        BatchParseError,
        ValidationError,
        FileStorageError,
        OCRProcessingError,
        AIClassificationError,
        OllamaConnectionError,
        IntegrationConnectionError,
        ProcessingTimeoutError,
    ])
    def test_all_inherit_from_base(self, exc_class):
        assert issubclass(exc_class, BGVBaseException)

    def test_parse_error_inherits_from_batch_parse_error(self):
        assert issubclass(ParseError, BatchParseError)
        assert issubclass(ParseError, BGVBaseException)
        assert ParseError.status_code == 400


class TestExceptionConstruction:
    """Verify exception construction and attributes."""

    def test_basic_construction(self):
        exc = BGVBaseException("Something failed")
        assert exc.message == "Something failed"
        assert exc.correlation_id is None
        assert exc.details == {}
        assert str(exc) == "Something failed"

    def test_construction_with_correlation_id(self):
        exc = DocumentNotFoundError("Doc not found", correlation_id="corr-123")
        assert exc.message == "Doc not found"
        assert exc.correlation_id == "corr-123"

    def test_construction_with_details(self):
        exc = OCRProcessingError(
            "OCR failed",
            correlation_id="corr-456",
            details={"page": 3, "engine": "paddleocr"},
        )
        assert exc.details == {"page": 3, "engine": "paddleocr"}
        assert exc.correlation_id == "corr-456"

    def test_details_defaults_to_empty_dict(self):
        exc = FileStorageError("Write failed")
        assert exc.details == {}


class TestGlobalExceptionHandler:
    """Verify the global exception handler returns correct HTTP responses."""

    @pytest.fixture
    def app(self):
        """Get the FastAPI app for testing."""
        from app.main import app
        return app

    @pytest.mark.asyncio
    async def test_domain_exception_returns_correct_status(self, app):
        """A DocumentNotFoundError should return 404 with structured body."""
        from fastapi import APIRouter

        # Add a test route that raises a domain exception
        test_router = APIRouter()

        @test_router.get("/test-404")
        async def raise_not_found():
            raise DocumentNotFoundError("Test doc not found", correlation_id="test-corr")

        app.include_router(test_router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/test-404")

        assert response.status_code == 404
        body = response.json()
        assert body["detail"] == "Test doc not found"
        assert body["error_type"] == "DocumentNotFoundError"
        assert body["correlation_id"] == "test-corr"

    @pytest.mark.asyncio
    async def test_domain_exception_without_correlation_id(self, app):
        """When no correlation_id, it should not appear in response."""
        from fastapi import APIRouter

        test_router = APIRouter()

        @test_router.get("/test-503")
        async def raise_connection_error():
            raise OllamaConnectionError("Ollama is down")

        app.include_router(test_router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/test-503")

        assert response.status_code == 503
        body = response.json()
        assert body["detail"] == "Ollama is down"
        assert body["error_type"] == "OllamaConnectionError"
        assert "correlation_id" not in body

    @pytest.mark.asyncio
    async def test_unhandled_exception_returns_safe_500(self, app):
        """Unhandled exceptions should return 500 without leaking internals."""
        from fastapi import APIRouter

        test_router = APIRouter()

        @test_router.get("/test-unhandled")
        async def raise_unhandled():
            raise RuntimeError("SECRET_DB_PASSWORD leaked in error")

        app.include_router(test_router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/test-unhandled")

        assert response.status_code == 500
        body = response.json()
        assert body["detail"] == "Internal server error"
        assert body["error_type"] == "InternalError"
        # Ensure no sensitive info leaked
        assert "SECRET_DB_PASSWORD" not in str(body)

    @pytest.mark.asyncio
    async def test_domain_exception_with_details(self, app):
        """Details dict should appear in response when provided."""
        from fastapi import APIRouter

        test_router = APIRouter()

        @test_router.get("/test-details")
        async def raise_with_details():
            raise OCRProcessingError(
                "OCR engine crashed",
                details={"page": 2, "engine": "paddleocr"},
            )

        app.include_router(test_router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/test-details")

        assert response.status_code == 500
        body = response.json()
        assert body["details"] == {"page": 2, "engine": "paddleocr"}
