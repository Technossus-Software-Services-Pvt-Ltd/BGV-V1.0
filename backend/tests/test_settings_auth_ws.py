"""Tests for settings routes, auth internals, WebSocket helpers, and integrations."""

import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.api.routes.auth import (
    _extract_session_token,
    _resolve_redirect_uri,
    _validate_oauth_config,
    _set_session_cookie,
    _clear_session_cookie,
)
from app.api.routes.settings import _check_callback_rate_limit, _callback_attempts, _get_or_create_config
from app.api.routes.ws import _consume_ws_ticket, _validate_ws_token
from app.services.integrations.gmail_scanner import GmailScanner, _EMAIL_RE, DiscoveredAttachment
from app.services.integrations.drive_service import GoogleDriveService, DiscoveredDriveFile


class TestExtractSessionToken:
    def test_from_cookie(self):
        request = MagicMock()
        request.cookies = MagicMock()
        request.cookies.get = MagicMock(return_value="token123")
        request.headers = MagicMock()
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.session_cookie_name = "bgv_session"
            token = _extract_session_token(request)
        assert token == "token123"

    def test_from_bearer_header(self):
        request = MagicMock()
        request.cookies = MagicMock()
        request.cookies.get = MagicMock(return_value=None)
        request.headers = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda k, d="": {
            "authorization": "Bearer mytoken",
            "x-session-token": "",
        }.get(k, d))
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.session_cookie_name = "bgv_session"
            token = _extract_session_token(request)
        assert token == "mytoken"

    def test_from_x_session_header(self):
        request = MagicMock()
        request.cookies = MagicMock()
        request.cookies.get = MagicMock(return_value=None)
        request.headers = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda k, d="": {
            "authorization": "",
            "x-session-token": "xtoken",
        }.get(k, d))
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.session_cookie_name = "bgv_session"
            token = _extract_session_token(request)
        assert token == "xtoken"


class TestResolveRedirectUri:
    def test_explicit_redirect_uri(self):
        result = _resolve_redirect_uri(None, "http://example.com/callback")
        assert result == "http://example.com/callback"

    def test_from_origin_header(self):
        request = MagicMock()
        request.headers = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda k, d="": {
            "origin": "http://localhost:3000",
            "referer": "",
        }.get(k, d))
        result = _resolve_redirect_uri(request, None)
        assert result == "http://localhost:3000/auth/callback"

    def test_from_referer_header(self):
        request = MagicMock()
        request.headers.get = MagicMock(side_effect=lambda k, d="": {
            "origin": "",
            "referer": "https://app.example.com/dashboard",
        }.get(k, d))
        result = _resolve_redirect_uri(request, None)
        assert result == "https://app.example.com/auth/callback"

    def test_fallback_to_settings(self):
        request = MagicMock()
        request.headers.get = MagicMock(return_value="")
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.google_redirect_uri = "http://default/callback"
            result = _resolve_redirect_uri(request, None)
        assert result == "http://default/callback"


class TestValidateOAuthConfig:
    def test_raises_if_not_configured(self):
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.google_client_id = ""
            mock_settings.google_client_secret = ""
            with pytest.raises(Exception):
                _validate_oauth_config()

    def test_passes_if_configured(self):
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.google_client_id = "client-id"
            mock_settings.google_client_secret = "client-secret"
            _validate_oauth_config()  # Should not raise


class TestSetSessionCookie:
    def test_sets_cookie(self):
        response = MagicMock()
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.session_cookie_name = "bgv_session"
            mock_settings.session_cookie_secure = False
            mock_settings.session_cookie_samesite = "lax"
            mock_settings.session_cookie_domain = None
            _set_session_cookie(response, "token123")
        response.set_cookie.assert_called_once()
        kwargs = response.set_cookie.call_args.kwargs
        assert kwargs["value"] == "token123"
        assert kwargs["httponly"] is True

    def test_clears_cookie(self):
        response = MagicMock()
        with patch("app.api.routes.auth.settings") as mock_settings:
            mock_settings.session_cookie_name = "bgv_session"
            mock_settings.session_cookie_secure = False
            mock_settings.session_cookie_samesite = "lax"
            mock_settings.session_cookie_domain = None
            _clear_session_cookie(response)
        response.delete_cookie.assert_called_once()


class TestCheckCallbackRateLimit:
    def setup_method(self):
        _callback_attempts.clear()

    def test_allows_under_limit(self):
        assert _check_callback_rate_limit("192.168.1.1") is False
        assert _check_callback_rate_limit("192.168.1.1") is False

    def test_blocks_over_limit(self):
        for _ in range(5):
            _check_callback_rate_limit("10.0.0.1")
        assert _check_callback_rate_limit("10.0.0.1") is True

    def test_different_ips_independent(self):
        for _ in range(5):
            _check_callback_rate_limit("10.0.0.1")
        assert _check_callback_rate_limit("10.0.0.2") is False


class TestGetOrCreateConfig:
    @pytest.mark.asyncio
    async def test_returns_existing(self):
        db = AsyncMock()
        existing = MagicMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        db.execute.return_value = result_mock

        config = await _get_or_create_config(db, "gmail")
        assert config is existing

    @pytest.mark.asyncio
    async def test_creates_new_if_not_found(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        config = await _get_or_create_config(db, "gmail")
        db.add.assert_called_once()
        db.commit.assert_called_once()
        assert config.provider == "gmail"
        assert config.is_enabled is False


class TestConsumeWSTicket:
    @pytest.mark.asyncio
    async def test_valid_ticket_consumed(self):
        mock_ticket = MagicMock()
        mock_ticket.expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute.return_value = result_mock

        with patch("app.api.routes.ws.AsyncSessionLocal") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await _consume_ws_ticket("valid-ticket")

        assert result is True
        mock_db.delete.assert_called_once_with(mock_ticket)

    @pytest.mark.asyncio
    async def test_invalid_ticket_returns_false(self):
        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        with patch("app.api.routes.ws.AsyncSessionLocal") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await _consume_ws_ticket("bad-ticket")

        assert result is False

    @pytest.mark.asyncio
    async def test_expired_ticket_returns_false(self):
        mock_ticket = MagicMock()
        mock_ticket.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_ticket
        mock_db.execute.return_value = result_mock

        with patch("app.api.routes.ws.AsyncSessionLocal") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await _consume_ws_ticket("expired-ticket")

        assert result is False


class TestValidateWSToken:
    @pytest.mark.asyncio
    async def test_empty_token_returns_false(self):
        result = await _validate_ws_token("")
        assert result is False

    @pytest.mark.asyncio
    async def test_valid_session_returns_true(self):
        mock_session = MagicMock()
        mock_session.revoked_at = None
        mock_session.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_session.user = MagicMock(is_active=True)

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = result_mock

        with patch("app.api.routes.ws.AsyncSessionLocal") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await _validate_ws_token("valid-token")

        assert result is True

    @pytest.mark.asyncio
    async def test_revoked_session_returns_false(self):
        mock_session = MagicMock()
        mock_session.revoked_at = datetime.now(timezone.utc)
        mock_session.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        mock_session.user = MagicMock(is_active=True)

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = mock_session
        mock_db.execute.return_value = result_mock

        with patch("app.api.routes.ws.AsyncSessionLocal") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await _validate_ws_token("revoked-token")

        assert result is False

    @pytest.mark.asyncio
    async def test_no_session_returns_false(self):
        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result_mock

        with patch("app.api.routes.ws.AsyncSessionLocal") as mock_ctx:
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)
            result = await _validate_ws_token("nonexistent")

        assert result is False


class TestGmailScannerEmailValidation:
    def test_valid_email(self):
        assert _EMAIL_RE.match("test@example.com") is not None

    def test_invalid_email(self):
        assert _EMAIL_RE.match("not-an-email") is None
        assert _EMAIL_RE.match("test@") is None
        assert _EMAIL_RE.match("") is None

    def test_email_with_special_chars(self):
        assert _EMAIL_RE.match("test+tag@example.com") is not None
        assert _EMAIL_RE.match("user.name@domain.co.uk") is not None


class TestDiscoveredAttachmentDataclass:
    def test_creation(self):
        att = DiscoveredAttachment(
            message_id="msg-1",
            attachment_id="att-1",
            filename="doc.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            subject="Documents",
            sender="test@example.com",
            date="2024-01-01",
        )
        assert att.filename == "doc.pdf"
        assert att.size_bytes == 1024


class TestDiscoveredDriveFileDataclass:
    def test_creation(self):
        f = DiscoveredDriveFile(
            file_id="file-1",
            filename="scan.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            parent_folder_id="folder-1",
            parent_folder_name="Documents",
            modified_time="2024-01-01T00:00:00Z",
            web_view_link="https://drive.google.com/file/d/file-1",
        )
        assert f.file_id == "file-1"
        assert f.filename == "scan.pdf"


class TestGoogleDriveServiceConsts:
    def test_supported_mimes(self):
        assert "application/pdf" in GoogleDriveService.SUPPORTED_MIMES
        assert "image/jpeg" in GoogleDriveService.SUPPORTED_MIMES

    def test_exportable_mimes(self):
        assert "application/vnd.google-apps.document" in GoogleDriveService.EXPORTABLE_MIMES


class TestSettingsRouteDisconnect:
    """Test settings route disconnect and status via authenticated HTTP client."""

    @pytest.mark.asyncio
    async def test_disconnect_clears_credentials(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post("/api/v1/settings/integrations/gmail/disconnect")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_gmail_status_not_connected(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/settings/integrations/gmail/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False

    @pytest.mark.asyncio
    async def test_get_drive_config_default(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/settings/integrations/drive/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "search_folder_ids" in data

    @pytest.mark.asyncio
    async def test_update_drive_config(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.put(
            "/api/v1/settings/integrations/drive/config",
            json={"search_folder_ids": ["folder-1"], "storage_root_folder_id": "root-1"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_required_documents_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/settings/required-documents")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_save_required_documents(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.put(
            "/api/v1/settings/required-documents",
            json={"items": [
                {"document_name": "Aadhaar Card", "category": "ID", "is_mandatory": True,
                 "accepted_formats": ["pdf", "jpg"], "sort_order": 0, "is_active": True}
            ]},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_file_naming_rule(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/settings/file-naming")
        assert resp.status_code == 200
        data = resp.json()
        assert "folder_structure_pattern" in data

    @pytest.mark.asyncio
    async def test_update_file_naming_rule(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.put(
            "/api/v1/settings/file-naming",
            json={
                "folder_structure_pattern": "{CandidateID}_{Date}",
                "file_rename_pattern": "{DocType}_{FirstName}",
            },
        )
        assert resp.status_code == 200
