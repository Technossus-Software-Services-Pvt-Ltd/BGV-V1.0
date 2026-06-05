"""Tests for email notification service."""

import re
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notifications.email_service import NotificationService
from app.models.enums import BatchCandidateStatus


class TestComposeEmail:
    def _make_candidate(self, status, name="John Doe", email="john@example.com", error_message=None):
        c = MagicMock()
        c.id = str(uuid.uuid4())
        c.source_name = name
        c.source_email = email
        c.status = status
        c.error_message = error_message
        return c

    def test_awaiting_required_documents(self):
        candidate = self._make_candidate(BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value)
        mandatory = {"Aadhaar Card", "PAN Card"}

        subject, body = NotificationService._compose_email(candidate, mandatory)

        assert "Action Required: Submit Required Documents" in subject
        assert "John Doe" in subject
        assert "Aadhaar Card" in body
        assert "PAN Card" in body
        assert "mandatory documents" in body.lower()

    def test_partial_status(self):
        candidate = self._make_candidate(
            BatchCandidateStatus.PARTIAL.value,
            error_message="Missing: PAN Card"
        )
        mandatory = {"Aadhaar Card", "PAN Card"}

        subject, body = NotificationService._compose_email(candidate, mandatory)

        assert "Missing Documents" in subject
        assert "John Doe" in subject

    def test_no_documents_status(self):
        candidate = self._make_candidate(BatchCandidateStatus.NO_DOCUMENTS.value)
        mandatory = {"Aadhaar Card", "PAN Card"}

        subject, body = NotificationService._compose_email(candidate, mandatory)

        assert "No Documents Received" in subject
        assert "Aadhaar Card" in body
        assert "PAN Card" in body

    def test_failed_status(self):
        candidate = self._make_candidate(
            BatchCandidateStatus.FAILED.value,
            error_message="OCR processing timeout"
        )
        mandatory = {"Aadhaar Card"}

        subject, body = NotificationService._compose_email(candidate, mandatory)

        assert "Resubmission" in subject
        assert "OCR processing timeout" in body

    def test_default_status(self):
        candidate = self._make_candidate("some_other_status")
        mandatory = set()

        subject, body = NotificationService._compose_email(candidate, mandatory)

        assert "BGV Notification" in subject
        assert "check your verification status" in body

    def test_html_escaping(self):
        candidate = self._make_candidate(
            BatchCandidateStatus.FAILED.value,
            name="<script>alert('xss')</script>",
            error_message="<b>bad</b>"
        )
        mandatory = set()

        subject, body = NotificationService._compose_email(candidate, mandatory)

        assert "<script>" not in body
        assert "&lt;b&gt;" in body


class TestExtractMissingDocs:
    def test_none_error_returns_all_mandatory(self):
        mandatory = {"Aadhaar Card", "PAN Card", "Passport"}
        result = NotificationService._extract_missing_docs(None, mandatory)
        assert result == mandatory

    def test_empty_error_returns_all_mandatory(self):
        mandatory = {"Aadhaar Card", "PAN Card"}
        result = NotificationService._extract_missing_docs("", mandatory)
        assert result == mandatory

    def test_mentioned_doc_excluded(self):
        mandatory = {"Aadhaar Card", "PAN Card", "Passport"}
        # If "aadhaar card" is mentioned in error message, it's excluded from missing
        result = NotificationService._extract_missing_docs(
            "Present documents: Aadhaar Card verified", mandatory
        )
        # Aadhaar Card is mentioned so excluded from missing
        assert "Aadhaar Card" not in result
        assert "PAN Card" in result
        assert "Passport" in result

    def test_no_match_returns_all(self):
        mandatory = {"Aadhaar Card", "PAN Card"}
        result = NotificationService._extract_missing_docs(
            "Some random error about timeout", mandatory
        )
        assert result == mandatory


class TestQueueNotifications:
    @pytest.mark.asyncio
    async def test_queue_empty_candidates(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute.return_value = result_mock

        result = await NotificationService.queue_notifications(db, [])
        assert result == []

    @pytest.mark.asyncio
    async def test_queue_candidates_without_email(self):
        db = AsyncMock()
        candidate = MagicMock()
        candidate.source_email = None
        candidate.id = "c1"
        candidate.source_name = "Test"
        candidate.status = BatchCandidateStatus.PARTIAL.value

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [candidate]

        # First call returns candidates, second returns rules
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = []
        db.execute.side_effect = [result_mock, rules_result]

        result = await NotificationService.queue_notifications(db, ["c1"])
        assert result == []

    @pytest.mark.asyncio
    async def test_queue_creates_notification_log(self):
        db = AsyncMock()
        candidate = MagicMock()
        candidate.source_email = "test@example.com"
        candidate.id = "c1"
        candidate.source_name = "Test User"
        candidate.status = BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value
        candidate.error_message = None

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [candidate]

        rule = MagicMock()
        rule.document_name = "Aadhaar Card"
        rule.is_active = True
        rule.is_mandatory = True
        rules_result = MagicMock()
        rules_result.scalars.return_value.all.return_value = [rule]

        db.execute.side_effect = [result_mock, rules_result]

        result = await NotificationService.queue_notifications(db, ["c1"])
        assert len(result) == 1
        db.add.assert_called_once()
        db.commit.assert_called_once()
