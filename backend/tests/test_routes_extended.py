"""Additional route tests for batch, review_queue, documents, upload, auth, and settings."""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api.deps import get_db, get_current_user


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    return MagicMock(id="user-1", email="admin@test.com", name="Admin")


@pytest.fixture
def auth_client(mock_db, mock_user):
    """Client with both DB and auth overridden."""
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()


# ─── Batch Routes ────────────────────────────────────────────────────────────


class TestBatchUploadRoute:
    """Test POST /api/v1/batch/upload."""

    @pytest.mark.asyncio
    async def test_upload_no_filename(self, auth_client):
        response = await auth_client.post(
            "/api/v1/batch/upload",
            files={"file": ("", b"data", "text/csv")},
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_upload_unsupported_format(self, auth_client):
        response = await auth_client.post(
            "/api/v1/batch/upload",
            files={"file": ("test.txt", b"name,email\n", "text/plain")},
        )
        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_valid_csv(self, auth_client, mock_db):
        """Upload a valid CSV - covered by test_routes_targeted.py, skip complex mock."""
        pytest.skip("Complex multi-step DB flow - covered elsewhere")

    @pytest.mark.asyncio
    async def test_upload_parse_fails(self, auth_client, mock_db):
        """Parse failure - covered by test_routes_targeted.py."""
        pytest.skip("Complex multi-step DB flow - covered elsewhere")


class TestBatchStartRoute:
    """Test POST /api/v1/batch/{batch_id}/start."""

    @pytest.mark.asyncio
    async def test_start_not_found(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.post("/api/v1/batch/nonexistent/start")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_start_wrong_status(self, auth_client, mock_db):
        batch = MagicMock(id="b1", status="processing")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = batch
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.post("/api/v1/batch/b1/start")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_start_valid_batch(self, auth_client, mock_db):
        batch = MagicMock(
            id="b1", status="parsed", batch_code="BGV_20240101001",
            original_filename="test.csv", total_candidates=3,
            processed_candidates=0, failed_candidates=0,
            error_message=None, correlation_id="corr-1",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = batch
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.api.routes.batch.task_manager"):
            response = await auth_client.post("/api/v1/batch/b1/start")

        assert response.status_code == 200


class TestBatchLogsRoute:
    """Test GET /api/v1/batch/{batch_id}/logs/all."""

    @pytest.mark.asyncio
    async def test_logs_not_found(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.get("/api/v1/batch/nonexistent/logs/all")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_logs_found(self, auth_client, mock_db):
        batch = MagicMock(id="b1")
        log1 = MagicMock(
            id="l1", batch_import_id="b1", batch_candidate_id=None,
            level="info", stage="orchestrator", message="Starting",
            details=None, created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )

        batch_result = MagicMock()
        batch_result.scalar_one_or_none.return_value = batch

        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = [log1]

        mock_db.execute = AsyncMock(side_effect=[batch_result, logs_result])

        response = await auth_client.get("/api/v1/batch/b1/logs/all")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["level"] == "info"


class TestBatchCandidatesRoute:
    """Test GET /api/v1/batch/{batch_id}/candidates."""

    @pytest.mark.asyncio
    async def test_list_candidates(self, auth_client, mock_db):
        bc = MagicMock(
            id="bc1", batch_import_id="b1", candidate_id=None,
            row_number=1, source_candidate_id="SC001",
            source_name="John", source_email="john@test.com",
            source_phone=None, source_dob=None, source_gender=None,
            status="pending", documents_found=0, documents_processed=0,
            documents_failed=0, gmail_emails_found=0, error_message=None,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [bc]
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.get("/api/v1/batch/b1/candidates")
        assert response.status_code == 200


class TestRetryCandidate:
    """Test POST /api/v1/batch/{batch_id}/candidates/{candidate_id}/retry."""

    @pytest.mark.asyncio
    async def test_retry_not_found(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.post("/api/v1/batch/b1/candidates/bc1/retry")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_wrong_status(self, auth_client, mock_db):
        bc = MagicMock(id="bc1", batch_import_id="b1", status="completed")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = bc
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.post("/api/v1/batch/b1/candidates/bc1/retry")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_valid(self, auth_client, mock_db):
        bc = MagicMock(
            id="bc1", batch_import_id="b1", candidate_id=None,
            row_number=1, source_candidate_id="SC001",
            source_name="John", source_email="john@test.com",
            source_phone=None, source_dob=None, source_gender=None,
            status="failed", documents_found=0, documents_processed=0,
            documents_failed=0, gmail_emails_found=0, error_message="timeout",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = bc
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.api.routes.batch.task_manager"):
            response = await auth_client.post("/api/v1/batch/b1/candidates/bc1/retry")

        assert response.status_code == 200


# ─── Review Queue Routes ─────────────────────────────────────────────────────


class TestReviewQueueNotify:
    """Test POST /api/v1/review-queue/notify."""

    @pytest.mark.asyncio
    async def test_notify_empty(self, auth_client, mock_db):
        response = await auth_client.post(
            "/api/v1/review-queue/notify",
            json={"candidate_ids": []},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_notify_too_many(self, auth_client, mock_db):
        response = await auth_client.post(
            "/api/v1/review-queue/notify",
            json={"candidate_ids": [f"id-{i}" for i in range(101)]},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_notify_no_valid_candidates(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.post(
            "/api/v1/review-queue/notify",
            json={"candidate_ids": ["id-1"]},
        )
        assert response.status_code == 202
        assert response.json()["queued"] == 0

    @pytest.mark.asyncio
    async def test_notify_valid_candidates(self, auth_client, mock_db):
        bc = MagicMock(
            id="bc-1", source_email="test@test.com",
            status="partial",
        )
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [bc]
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.api.routes.review_queue.NotificationService") as mock_svc, \
             patch("app.api.routes.review_queue.task_manager"):
            mock_svc.queue_notifications = AsyncMock(return_value=["log-1"])

            response = await auth_client.post(
                "/api/v1/review-queue/notify",
                json={"candidate_ids": ["bc-1"]},
            )

        assert response.status_code == 202
        assert response.json()["queued"] == 1


class TestReviewQueueNotifications:
    """Test GET /api/v1/review-queue/notifications/{candidate_id}."""

    @pytest.mark.asyncio
    async def test_get_notifications_empty(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.get("/api/v1/review-queue/notifications/bc-1")
        assert response.status_code == 200
        assert response.json() == []


class TestRetryNotification:
    """Test POST /api/v1/review-queue/notify/retry/{notification_id}."""

    @pytest.mark.asyncio
    async def test_retry_not_found(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.post("/api/v1/review-queue/notify/retry/notif-1")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retry_not_failed(self, auth_client, mock_db):
        log = MagicMock(id="notif-1", status="sent")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = log
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.post("/api/v1/review-queue/notify/retry/notif-1")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_retry_valid(self, auth_client, mock_db):
        log = MagicMock(id="notif-1", status="failed", error_message="smtp error")
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = log
        mock_db.execute = AsyncMock(return_value=result_mock)

        with patch("app.api.routes.review_queue.task_manager"):
            response = await auth_client.post("/api/v1/review-queue/notify/retry/notif-1")

        assert response.status_code == 202


# ─── Document Routes ─────────────────────────────────────────────────────────


class TestDocumentRoutesExtended:
    """Additional document route tests."""

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.get("/api/v1/documents/nonexistent")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_documents_with_candidate_filter(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.get("/api/v1/documents?candidate_id=cand-1")
        assert response.status_code == 200


# ─── Upload Routes ───────────────────────────────────────────────────────────


class TestUploadRouteExtended:
    """Additional upload route tests."""

    @pytest.mark.asyncio
    async def test_upload_oversized_file(self, auth_client, mock_db):
        """Files over 20MB should be rejected."""
        # Create a file that claims to be large
        large_content = b"x" * (21 * 1024 * 1024)  # 21MB

        with patch("app.api.routes.upload.validate_file_content", return_value=(True, "")):
            response = await auth_client.post(
                "/api/v1/upload",
                data={"candidate_id": "cand-1"},
                files={"files": ("large.pdf", large_content, "application/pdf")},
            )

        # Should fail with size error
        assert response.status_code in (400, 413, 422)


# ─── Settings Extended ───────────────────────────────────────────────────────


class TestSettingsGmailOAuthFlow:
    """Test settings Gmail OAuth start flow."""

    @pytest.mark.asyncio
    async def test_gmail_status_not_connected(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.get("/api/v1/settings/integrations/gmail/status")
        assert response.status_code == 200
        data = response.json()
        assert data["connected"] is False


class TestSettingsDriveExtended:
    """Test settings Drive config routes."""

    @pytest.mark.asyncio
    async def test_drive_config_get_not_configured(self, auth_client, mock_db):
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result_mock)

        response = await auth_client.get("/api/v1/settings/integrations/drive/config")
        assert response.status_code == 200
