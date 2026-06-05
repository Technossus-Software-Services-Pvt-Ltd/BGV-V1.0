"""Targeted HTTP route tests - avoid multi-step flows that cause SQLite locking."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient


class TestBatchRoutes:
    """Batch route coverage - individual endpoints."""

    @pytest.mark.asyncio
    async def test_upload_valid_csv(self, authenticated_client: AsyncClient):
        csv_content = b"candidate_id,name,email\nC001,John Doe,john@example.com\nC002,Jane Doe,jane@example.com"
        resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["total_candidates"] == 2
        assert "batch_id" in data
        assert "batch_code" in data

    @pytest.mark.asyncio
    async def test_upload_empty_csv(self, authenticated_client: AsyncClient):
        csv_content = b"candidate_id,name,email\n"
        resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files={"file": ("empty.csv", csv_content, "text/csv")},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_invalid_format(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files={"file": ("test.txt", b"some text", "text/plain")},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_batches_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/batch")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_list_batches_with_status_filter(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/batch?status=completed")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_batches_with_date_filter(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/batch?date_from=2020-01-01&date_to=2030-12-31")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_batches_bad_date_ignored(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/batch?date_from=bad-date")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_batch_detail_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"/api/v1/batch/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_start_batch_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(f"/api/v1/batch/{uuid.uuid4()}/start")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_batch_logs_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"/api/v1/batch/{uuid.uuid4()}/logs")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_batch_logs_with_filters(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(
            f"/api/v1/batch/{uuid.uuid4()}/logs?level=error&stage=discovery"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_candidate_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            f"/api/v1/batch/{uuid.uuid4()}/candidates/{uuid.uuid4()}/retry"
        )
        assert resp.status_code == 404


class TestAuthRoutes:
    """Auth route tests."""

    @pytest.mark.asyncio
    async def test_google_auth_start(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/auth/google/start")
        assert resp.status_code == 200
        data = resp.json()
        assert "oauth_url" in data or "error" in data or "success" in data

    @pytest.mark.asyncio
    async def test_google_callback_invalid(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/api/v1/auth/google/callback",
            json={"code": "fake-code", "state": "invalid-state"},
        )
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_logout(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_auth_session_check(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/auth/session")
        assert resp.status_code in (200, 404)


class TestReviewQueueRoutes:
    """Review queue endpoint tests."""

    @pytest.mark.asyncio
    async def test_list_review_queue(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/review-queue?skip=0&limit=10")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_notify_nonexistent_ids(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/api/v1/review-queue/notify",
            json={"candidate_ids": [str(uuid.uuid4())]},
        )
        assert resp.status_code == 202


class TestDocumentRoutes:
    """Document route tests."""

    @pytest.mark.asyncio
    async def test_list_documents(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/documents?skip=0&limit=5")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_documents_with_status(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/documents?status=completed")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"/api/v1/documents/{uuid.uuid4()}")
        assert resp.status_code == 404


class TestCandidateRoutes:
    """Candidate route tests."""

    @pytest.mark.asyncio
    async def test_list_candidates(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/candidates")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_create_candidate(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/api/v1/candidates",
            json={"candidate_id": "TEST-001", "name": "Test Candidate", "email": "test@example.com"},
        )
        assert resp.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_get_candidate_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"/api/v1/candidates/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_candidates_with_search(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/candidates?search=nonexistent")
        assert resp.status_code == 200


class TestUploadRoutes:
    """Upload route tests."""

    @pytest.mark.asyncio
    async def test_upload_with_metadata(self, authenticated_client: AsyncClient):
        pdf_data = b"%PDF-1.4 test content"
        resp = await authenticated_client.post(
            "/api/v1/upload",
            data={
                "candidate_id": "UP-001",
                "candidate_name": "Upload Test",
            },
            files=[("files", ("doc1.pdf", pdf_data, "application/pdf"))],
        )
        assert resp.status_code == 202

    @pytest.mark.asyncio
    async def test_upload_multiple_files(self, authenticated_client: AsyncClient):
        pdf_data = b"%PDF-1.4 multi test"
        resp = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_id": "UP-002", "candidate_name": "Multi Upload"},
            files=[
                ("files", ("doc1.pdf", pdf_data, "application/pdf")),
                ("files", ("doc2.pdf", pdf_data, "application/pdf")),
            ],
        )
        assert resp.status_code == 202
        assert resp.json()["total_files"] == 2

    @pytest.mark.asyncio
    async def test_upload_no_files(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post(
            "/api/v1/upload",
            data={"candidate_name": "No Files"},
        )
        assert resp.status_code == 422


class TestWebSocketRoutes:
    """WebSocket ticket tests."""

    @pytest.mark.asyncio
    async def test_ws_ticket_creation(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post("/api/v1/ws/ticket")
        assert resp.status_code == 200
        data = resp.json()
        assert "ticket" in data
        assert len(data["ticket"]) > 20


class TestDashboardRoutes:
    """Dashboard route tests."""

    @pytest.mark.asyncio
    async def test_dashboard_stats(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_dashboard_force_refresh(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/dashboard/stats?force_refresh=true")
        assert resp.status_code == 200


class TestProcessingRoutes:
    """Processing route tests."""

    @pytest.mark.asyncio
    async def test_processing_timeline_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"/api/v1/processing/timeline/{uuid.uuid4()}")
        assert resp.status_code in (200, 404)  # May return empty list or 404

    @pytest.mark.asyncio
    async def test_list_processing_batches(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/processing/batches?skip=0&limit=10")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_processing_batch_not_found(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"/api/v1/processing/batches/{uuid.uuid4()}")
        assert resp.status_code == 404
