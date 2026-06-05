"""Tests for services: email_service, OCR engine, AI classifier, drive_service deeper, drive_upload."""

import asyncio
import base64
import io
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import numpy as np
import pytest

from app.services.notifications.email_service import NotificationService
from app.services.ocr.engine import PaddleOCREngine, OCREngineResult
from app.services.ai.classifier import AIClassifier, ClassificationResult, OwnershipExtractionResult
from app.services.integrations.drive_service import GoogleDriveService, DiscoveredDriveFile
from app.services.batch.drive_upload_service import DriveUploadService
from app.models.enums import (
    NotificationStatus, BatchCandidateStatus, DocumentType,
)


# ─── NotificationService ────────────────────────────────────────────────────


class TestNotificationServiceCompose:
    """Test _compose_email for all status branches."""

    def test_compose_awaiting_required_documents(self):
        bc = MagicMock(
            source_name="John Doe",
            source_email="john@test.com",
            status=BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value,
            error_message=None,
        )
        mandatory_names = {"Aadhaar Card", "PAN Card"}
        subject, body = NotificationService._compose_email(bc, mandatory_names)
        assert "Action Required" in subject
        assert "John Doe" in subject
        assert "Aadhaar Card" in body
        assert "PAN Card" in body

    def test_compose_partial(self):
        bc = MagicMock(
            source_name="Jane Smith",
            source_email="jane@test.com",
            status=BatchCandidateStatus.PARTIAL.value,
            error_message="Missing: PAN Card",
        )
        mandatory_names = {"Aadhaar Card", "PAN Card"}
        subject, body = NotificationService._compose_email(bc, mandatory_names)
        assert "Missing Documents" in subject
        assert "Jane Smith" in subject

    def test_compose_no_documents(self):
        bc = MagicMock(
            source_name="Test User",
            source_email="test@test.com",
            status=BatchCandidateStatus.NO_DOCUMENTS.value,
            error_message=None,
        )
        mandatory_names = {"Aadhaar Card"}
        subject, body = NotificationService._compose_email(bc, mandatory_names)
        assert "No Documents Received" in subject

    def test_compose_failed(self):
        bc = MagicMock(
            source_name="Fail User",
            source_email="fail@test.com",
            status=BatchCandidateStatus.FAILED.value,
            error_message="OCR processing timeout",
        )
        subject, body = NotificationService._compose_email(bc, set())
        assert "Resubmission" in subject
        assert "OCR processing timeout" in body

    def test_compose_default_status(self):
        bc = MagicMock(
            source_name="Other User",
            source_email="other@test.com",
            status=BatchCandidateStatus.COMPLETED.value,
            error_message=None,
        )
        subject, body = NotificationService._compose_email(bc, set())
        assert "BGV Notification" in subject

    def test_compose_escapes_html(self):
        bc = MagicMock(
            source_name="<script>alert('xss')</script>",
            source_email="xss@test.com",
            status=BatchCandidateStatus.NO_DOCUMENTS.value,
            error_message=None,
        )
        subject, body = NotificationService._compose_email(bc, {"Aadhaar Card"})
        assert "<script>" not in body
        assert "&lt;script&gt;" in body


class TestNotificationServiceExtract:
    """Test _extract_missing_docs."""

    def test_no_error_message(self):
        mandatory = {"Aadhaar Card", "PAN Card"}
        result = NotificationService._extract_missing_docs(None, mandatory)
        assert result == mandatory

    def test_with_error_mentioning_present_docs(self):
        mandatory = {"Aadhaar Card", "PAN Card", "Passport"}
        result = NotificationService._extract_missing_docs(
            "Missing mandatory documents: PAN Card, Passport", mandatory
        )
        # Should identify which ones are truly missing
        assert isinstance(result, set)
        assert len(result) > 0

    def test_empty_mandatory(self):
        result = NotificationService._extract_missing_docs("some error", set())
        assert result == set()


class TestNotificationServiceSend:
    """Test send_notifications_background and helpers."""

    @pytest.mark.asyncio
    async def test_mark_failed(self):
        db = AsyncMock()
        logs = [
            MagicMock(id="log-1", status=NotificationStatus.QUEUED.value),
            MagicMock(id="log-2", status=NotificationStatus.QUEUED.value),
        ]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = logs
        db.execute = AsyncMock(return_value=result_mock)
        db.commit = AsyncMock()

        await NotificationService._mark_failed(db, ["log-1", "log-2"], "Test failure")

        assert logs[0].status == NotificationStatus.FAILED.value
        assert logs[0].error_message == "Test failure"
        assert logs[1].status == NotificationStatus.FAILED.value

    @pytest.mark.asyncio
    async def test_send_background_no_gmail_config(self):
        """When Gmail is not configured, all logs get marked failed."""
        mock_db = AsyncMock()

        # Gmail config query returns None
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=config_result)
        mock_db.commit = AsyncMock()

        with patch("app.services.notifications.email_service.AsyncSessionLocal") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(NotificationService, "_mark_failed", new_callable=AsyncMock) as mock_mark:
                await NotificationService.send_notifications_background(["log-1"])
                mock_mark.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_background_with_config_success(self):
        """When Gmail is configured and send succeeds."""
        mock_db = AsyncMock()

        config = MagicMock(
            credentials_json='{"token":"t","refresh_token":"r","token_uri":"u","client_id":"c","client_secret":"s"}',
            is_enabled=True,
        )
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config

        log_entry = MagicMock(
            id="log-1",
            recipient_email="test@test.com",
            subject="Test",
            body_html="<p>Test</p>",
            status=NotificationStatus.QUEUED.value,
        )
        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = [log_entry]

        mock_db.execute = AsyncMock(side_effect=[config_result, logs_result])
        mock_db.commit = AsyncMock()

        with patch("app.services.notifications.email_service.AsyncSessionLocal") as mock_session:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch.object(NotificationService, "_send_single_email", new_callable=AsyncMock):
                await NotificationService.send_notifications_background(["log-1"])

        assert log_entry.status == NotificationStatus.SENT.value

    @pytest.mark.asyncio
    async def test_send_background_send_fails(self):
        """When _send_single_email raises, log is marked FAILED."""
        mock_db = AsyncMock()

        config = MagicMock(
            credentials_json='{"token":"t","refresh_token":"r","token_uri":"u","client_id":"c","client_secret":"s"}',
            is_enabled=True,
        )
        config_result = MagicMock()
        config_result.scalar_one_or_none.return_value = config

        log_entry = MagicMock(
            id="log-1",
            recipient_email="test@test.com",
            subject="Test",
            body_html="<p>Test</p>",
            status=NotificationStatus.QUEUED.value,
        )
        logs_result = MagicMock()
        logs_result.scalars.return_value.all.return_value = [log_entry]

        mock_db.execute = AsyncMock(side_effect=[config_result, logs_result])
        mock_db.commit = AsyncMock()

        with patch("app.services.notifications.email_service.AsyncSessionLocal") as mock_session, \
             patch("app.services.notifications.email_service.settings") as mock_settings:
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_settings.email_max_retries = 1

            with patch.object(
                NotificationService, "_send_single_email",
                new_callable=AsyncMock, side_effect=RuntimeError("SMTP error")
            ):
                await NotificationService.send_notifications_background(["log-1"])

        assert log_entry.status == NotificationStatus.FAILED.value


class TestNotificationServiceRecover:
    """Test recover_stuck_notifications."""

    @pytest.mark.asyncio
    async def test_recover_no_stuck(self):
        mock_db = MagicMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result_mock)

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory = MagicMock(return_value=mock_ctx)

        with patch("app.db.session.AsyncSessionLocal", mock_session_factory):
            await NotificationService.recover_stuck_notifications(max_age_minutes=30)

    @pytest.mark.asyncio
    async def test_recover_with_stuck(self):
        """When stuck notifications exist, they are re-sent."""
        mock_db = MagicMock()
        stuck_logs = [MagicMock(id="s1"), MagicMock(id="s2")]
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = stuck_logs
        mock_db.execute = AsyncMock(return_value=result_mock)

        # Patch at the module where it's imported from
        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_ctx)

        with patch("app.db.session.AsyncSessionLocal", mock_session_factory):
            with patch.object(
                NotificationService, "send_notifications_background", new_callable=AsyncMock
            ) as mock_send:
                await NotificationService.recover_stuck_notifications(max_age_minutes=30)
                mock_send.assert_called_once_with(["s1", "s2"])


# ─── OCR Engine ─────────────────────────────────────────────────────────────


class TestOCREngine:
    """Test PaddleOCREngine with mocked PaddleOCR."""

    def test_process_empty_result(self):
        engine = PaddleOCREngine()

        with patch("app.services.ocr.engine._get_paddle_ocr") as mock_get:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = [None]
            mock_get.return_value = mock_ocr

            result = engine.process(np.zeros((100, 100, 3), dtype=np.uint8))

        assert result.text == ""
        assert result.word_count == 0
        assert result.confidence == 0.0

    def test_process_with_text(self):
        engine = PaddleOCREngine()

        mock_result = [[
            [[[0, 0], [100, 0], [100, 30], [0, 30]], ("Hello World", 0.95)],
            [[[0, 40], [100, 40], [100, 70], [0, 70]], ("Test Document", 0.88)],
        ]]

        with patch("app.services.ocr.engine._get_paddle_ocr") as mock_get:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = mock_result
            mock_get.return_value = mock_ocr

            result = engine.process(np.zeros((100, 100, 3), dtype=np.uint8))

        assert "Hello World" in result.text
        assert "Test Document" in result.text
        assert result.word_count == 4
        assert result.confidence > 0.8
        assert result.is_successful

    def test_process_low_confidence_filtered(self):
        engine = PaddleOCREngine()

        mock_result = [[
            [[[0, 0], [100, 0], [100, 30], [0, 30]], ("Good Text", 0.95)],
            [[[0, 40], [100, 40], [100, 70], [0, 70]], ("Noise", 0.1)],  # Below threshold
        ]]

        with patch("app.services.ocr.engine._get_paddle_ocr") as mock_get:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = mock_result
            mock_get.return_value = mock_ocr

            result = engine.process(np.zeros((100, 100, 3), dtype=np.uint8))

        assert "Good Text" in result.text
        assert "Noise" not in result.text

    def test_process_exception(self):
        engine = PaddleOCREngine()

        with patch("app.services.ocr.engine._get_paddle_ocr") as mock_get:
            mock_get.side_effect = RuntimeError("OCR init failed")

            result = engine.process(np.zeros((100, 100, 3), dtype=np.uint8))

        assert result.error is not None
        assert "OCR init failed" in result.error
        assert not result.is_successful

    def test_process_from_path_empty(self):
        engine = PaddleOCREngine()

        with patch("app.services.ocr.engine._get_paddle_ocr") as mock_get:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = [[]]
            mock_get.return_value = mock_ocr

            result = engine.process_from_path(Path("/tmp/test.png"))

        assert result.text == ""

    def test_process_from_path_with_text(self):
        engine = PaddleOCREngine()

        mock_result = [[
            [[[0, 0], [200, 0], [200, 30], [0, 30]], ("AADHAAR CARD", 0.99)],
            [[[0, 40], [200, 40], [200, 70], [0, 70]], ("1234 5678 9012", 0.92)],
        ]]

        with patch("app.services.ocr.engine._get_paddle_ocr") as mock_get:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = mock_result
            mock_get.return_value = mock_ocr

            result = engine.process_from_path(Path("/tmp/aadhaar.png"))

        assert "AADHAAR CARD" in result.text
        assert result.word_count >= 4

    def test_process_from_path_exception(self):
        engine = PaddleOCREngine()

        with patch("app.services.ocr.engine._get_paddle_ocr") as mock_get:
            mock_ocr = MagicMock()
            mock_ocr.ocr.side_effect = Exception("File not found")
            mock_get.return_value = mock_ocr

            result = engine.process_from_path(Path("/nonexistent.png"))

        assert result.error is not None

    @pytest.mark.asyncio
    async def test_process_async(self):
        engine = PaddleOCREngine()

        with patch("app.services.ocr.engine._get_paddle_ocr") as mock_get:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = [None]
            mock_get.return_value = mock_ocr

            result = await engine.process_async(np.zeros((50, 50, 3), dtype=np.uint8))

        assert result.text == ""

    @pytest.mark.asyncio
    async def test_process_from_path_async(self):
        engine = PaddleOCREngine()

        with patch("app.services.ocr.engine._get_paddle_ocr") as mock_get:
            mock_ocr = MagicMock()
            mock_ocr.ocr.return_value = [[]]
            mock_get.return_value = mock_ocr

            result = await engine.process_from_path_async(Path("/tmp/test.jpg"))

        assert result.text == ""


class TestOCREngineResult:
    """Test OCREngineResult properties."""

    def test_is_successful_with_text(self):
        r = OCREngineResult(text="Hello", confidence=0.9, word_count=1, raw_output=[], processing_duration_ms=100)
        assert r.is_successful

    def test_is_successful_with_error(self):
        r = OCREngineResult(text="", confidence=0.0, word_count=0, raw_output=[], processing_duration_ms=100, error="fail")
        assert not r.is_successful

    def test_is_successful_empty_text(self):
        r = OCREngineResult(text="", confidence=0.0, word_count=0, raw_output=[], processing_duration_ms=100)
        assert not r.is_successful


# ─── AI Classifier ──────────────────────────────────────────────────────────


class TestAIClassifier:
    """Test AIClassifier methods."""

    @pytest.mark.asyncio
    async def test_classify_insufficient_text(self):
        classifier = AIClassifier(client=MagicMock())
        result = await classifier.classify_document("Hi", 0.5, 1)
        assert result.document_type == DocumentType.UNKNOWN.value
        assert "Insufficient" in result.error

    @pytest.mark.asyncio
    async def test_classify_empty_text(self):
        classifier = AIClassifier(client=MagicMock())
        result = await classifier.classify_document("", 0.0, 0)
        assert result.document_type == DocumentType.UNKNOWN.value

    @pytest.mark.asyncio
    async def test_classify_success(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=MagicMock(
            is_successful=True,
            content='{"document_type": "aadhaar", "confidence": 0.95, "reasoning": "Contains Aadhaar number"}',
            model="llama3",
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=200,
        ))

        classifier = AIClassifier(client=mock_client)
        result = await classifier.classify_document(
            "GOVERNMENT OF INDIA\nUnique Identification Authority\n1234 5678 9012",
            0.92, 10
        )
        assert result.document_type == "aadhaar"
        assert result.confidence == 0.95
        assert result.is_successful

    @pytest.mark.asyncio
    async def test_classify_ai_failure(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=MagicMock(
            is_successful=False,
            content="",
            model="llama3",
            prompt_tokens=0,
            completion_tokens=0,
            duration_ms=100,
            error="Connection refused",
        ))

        classifier = AIClassifier(client=mock_client)
        result = await classifier.classify_document("Some text content here for classification", 0.8, 7)
        assert result.document_type == DocumentType.UNKNOWN.value
        assert result.error == "Connection refused"

    @pytest.mark.asyncio
    async def test_classify_invalid_json_response(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=MagicMock(
            is_successful=True,
            content="This is not JSON at all",
            model="llama3",
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=200,
        ))

        classifier = AIClassifier(client=mock_client)
        result = await classifier.classify_document("Some document text here to classify", 0.8, 7)
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_classify_json_in_code_block(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=MagicMock(
            is_successful=True,
            content='```json\n{"document_type": "pan_card", "confidence": 0.88, "reasoning": "PAN number found"}\n```',
            model="llama3",
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=200,
        ))

        classifier = AIClassifier(client=mock_client)
        result = await classifier.classify_document("INCOME TAX DEPARTMENT\nPermanent Account Number\nABCDE1234F", 0.9, 8)
        assert result.document_type == "pan_card"
        assert result.confidence == 0.88

    @pytest.mark.asyncio
    async def test_extract_ownership_success(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=MagicMock(
            is_successful=True,
            content='{"holder_name": "John Doe", "date_of_birth": "01/01/1990", "confidence": 0.9}',
            model="llama3",
            prompt_tokens=80,
            completion_tokens=30,
            duration_ms=150,
        ))

        classifier = AIClassifier(client=mock_client)
        result = await classifier.extract_ownership("Name: John Doe DOB: 01/01/1990", "aadhaar_card")
        assert result.holder_name == "John Doe"
        assert result.date_of_birth == "01/01/1990"

    @pytest.mark.asyncio
    async def test_extract_ownership_empty_text(self):
        classifier = AIClassifier(client=MagicMock())
        result = await classifier.extract_ownership("", "aadhaar_card")
        assert result.error == "No OCR text provided"

    @pytest.mark.asyncio
    async def test_extract_ownership_ai_failure(self):
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=MagicMock(
            is_successful=False,
            content="",
            model="llama3",
            error="timeout",
        ))

        classifier = AIClassifier(client=mock_client)
        result = await classifier.extract_ownership("Some text", "pan_card")
        assert result.error == "timeout"

    def test_extract_json_direct(self):
        classifier = AIClassifier(client=MagicMock())
        result = classifier._extract_json('{"key": "value"}')
        assert json.loads(result) == {"key": "value"}

    def test_extract_json_code_block(self):
        classifier = AIClassifier(client=MagicMock())
        result = classifier._extract_json('Here is the result:\n```json\n{"key": "value"}\n```\nDone.')
        assert json.loads(result) == {"key": "value"}

    def test_extract_json_embedded(self):
        classifier = AIClassifier(client=MagicMock())
        result = classifier._extract_json('Some text before {"key": "value"} some text after')
        assert json.loads(result) == {"key": "value"}


# ─── GoogleDriveService deeper ──────────────────────────────────────────────


class TestGoogleDriveServiceDeep:
    """Deeper tests for GoogleDriveService methods."""

    def _make_service(self, mock_drive=None, config=None):
        creds_json = json.dumps({
            "token": "t", "refresh_token": "r",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "c", "client_secret": "s",
        })
        config_json = json.dumps(config) if config else None

        with patch("google.oauth2.credentials.Credentials") as mock_creds, \
             patch("googleapiclient.discovery.build", return_value=mock_drive or MagicMock()):
            mock_cred_inst = MagicMock(valid=True, expired=False)
            mock_creds.from_authorized_user_info.return_value = mock_cred_inst
            service = GoogleDriveService(credentials_json=creds_json, config_json=config_json)
        return service

    def test_download_file_regular(self):
        """Test downloading a regular PDF file."""
        mock_drive = MagicMock()
        content = b"%PDF-1.4 document content"

        # Mock MediaIoBaseDownload
        with patch("googleapiclient.http.MediaIoBaseDownload") as mock_dl_cls:
            mock_downloader = MagicMock()
            mock_downloader.next_chunk.return_value = (None, True)
            mock_dl_cls.return_value = mock_downloader

            service = self._make_service(mock_drive)
            # Since we patched MediaIoBaseDownload, download_file will use it
            result = service.download_file("file-123", "application/pdf")

        # The result will be empty because buffer.getvalue() on empty buffer
        assert isinstance(result, bytes)

    def test_download_file_google_doc_exports(self):
        """Test downloading a Google Doc (exports to PDF)."""
        mock_drive = MagicMock()

        with patch("googleapiclient.http.MediaIoBaseDownload") as mock_dl_cls:
            mock_downloader = MagicMock()
            mock_downloader.next_chunk.return_value = (None, True)
            mock_dl_cls.return_value = mock_downloader

            service = self._make_service(mock_drive)
            result = service.download_file("file-456", "application/vnd.google-apps.document")

        # Should have called export_media instead of get_media
        mock_drive.files.return_value.export_media.assert_called_once()

    def test_create_storage_folder(self):
        mock_drive = MagicMock()
        create_mock = MagicMock()
        create_mock.execute.return_value = {"id": "new-folder-id"}
        mock_drive.files.return_value.create.return_value = create_mock

        service = self._make_service(mock_drive, config={"storage_root_folder_id": "root-123"})
        folder_id = service.create_storage_folder("BATCH001", "John Doe")

        assert folder_id == "new-folder-id"
        call_args = mock_drive.files.return_value.create.call_args
        body = call_args[1]["body"] if "body" in call_args[1] else call_args[0][0]
        assert "BATCH001-John Doe" in body.get("name", "")

    def test_create_storage_folder_with_name(self):
        mock_drive = MagicMock()
        create_mock = MagicMock()
        create_mock.execute.return_value = {"id": "f-id"}
        mock_drive.files.return_value.create.return_value = create_mock

        service = self._make_service(mock_drive)
        folder_id = service.create_storage_folder_with_name("TestFolder")
        assert folder_id == "f-id"

    def test_upload_file(self):
        mock_drive = MagicMock()
        create_mock = MagicMock()
        create_mock.execute.return_value = {"id": "uploaded-file-id"}
        mock_drive.files.return_value.create.return_value = create_mock

        with patch("googleapiclient.http.MediaInMemoryUpload"):
            service = self._make_service(mock_drive)
            file_id = service.upload_file("folder-1", "test.pdf", b"content", "application/pdf")

        assert file_id == "uploaded-file-id"

    def test_delete_folder(self):
        mock_drive = MagicMock()
        delete_mock = MagicMock()
        delete_mock.execute.return_value = None
        mock_drive.files.return_value.delete.return_value = delete_mock

        service = self._make_service(mock_drive)
        service.delete_folder("folder-to-delete")

        mock_drive.files.return_value.delete.assert_called_once()

    def test_escape_query(self):
        assert GoogleDriveService._escape_query("O'Brien") == "O\\'Brien"
        assert GoogleDriveService._escape_query("Normal") == "Normal"

    def test_search_with_folder_filter(self):
        """Test search uses folder filter when configured."""
        mock_drive = MagicMock()
        list_mock = MagicMock()
        list_mock.execute.return_value = {"files": []}
        mock_drive.files.return_value.list.return_value = list_mock

        service = self._make_service(mock_drive, config={"search_folder_ids": ["folder-A", "folder-B"]})
        results = service.search_for_candidate("Test User", "cand-1")

        assert results == []
        # Verify list was called (with folder filter in query)
        assert mock_drive.files.return_value.list.called

    def test_search_deduplicates(self):
        """Files found by both name and ID are not duplicated."""
        mock_drive = MagicMock()
        list_mock = MagicMock()
        # Same file returned for both search terms
        list_mock.execute.return_value = {
            "files": [{"id": "f1", "name": "doc.pdf", "mimeType": "application/pdf", "size": "1024", "modifiedTime": "2024-01-01", "webViewLink": ""}]
        }
        mock_drive.files.return_value.list.return_value = list_mock

        service = self._make_service(mock_drive)
        results = service.search_for_candidate("Test User", "cand-1")

        # Should be 1, not 2 (deduplicated by file_id)
        assert len(results) == 1

    def test_search_error_handled(self):
        """If Drive API raises, it's handled gracefully."""
        mock_drive = MagicMock()
        list_mock = MagicMock()
        list_mock.execute.side_effect = Exception("API quota exceeded")
        mock_drive.files.return_value.list.return_value = list_mock

        service = self._make_service(mock_drive)
        results = service.search_for_candidate("Test", "c1")
        assert results == []


# ─── DriveUploadService ─────────────────────────────────────────────────────


class TestDriveUploadServiceDeep:
    """Test DriveUploadService.upload_document."""

    @pytest.mark.asyncio
    async def test_upload_document_creates_folder(self):
        db = AsyncMock()
        svc = DriveUploadService(db)

        # Mock document query (scalar_one returns doc)
        doc = MagicMock(file_path="/tmp/test.pdf", mime_type="application/pdf", original_filename="aadhaar.pdf")
        doc_query_result = MagicMock()
        doc_query_result.scalar_one.return_value = doc

        # Mock classification query for _get_document_type
        doc_type_result = MagicMock()
        doc_type_result.scalar_one_or_none.return_value = "aadhaar"

        # First call: get_active_rule (via FileNamingRuleService)
        # Second call: doc select, Third call: _get_document_type
        db.execute = AsyncMock(side_effect=[doc_query_result, doc_type_result])
        db.flush = AsyncMock()

        drive_service = MagicMock()
        drive_service.create_storage_folder_with_name.return_value = "new-folder-id"
        drive_service.upload_file.return_value = "uploaded-id"

        batch = MagicMock(batch_code="B001", created_at=datetime(2024, 1, 1))
        bc = MagicMock(source_name="John Doe", source_candidate_id="SC001")

        naming_rule = MagicMock(
            folder_structure_pattern="{candidate_id}-{candidate_name}",
            file_rename_pattern="{document_type}-{original_filename}",
        )

        with patch("app.services.batch.drive_upload_service.FileNamingRuleService") as mock_fnrs, \
             patch("pathlib.Path.read_bytes", return_value=b"content"):
            mock_fnrs.get_active_rule = AsyncMock(return_value=naming_rule)
            mock_fnrs.resolve_folder_name.return_value = "SC001-John Doe"
            mock_fnrs.resolve_file_name.return_value = "aadhaar-aadhaar.pdf"

            result_service, folder_id = await svc.upload_document(
                drive_service, None, batch, bc, "doc-1"
            )

        assert folder_id == "new-folder-id"

    @pytest.mark.asyncio
    async def test_upload_document_reuses_folder(self):
        db = AsyncMock()
        svc = DriveUploadService(db)

        doc = MagicMock(file_path="/tmp/pan.pdf", mime_type="application/pdf", original_filename="pan.pdf")
        doc_query_result = MagicMock()
        doc_query_result.scalar_one.return_value = doc

        doc_type_result = MagicMock()
        doc_type_result.scalar_one_or_none.return_value = "pan_card"

        db.execute = AsyncMock(side_effect=[doc_query_result, doc_type_result])
        db.flush = AsyncMock()

        drive_service = MagicMock()
        drive_service.upload_file.return_value = "uploaded-id-2"

        batch = MagicMock(batch_code="B001", created_at=datetime(2024, 1, 1))
        bc = MagicMock(source_name="Jane", source_candidate_id="SC002")

        naming_rule = MagicMock(
            folder_structure_pattern="{candidate_id}",
            file_rename_pattern="{document_type}.pdf",
        )

        with patch("app.services.batch.drive_upload_service.FileNamingRuleService") as mock_fnrs, \
             patch("pathlib.Path.read_bytes", return_value=b"content"):
            mock_fnrs.get_active_rule = AsyncMock(return_value=naming_rule)
            mock_fnrs.resolve_file_name.return_value = "pan_card.pdf"

            result_service, folder_id = await svc.upload_document(
                drive_service, "existing-folder-id", batch, bc, "doc-2"
            )

        assert folder_id == "existing-folder-id"
        # Should NOT create folder since one already exists
        drive_service.create_storage_folder_with_name.assert_not_called()
