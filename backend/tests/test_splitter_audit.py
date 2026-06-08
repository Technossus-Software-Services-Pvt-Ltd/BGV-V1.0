"""Tests for DocumentSplitter, AuditService, and main app internals."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.processing.splitter import DocumentSplitter, PageClassification, DocumentGroup
from app.services.audit.logger import AuditService, mask_pii, PII_PATTERNS
from app.models.enums import AuditAction, LogLevel


class TestDocumentSplitterGroupPages:
    def test_empty_classifications(self):
        splitter = DocumentSplitter()
        result = splitter.group_pages_by_type([])
        assert result == []

    def test_single_page(self):
        splitter = DocumentSplitter()
        result = splitter.group_pages_by_type([
            PageClassification(page_number=1, document_type="aadhaar", confidence=0.95),
        ])
        assert len(result) == 1
        assert result[0].document_type == "aadhaar"
        assert result[0].pages == [1]
        assert result[0].confidence == 0.95

    def test_consecutive_same_type(self):
        splitter = DocumentSplitter()
        result = splitter.group_pages_by_type([
            PageClassification(page_number=1, document_type="aadhaar", confidence=0.9),
            PageClassification(page_number=2, document_type="aadhaar", confidence=0.85),
            PageClassification(page_number=3, document_type="aadhaar", confidence=0.88),
        ])
        assert len(result) == 1
        assert result[0].pages == [1, 2, 3]
        assert result[0].confidence == pytest.approx((0.9 + 0.85 + 0.88) / 3)

    def test_different_types_create_separate_groups(self):
        splitter = DocumentSplitter()
        result = splitter.group_pages_by_type([
            PageClassification(page_number=1, document_type="aadhaar", confidence=0.9),
            PageClassification(page_number=2, document_type="pan", confidence=0.85),
            PageClassification(page_number=3, document_type="pan", confidence=0.88),
        ])
        assert len(result) == 2
        assert result[0].document_type == "aadhaar"
        assert result[0].pages == [1]
        assert result[1].document_type == "pan"
        assert result[1].pages == [2, 3]

    def test_alternating_types(self):
        splitter = DocumentSplitter()
        result = splitter.group_pages_by_type([
            PageClassification(page_number=1, document_type="aadhaar", confidence=0.9),
            PageClassification(page_number=2, document_type="pan", confidence=0.85),
            PageClassification(page_number=3, document_type="aadhaar", confidence=0.88),
        ])
        assert len(result) == 3

    def test_detect_mixed_documents_true(self):
        splitter = DocumentSplitter()
        groups = [
            DocumentGroup(document_type="aadhaar", pages=[1], confidence=0.9),
            DocumentGroup(document_type="pan", pages=[2], confidence=0.85),
        ]
        assert splitter.detect_mixed_documents(groups) is True

    def test_detect_mixed_documents_false_single_type(self):
        splitter = DocumentSplitter()
        groups = [
            DocumentGroup(document_type="aadhaar", pages=[1, 2], confidence=0.9),
        ]
        assert splitter.detect_mixed_documents(groups) is False

    def test_detect_mixed_documents_ignores_unknown(self):
        splitter = DocumentSplitter()
        groups = [
            DocumentGroup(document_type="aadhaar", pages=[1], confidence=0.9),
            DocumentGroup(document_type="unknown", pages=[2], confidence=0.5),
        ]
        assert splitter.detect_mixed_documents(groups) is False


class TestMaskPII:
    def test_masks_aadhaar(self):
        text = "Aadhaar: 1234 5678 9012"
        masked = mask_pii(text)
        assert "XXXX XXXX XXXX" in masked
        assert "1234" not in masked

    def test_masks_pan(self):
        text = "PAN: ABCDE1234F"
        masked = mask_pii(text)
        assert "XXXXX0000X" in masked
        assert "ABCDE" not in masked

    def test_masks_phone(self):
        text = "Phone: 9876543210"
        masked = mask_pii(text)
        assert "XXXXXXXXXX" in masked
        assert "9876543210" not in masked

    def test_masks_email(self):
        text = "Email: test@example.com"
        masked = mask_pii(text)
        assert "[EMAIL REDACTED]" in masked
        assert "test@example.com" not in masked

    def test_empty_string(self):
        assert mask_pii("") == ""

    def test_none_returns_none(self):
        assert mask_pii(None) is None

    def test_no_pii_unchanged(self):
        text = "This is a normal sentence."
        assert mask_pii(text) == text

    def test_multiple_pii_in_one_text(self):
        text = "Name, PAN: ABCDE1234F, Phone: 9876543210"
        masked = mask_pii(text)
        assert "ABCDE" not in masked
        assert "9876543210" not in masked


class TestAuditServiceLog:
    @pytest.mark.asyncio
    async def test_log_creates_audit_entry(self):
        db = AsyncMock()
        svc = AuditService(db)

        entry = await svc.log(
            correlation_id="corr-1",
            action=AuditAction.UPLOAD.value,
            message="File uploaded",
            document_id="doc-1",
        )

        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_masks_pii_in_message(self):
        db = AsyncMock()
        svc = AuditService(db)

        await svc.log(
            correlation_id="corr-1",
            action=AuditAction.UPLOAD.value,
            message="File for PAN ABCDE1234F uploaded",
        )

        call_args = db.add.call_args[0][0]
        assert "ABCDE1234F" not in call_args.message

    @pytest.mark.asyncio
    async def test_log_with_details(self):
        db = AsyncMock()
        svc = AuditService(db)

        await svc.log(
            correlation_id="corr-1",
            action="test",
            message="test",
            details={"key": "value"},
            duration_ms=100,
        )

        call_args = db.add.call_args[0][0]
        assert call_args.duration_ms == 100


class TestAuditServiceRecordProcessingEvent:
    @pytest.mark.asyncio
    async def test_record_creates_event(self):
        db = AsyncMock()
        svc = AuditService(db)

        await svc.record_processing_event(
            correlation_id="corr-1",
            document_id="doc-1",
            event_type="stage_start",
            stage="normalization",
            status="running",
        )

        db.add.assert_called_once()
        db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_record_with_metadata(self):
        db = AsyncMock()
        svc = AuditService(db)

        await svc.record_processing_event(
            correlation_id="corr-1",
            document_id="doc-1",
            event_type="stage_complete",
            stage="ocr",
            status="completed",
            message="OCR done",
            metadata={"pages": 3},
            duration_ms=500,
        )

        call_args = db.add.call_args[0][0]
        assert call_args.duration_ms == 500
