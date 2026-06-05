"""Tests for app.api.deps module and app.services.notifications.email_service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient

from app.api.deps import _extract_token, get_current_user


class TestExtractToken:
    def test_extract_from_cookie(self):
        request = MagicMock()
        request.cookies = MagicMock()
        request.cookies.get = MagicMock(return_value="cookie-token-123")
        token = _extract_token(request)
        assert token == "cookie-token-123"

    def test_extract_from_bearer_header(self):
        request = MagicMock()
        request.cookies = MagicMock()
        request.cookies.get = MagicMock(return_value=None)
        request.headers = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda key, *args: {
            "authorization": "Bearer header-token-456",
            "x-session-token": "",
        }.get(key, args[0] if args else ""))
        token = _extract_token(request)
        assert token == "header-token-456"

    def test_extract_from_x_session_token(self):
        request = MagicMock()
        request.cookies = MagicMock()
        request.cookies.get = MagicMock(return_value=None)
        request.headers = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda key, *args: {
            "authorization": "",
            "x-session-token": "x-token-789",
        }.get(key, args[0] if args else ""))
        token = _extract_token(request)
        assert token == "x-token-789"

    def test_extract_none_when_no_token(self):
        request = MagicMock()
        request.cookies = MagicMock()
        request.cookies.get = MagicMock(return_value=None)
        request.headers = MagicMock()
        request.headers.get = MagicMock(return_value="")
        token = _extract_token(request)
        # Returns empty string when no token present (falsy)
        assert not token


class TestGetCurrentUser:
    """Test auth middleware via HTTP."""

    @pytest.mark.asyncio
    async def test_unauthenticated_returns_401(self, client: AsyncClient):
        """Requesting protected endpoint without auth returns 401."""
        resp = await client.get("/api/v1/candidates")
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]


class TestNotificationService:
    """Tests for email notification service."""

    @pytest.mark.asyncio
    async def test_queue_notifications_empty(self):
        from app.services.notifications.email_service import NotificationService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await NotificationService.queue_notifications(mock_db, [])
        assert result == []

    def test_compose_email_awaiting_docs(self):
        from app.services.notifications.email_service import NotificationService
        from app.models.enums import BatchCandidateStatus

        candidate = MagicMock()
        candidate.source_name = "Priya Sharma"
        candidate.status = BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value
        candidate.error_message = None

        mandatory_names = {"PAN Card", "Aadhaar Card"}
        subject, body = NotificationService._compose_email(candidate, mandatory_names)
        assert "Action Required" in subject
        assert "Priya Sharma" in subject
        assert "PAN Card" in body or "Aadhaar Card" in body

    def test_compose_email_partial(self):
        from app.services.notifications.email_service import NotificationService
        from app.models.enums import BatchCandidateStatus

        candidate = MagicMock()
        candidate.source_name = "Rahul Kumar"
        candidate.status = BatchCandidateStatus.PARTIAL.value
        candidate.error_message = "Missing: Aadhaar Card"

        mandatory_names = {"PAN Card", "Aadhaar Card"}
        subject, body = NotificationService._compose_email(candidate, mandatory_names)
        assert "Rahul Kumar" in subject

    def test_compose_email_html_escaping(self):
        from app.services.notifications.email_service import NotificationService
        from app.models.enums import BatchCandidateStatus

        candidate = MagicMock()
        candidate.source_name = "<script>alert('xss')</script>"
        candidate.status = BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value
        candidate.error_message = None

        subject, body = NotificationService._compose_email(candidate, {"PAN Card"})
        # Verify XSS is escaped
        assert "<script>" not in body
        assert "&lt;script&gt;" in body
