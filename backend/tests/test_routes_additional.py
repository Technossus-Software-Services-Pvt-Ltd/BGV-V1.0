"""Tests for processing routes, upload routes additional coverage, and auth routes."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from pathlib import Path

from app.api.utils import parse_date_param
from fastapi import HTTPException


class TestParseDateParam:
    def test_valid_date(self):
        result = parse_date_param("2024-01-15", "date_from")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_invalid_date_raises(self):
        with pytest.raises(HTTPException) as exc:
            parse_date_param("not-a-date", "date_from")
        assert exc.value.status_code == 400
        assert "Invalid" in exc.value.detail

    def test_wrong_format_raises(self):
        with pytest.raises(HTTPException):
            parse_date_param("15/01/2024", "date_to")


class TestProcessingRoutes:
    """Test processing timeline and batch routes."""

    @pytest.mark.asyncio
    async def test_processing_timeline_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/processing/timeline/nonexistent-doc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == "nonexistent-doc"
        assert data["events"] == []
        assert data["current_status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_processing_batches_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/processing/batches")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_processing_batch_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/processing/batches/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_audit_logs_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/audit/logs")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_audit_logs_with_filters(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/audit/logs", params={
            "correlation_id": "test-corr",
            "action": "upload",
        })
        assert resp.status_code == 200


class TestUploadRouteAdditional:
    """Additional upload route tests."""

    @pytest.mark.asyncio
    async def test_upload_invalid_candidate_id_format(self, authenticated_client: AsyncClient, upload_dir: Path, sample_pdf_bytes: bytes):
        """Invalid candidate_id format should fail."""
        resp = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "invalid id with spaces!", "candidate_name": "Test"},
            files=[("files", ("test.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 400
        assert "Invalid candidate_id" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_too_many_files(self, authenticated_client: AsyncClient, upload_dir: Path, sample_pdf_bytes: bytes):
        """Uploading more than max files should fail."""
        from app.core.config import settings
        files = [
            ("files", (f"doc{i}.pdf", sample_pdf_bytes, "application/pdf"))
            for i in range(settings.max_files_per_upload + 1)
        ]
        resp = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-MANY", "candidate_name": "Many Files"},
            files=files,
        )
        assert resp.status_code == 400
        assert "Maximum" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_creates_candidate_and_batch(self, authenticated_client: AsyncClient, upload_dir: Path, sample_pdf_bytes: bytes):
        """Upload creates candidate, batch, and returns proper response."""
        resp = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-NEW-001", "candidate_name": "New Candidate"},
            files=[("files", ("document.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["total_files"] == 1
        assert data["batch_reference"].startswith("BATCH-")
        assert data["correlation_id"]
        assert len(data["documents"]) == 1

    @pytest.mark.asyncio
    async def test_upload_reuses_existing_candidate(self, authenticated_client: AsyncClient, upload_dir: Path, sample_pdf_bytes: bytes):
        """Second upload for same candidate_id reuses the candidate record."""
        await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-REUSE", "candidate_name": "Reuse Test"},
            files=[("files", ("doc1.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        resp = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-REUSE", "candidate_name": "Reuse Test"},
            files=[("files", ("doc2.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        assert resp.status_code == 202

        # List candidates - should only be one with that candidate_id
        cands_resp = await authenticated_client.get("/api/v1/candidates")
        matching = [c for c in cands_resp.json()["candidates"] if c["candidate_id"] == "CAND-REUSE"]
        assert len(matching) == 1


class TestDocumentsRouteFilters:
    """Test document list filters."""

    @pytest.mark.asyncio
    async def test_documents_filter_by_candidate(self, authenticated_client: AsyncClient, upload_dir: Path, sample_pdf_bytes: bytes):
        """Upload for one candidate then filter by candidate_id."""
        upload_resp = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "CAND-FILTER-A", "candidate_name": "Filter A"},
            files=[("files", ("a.pdf", sample_pdf_bytes, "application/pdf"))],
        )
        candidate_id = upload_resp.json()["candidate_id"]

        resp = await authenticated_client.get(f"/api/v1/documents?candidate_id={candidate_id}")
        assert resp.status_code == 200
        docs = resp.json()
        assert all(d["candidate_id"] == candidate_id for d in docs)

    @pytest.mark.asyncio
    async def test_documents_with_pagination(self, authenticated_client: AsyncClient):
        """Pagination params work."""
        resp = await authenticated_client.get("/api/v1/documents?skip=0&limit=5")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_documents_with_date_filter(self, authenticated_client: AsyncClient):
        """Date filter params work."""
        resp = await authenticated_client.get("/api/v1/documents?date_from=2020-01-01&date_to=2099-12-31")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_documents_invalid_date_filter(self, authenticated_client: AsyncClient):
        """Invalid date format returns 400."""
        resp = await authenticated_client.get("/api/v1/documents?date_from=invalid")
        assert resp.status_code == 400


class TestAuthRoutesAdditional:
    """Additional auth route coverage."""

    @pytest.mark.asyncio
    async def test_google_auth_start_with_config(self, authenticated_client: AsyncClient):
        """Auth start with configured OAuth should return URL."""
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.google_client_id = "test-client-id"
            mock_settings.google_client_secret = "test-secret"
            mock_settings.google_redirect_uri = "http://localhost:3000/auth/callback"
            mock_settings.session_cookie_name = "bgv_session"
            mock_settings.session_cookie_secure = False
            mock_settings.session_cookie_samesite = "lax"
            mock_settings.session_cookie_domain = ""

            resp = await authenticated_client.get("/api/v1/auth/google/start")
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert "accounts.google.com" in data["oauth_url"]
            assert data["state"]

    @pytest.mark.asyncio
    async def test_google_callback_expired_state(self, authenticated_client: AsyncClient, db_session):
        """Callback with expired state should return 400."""
        from app.models.oauth_state import OAuthState
        from datetime import datetime, timezone, timedelta

        # Create an expired state
        state = OAuthState(
            state="expired-state-123",
            redirect_uri="http://localhost:3000/auth/callback",
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db_session.add(state)
        await db_session.commit()

        resp = await authenticated_client.post(
            "/api/v1/auth/google/callback",
            json={"code": "fake-code", "state": "expired-state-123"},
        )
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"].lower()
