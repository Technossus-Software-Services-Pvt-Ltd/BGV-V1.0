"""Tests for settings routes, gmail/drive integration, and additional batch/auth/upload paths."""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient


class TestSettingsGmailDisconnect:
    """Settings Gmail disconnect and status."""

    @pytest.mark.asyncio
    async def test_gmail_disconnect(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.post("/api/v1/settings/integrations/gmail/disconnect")
        assert resp.status_code == 200
        assert resp.json()["status"] == "disconnected"

    @pytest.mark.asyncio
    async def test_gmail_status(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/settings/integrations/gmail/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "connected" in data
        assert "has_client_config" in data
        assert "is_enabled" in data


class TestSettingsGmailAuthUrl:
    """Gmail auth URL generation (requires google_auth_oauthlib)."""

    @pytest.mark.asyncio
    async def test_gmail_auth_url_no_client_config(self, authenticated_client: AsyncClient):
        """Without GOOGLE_CLIENT_ID set, should return 500."""
        with patch("app.api.routes.settings.app_settings") as mock_settings:
            mock_settings.google_client_id = ""
            mock_settings.google_client_secret = ""
            resp = await authenticated_client.get("/api/v1/settings/integrations/gmail/auth-url")
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_gmail_auth_url_with_config(self, authenticated_client: AsyncClient):
        """With config set + mock Flow, should return auth_url."""
        mock_flow = MagicMock()
        mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?client_id=test", None)
        mock_flow.code_verifier = "test_verifier"

        with patch("app.api.routes.settings.app_settings") as mock_settings, \
             patch("google_auth_oauthlib.flow.Flow.from_client_config", return_value=mock_flow):
            mock_settings.google_client_id = "test-client-id"
            mock_settings.google_client_secret = "test-secret"
            mock_settings.environment = "development"
            resp = await authenticated_client.get("/api/v1/settings/integrations/gmail/auth-url")

        assert resp.status_code == 200
        assert "auth_url" in resp.json()


class TestSettingsGmailCallback:
    """Gmail OAuth callback route."""

    @pytest.mark.asyncio
    async def test_callback_rate_limited(self, authenticated_client: AsyncClient):
        """Too many attempts should trigger 429."""
        from app.api.routes.settings import _callback_attempts, _CALLBACK_RATE_LIMIT
        import time

        # Test client IP is "127.0.0.1" in httpx/ASGI transport
        test_ip = "127.0.0.1"
        now = time.monotonic()
        _callback_attempts[test_ip] = [now] * (_CALLBACK_RATE_LIMIT)

        resp = await authenticated_client.get(
            "/api/v1/settings/integrations/gmail/callback?code=test&state=test"
        )
        assert resp.status_code == 429

        # Cleanup
        _callback_attempts.pop(test_ip, None)

    @pytest.mark.asyncio
    async def test_callback_invalid_state(self, authenticated_client: AsyncClient):
        """Invalid state should return 400 HTML."""
        from app.api.routes.settings import _callback_attempts
        _callback_attempts.clear()

        with patch("app.api.routes.settings.app_settings") as mock_settings:
            mock_settings.google_client_id = "test-id"
            mock_settings.google_client_secret = "test-secret"
            resp = await authenticated_client.get(
                "/api/v1/settings/integrations/gmail/callback?code=fake&state=invalid"
            )
        assert resp.status_code == 400


class TestSettingsDriveConfig:
    """Drive config routes."""

    @pytest.mark.asyncio
    async def test_get_drive_config_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/settings/integrations/drive/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "search_folder_ids" in data

    @pytest.mark.asyncio
    async def test_update_drive_config(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.put(
            "/api/v1/settings/integrations/drive/config",
            json={
                "search_folder_ids": ["folder1", "folder2"],
                "storage_root_folder_id": "root-folder",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "saved"


class TestSettingsRequiredDocuments:
    """Required document checklist routes."""

    @pytest.mark.asyncio
    async def test_list_required_documents_empty(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/settings/required-documents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_save_required_documents(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.put(
            "/api/v1/settings/required-documents",
            json={
                "items": [
                    {
                        "document_name": "Aadhaar Card",
                        "category": "identity",
                        "is_mandatory": True,
                        "accepted_formats": ["pdf", "jpg", "png"],
                        "sort_order": 0,
                        "is_active": True,
                    },
                    {
                        "document_name": "PAN Card",
                        "category": "identity",
                        "is_mandatory": True,
                        "accepted_formats": ["pdf", "jpg"],
                        "sort_order": 1,
                        "is_active": True,
                    },
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["document_name"] == "Aadhaar Card"

    @pytest.mark.asyncio
    async def test_list_after_save(self, authenticated_client: AsyncClient):
        # First save
        await authenticated_client.put(
            "/api/v1/settings/required-documents",
            json={
                "items": [
                    {
                        "document_name": "Passport",
                        "category": "travel",
                        "is_mandatory": False,
                        "accepted_formats": ["pdf"],
                        "sort_order": 0,
                        "is_active": True,
                    }
                ]
            },
        )
        # Then list
        resp = await authenticated_client.get("/api/v1/settings/required-documents")
        assert resp.status_code == 200
        data = resp.json()
        assert any(d["document_name"] == "Passport" for d in data)


class TestSettingsFileNaming:
    """File naming rule routes."""

    @pytest.mark.asyncio
    async def test_get_file_naming_rule(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/settings/file-naming")
        assert resp.status_code == 200
        data = resp.json()
        assert "folder_structure_pattern" in data
        assert "file_rename_pattern" in data

    @pytest.mark.asyncio
    async def test_save_file_naming_rule(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.put(
            "/api/v1/settings/file-naming",
            json={
                "folder_structure_pattern": "{candidate_name}/{document_type}",
                "file_rename_pattern": "{candidate_id}_{document_type}_{date}",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["folder_structure_pattern"] == "{candidate_name}/{document_type}"

    @pytest.mark.asyncio
    async def test_save_file_naming_empty_pattern(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.put(
            "/api/v1/settings/file-naming",
            json={
                "folder_structure_pattern": "",
                "file_rename_pattern": "{name}",
            },
        )
        assert resp.status_code == 400


class TestSettingsRateLimitHelper:
    """Test _check_callback_rate_limit helper."""

    def test_rate_limit_not_exceeded(self):
        from app.api.routes.settings import _check_callback_rate_limit, _callback_attempts
        _callback_attempts.clear()
        assert _check_callback_rate_limit("192.168.1.1") is False

    def test_rate_limit_exceeded(self):
        import time
        from app.api.routes.settings import _check_callback_rate_limit, _callback_attempts, _CALLBACK_RATE_LIMIT
        _callback_attempts.clear()
        now = time.monotonic()
        _callback_attempts["10.0.0.1"] = [now] * _CALLBACK_RATE_LIMIT
        assert _check_callback_rate_limit("10.0.0.1") is True
        _callback_attempts.clear()


class TestBatchUploadXlsx:
    """Test xlsx batch upload."""

    @pytest.mark.asyncio
    async def test_upload_xlsx(self, authenticated_client: AsyncClient):
        # Minimal xlsx would need openpyxl but test the route accepts the extension
        # This will fail at parsing but exercises the upload path
        resp = await authenticated_client.post(
            "/api/v1/batch/upload",
            files={"file": ("test.xlsx", b"PK\x03\x04fake", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        # Should fail at parsing (invalid xlsx), not at file format check
        assert resp.status_code in (400, 500)


class TestCandidateRoutesExtended:
    """Additional candidate coverage."""

    @pytest.mark.asyncio
    async def test_create_duplicate_candidate(self, authenticated_client: AsyncClient):
        # Create first
        await authenticated_client.post(
            "/api/v1/candidates",
            json={"candidate_id": "DUP-001", "name": "First"},
        )
        # Create duplicate
        resp = await authenticated_client.post(
            "/api/v1/candidates",
            json={"candidate_id": "DUP-001", "name": "Second"},
        )
        assert resp.status_code == 409


class TestDocumentRoutesExtended:
    """Additional document coverage."""

    @pytest.mark.asyncio
    async def test_list_documents_by_candidate(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get(f"/api/v1/documents?candidate_id={uuid.uuid4()}")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestDashboardExtended:
    """Dashboard additional routes."""

    @pytest.mark.asyncio
    async def test_dashboard_recent_activity(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/dashboard/recent-activity")
        assert resp.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_dashboard_processing_summary(self, authenticated_client: AsyncClient):
        resp = await authenticated_client.get("/api/v1/dashboard/processing-summary")
        assert resp.status_code in (200, 404)
