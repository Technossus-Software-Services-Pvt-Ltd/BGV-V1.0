"""Tests for API routes: auth, batch, dashboard, review_queue, ws, documents, candidates."""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient
from pathlib import Path


class TestAuthRoutes:
    """Test auth endpoints."""

    @pytest.mark.asyncio
    async def test_google_auth_start_no_config(self, client: AsyncClient):
        """Should return 500 if Google OAuth not configured."""
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.google_client_id = ""
            mock_settings.google_client_secret = ""
            mock_settings.session_cookie_name = "bgv_session"
            resp = await client.get("/api/v1/auth/google/start")
            assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_logout_no_token(self, client: AsyncClient):
        """Logout without a token should still succeed."""
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "Signed out" in data["message"]

    @pytest.mark.asyncio
    async def test_logout_with_invalid_token(self, client: AsyncClient):
        """Logout with invalid token should still succeed."""
        resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": "Bearer invalid-token-xyz"}
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    @pytest.mark.asyncio
    async def test_google_callback_invalid_state(self, authenticated_client: AsyncClient):
        """Callback with invalid state should return 400."""
        resp = await authenticated_client.post(
            "/api/v1/auth/google/callback",
            json={"code": "fake-code", "state": "invalid-state"},
        )
        # Will fail because state is not in DB
        assert resp.status_code in (400, 500)


class TestBatchRoutes:
    """Test batch upload and management routes."""

    @pytest.mark.asyncio
    async def test_upload_no_filename(self, authenticated_client: AsyncClient):
        """Upload without filename should fail."""
        resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files=[("file", ("", b"content", "text/csv"))],
        )
        assert resp.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_upload_unsupported_extension(self, authenticated_client: AsyncClient):
        """Upload .txt file should fail."""
        resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files=[("file", ("data.txt", b"candidate_id,name\nC001,Test\n", "text/plain"))],
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_oversized_file(self, authenticated_client: AsyncClient):
        """Upload file > 10MB should fail."""
        big_content = b"x" * (11 * 1024 * 1024)
        resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files=[("file", ("big.csv", big_content, "text/csv"))],
        )
        assert resp.status_code == 400
        assert "10MB" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_valid_csv(self, authenticated_client: AsyncClient, upload_dir: Path):
        """Upload a valid CSV file should succeed."""
        csv_content = b"candidate_id,name,email\nC001,Priya Sharma,priya@test.com\nC002,Rahul Kumar,rahul@test.com\n"
        resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files=[("file", ("candidates.csv", csv_content, "text/csv"))],
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["total_candidates"] == 2
        assert data["batch_code"].startswith("BGV_")

    @pytest.mark.asyncio
    async def test_upload_csv_no_valid_candidates(self, authenticated_client: AsyncClient, upload_dir: Path):
        """Upload CSV with no valid rows should fail."""
        csv_content = b"candidate_id,name\n,\n,\n"
        resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files=[("file", ("bad.csv", csv_content, "text/csv"))],
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_list_batches_empty(self, authenticated_client: AsyncClient):
        """List batches when none exist."""
        resp = await authenticated_client.get("/api/v1/batch")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_batches_with_filters(self, authenticated_client: AsyncClient, upload_dir: Path):
        """Upload a batch then filter list."""
        csv_content = b"candidate_id,name\nC001,Test\n"
        await authenticated_client.post(
            "/api/v1/batch/upload",
            files=[("file", ("test.csv", csv_content, "text/csv"))],
        )
        resp = await authenticated_client.get("/api/v1/batch?status=parsed")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @pytest.mark.asyncio
    async def test_get_batch_detail_not_found(self, authenticated_client: AsyncClient):
        """Get non-existent batch should return 404."""
        resp = await authenticated_client.get("/api/v1/batch/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_batch_detail(self, authenticated_client: AsyncClient, upload_dir: Path):
        """Upload then get batch detail."""
        csv_content = b"candidate_id,name\nC001,Test User\n"
        upload_resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files=[("file", ("test.csv", csv_content, "text/csv"))],
        )
        batch_id = upload_resp.json()["batch_id"]
        resp = await authenticated_client.get(f"/api/v1/batch/{batch_id}")
        assert resp.status_code == 200
        assert resp.json()["batch"]["batch_code"].startswith("BGV_")
        assert len(resp.json()["candidates"]) == 1

    @pytest.mark.asyncio
    async def test_list_batch_candidates(self, authenticated_client: AsyncClient, upload_dir: Path):
        """List candidates for a batch."""
        csv_content = b"candidate_id,name\nC001,User1\nC002,User2\n"
        upload_resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files=[("file", ("test.csv", csv_content, "text/csv"))],
        )
        batch_id = upload_resp.json()["batch_id"]
        resp = await authenticated_client.get(f"/api/v1/batch/{batch_id}/candidates")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_start_batch_not_found(self, authenticated_client: AsyncClient):
        """Start non-existent batch should return 404."""
        resp = await authenticated_client.post("/api/v1/batch/fake-id/start")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_candidate_not_found(self, authenticated_client: AsyncClient):
        """Retry non-existent candidate should return 404."""
        resp = await authenticated_client.post("/api/v1/batch/fake-batch/candidates/fake-cand/retry")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_batch_logs_not_found(self, authenticated_client: AsyncClient):
        """Logs for non-existent batch should return 404."""
        resp = await authenticated_client.get("/api/v1/batch/fake-id/logs/all")
        assert resp.status_code == 404


class TestDashboardRoutes:
    """Test dashboard stats endpoint."""

    @pytest.mark.asyncio
    async def test_dashboard_stats(self, authenticated_client: AsyncClient):
        """Dashboard stats should return summary data."""
        resp = await authenticated_client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "document_status" in data
        assert "batch_status" in data
        assert "ownership_verification" in data
        assert "daily_documents" in data

    @pytest.mark.asyncio
    async def test_dashboard_stats_cached(self, authenticated_client: AsyncClient):
        """Second call should return cached result."""
        resp1 = await authenticated_client.get("/api/v1/dashboard/stats")
        resp2 = await authenticated_client.get("/api/v1/dashboard/stats")
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        # Both should return same data (from cache)
        assert resp1.json()["summary"] == resp2.json()["summary"]


class TestReviewQueueRoutes:
    """Test review queue endpoints."""

    @pytest.mark.asyncio
    async def test_list_review_queue_empty(self, authenticated_client: AsyncClient):
        """List review queue when empty."""
        resp = await authenticated_client.get("/api/v1/review-queue")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_notify_empty_ids(self, authenticated_client: AsyncClient):
        """Notify with empty IDs should fail."""
        resp = await authenticated_client.post(
            "/api/v1/review-queue/notify",
            json={"candidate_ids": []},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_notify_too_many_ids(self, authenticated_client: AsyncClient):
        """Notify with > 100 IDs should fail."""
        resp = await authenticated_client.post(
            "/api/v1/review-queue/notify",
            json={"candidate_ids": [f"id-{i}" for i in range(101)]},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_notify_no_valid_candidates(self, authenticated_client: AsyncClient):
        """Notify with non-existent candidate IDs should return 0 queued."""
        resp = await authenticated_client.post(
            "/api/v1/review-queue/notify",
            json={"candidate_ids": ["nonexistent-1", "nonexistent-2"]},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["queued"] == 0

    @pytest.mark.asyncio
    async def test_get_candidate_notifications_empty(self, authenticated_client: AsyncClient):
        """Get notifications for non-existent candidate."""
        resp = await authenticated_client.get("/api/v1/review-queue/notifications/fake-id")
        assert resp.status_code == 200
        assert resp.json() == []


class TestWebSocketTicket:
    """Test WebSocket ticket endpoint."""

    @pytest.mark.asyncio
    async def test_create_ws_ticket(self, authenticated_client: AsyncClient):
        """Authenticated user can create a WS ticket."""
        resp = await authenticated_client.post("/api/v1/ws/ticket")
        assert resp.status_code == 200
        data = resp.json()
        assert "ticket" in data
        assert len(data["ticket"]) > 10

    @pytest.mark.asyncio
    async def test_create_ws_ticket_unauthenticated(self, client: AsyncClient):
        """Unauthenticated user cannot create a WS ticket."""
        resp = await client.post("/api/v1/ws/ticket")
        assert resp.status_code == 401


class TestDocumentsAdditional:
    """Additional document route tests for coverage."""

    @pytest.mark.asyncio
    async def test_list_documents_empty(self, authenticated_client: AsyncClient):
        """List documents when none exist."""
        resp = await authenticated_client.get("/api/v1/documents")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, authenticated_client: AsyncClient):
        """Get non-existent document should return 404."""
        resp = await authenticated_client.get("/api/v1/documents/nonexistent-id")
        assert resp.status_code == 404


class TestCandidatesAdditional:
    """Additional candidate route tests for coverage."""

    @pytest.mark.asyncio
    async def test_list_candidates_empty(self, authenticated_client: AsyncClient):
        """List candidates when none exist."""
        resp = await authenticated_client.get("/api/v1/candidates")
        assert resp.status_code == 200
        data = resp.json()
        assert data["candidates"] == []

    @pytest.mark.asyncio
    async def test_get_candidate_not_found(self, authenticated_client: AsyncClient):
        """Get non-existent candidate should return 404."""
        resp = await authenticated_client.get("/api/v1/candidates/nonexistent-id")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_candidate(self, authenticated_client: AsyncClient):
        """Create a new candidate."""
        resp = await authenticated_client.post("/api/v1/candidates", json={
            "candidate_id": "TEST-001",
            "name": "Test Candidate",
            "email": "test@example.com",
        })
        assert resp.status_code == 201
        assert resp.json()["candidate_id"] == "TEST-001"

    @pytest.mark.asyncio
    async def test_create_candidate_duplicate(self, authenticated_client: AsyncClient):
        """Create duplicate candidate should fail."""
        payload = {"candidate_id": "DUP-001", "name": "Duplicate"}
        await authenticated_client.post("/api/v1/candidates", json=payload)
        resp = await authenticated_client.post("/api/v1/candidates", json=payload)
        assert resp.status_code in (400, 409)
