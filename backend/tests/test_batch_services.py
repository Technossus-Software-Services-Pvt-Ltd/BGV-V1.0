"""Tests for Phase 3: BatchOrchestrator split into services.

Verifies that:
1. Each extracted service can be instantiated independently
2. ChecklistMatcher pure logic works correctly
3. BatchOrchestrator creates all sub-services
4. BatchStatusService emits via ws_hub
5. Public API (process_batch, retry_candidate) remains unchanged
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.batch.checklist_matcher import ChecklistMatcher
from app.services.batch.discovery_service import DiscoveryService
from app.services.batch.ingest_service import DocumentIngestService
from app.services.batch.drive_upload_service import DriveUploadService
from app.services.batch.status_service import BatchStatusService
from app.services.batch.orchestrator import BatchOrchestrator


class TestChecklistMatcher:
    """Verify ChecklistMatcher pure logic."""

    def test_normalize_doc_type_basic(self):
        assert ChecklistMatcher.normalize_doc_type("PAN Card") == "pancard"
        assert ChecklistMatcher.normalize_doc_type("pan_card") == "pancard"
        assert ChecklistMatcher.normalize_doc_type("  Aadhaar Card ") == "aadhaarcard"
        assert ChecklistMatcher.normalize_doc_type("driving-license") == "drivinglicense"

    def test_normalize_strips_all_separators(self):
        assert ChecklistMatcher.normalize_doc_type("a_b-c d") == "abcd"

    def test_doc_type_matches_checklist_exact(self):
        mandatory = {"pancard", "aadhaarcard"}
        assert ChecklistMatcher.doc_type_matches_checklist("pancard", mandatory) is True

    def test_doc_type_matches_checklist_substring(self):
        mandatory = {"aadhaarcard"}
        assert ChecklistMatcher.doc_type_matches_checklist("aadhaar", mandatory) is True

    def test_doc_type_matches_checklist_reverse_substring(self):
        mandatory = {"pan"}
        assert ChecklistMatcher.doc_type_matches_checklist("pancard", mandatory) is True

    def test_doc_type_no_match(self):
        mandatory = {"pancard", "aadhaarcard"}
        assert ChecklistMatcher.doc_type_matches_checklist("passport", mandatory) is False

    def test_get_matched_mandatory_all_matched(self):
        uploaded = {"pancard", "aadhaarcard"}
        mandatory = {"pancard", "aadhaarcard"}
        matched, missing = ChecklistMatcher.get_matched_mandatory(uploaded, mandatory)
        assert matched == {"pancard", "aadhaarcard"}
        assert missing == set()

    def test_get_matched_mandatory_partial(self):
        uploaded = {"pancard"}
        mandatory = {"pancard", "aadhaarcard"}
        matched, missing = ChecklistMatcher.get_matched_mandatory(uploaded, mandatory)
        assert matched == {"pancard"}
        assert missing == {"aadhaarcard"}

    def test_get_matched_mandatory_none(self):
        uploaded = {"passport"}
        mandatory = {"pancard", "aadhaarcard"}
        matched, missing = ChecklistMatcher.get_matched_mandatory(uploaded, mandatory)
        assert matched == set()
        assert missing == {"pancard", "aadhaarcard"}


class TestDiscoveryService:
    """Verify DiscoveryService instantiation."""

    def test_instantiation(self):
        mock_db = MagicMock()
        service = DiscoveryService(mock_db)
        assert service.db is mock_db


class TestDocumentIngestService:
    """Verify DocumentIngestService instantiation."""

    def test_instantiation(self):
        mock_db = MagicMock()
        mock_audit = MagicMock()
        service = DocumentIngestService(mock_db, mock_audit)
        assert service.db is mock_db
        assert service.audit is mock_audit


class TestDriveUploadService:
    """Verify DriveUploadService instantiation."""

    def test_instantiation(self):
        mock_db = MagicMock()
        service = DriveUploadService(mock_db)
        assert service.db is mock_db


class TestBatchStatusService:
    """Verify BatchStatusService instantiation and ws_hub injection."""

    def test_instantiation_with_default_hub(self):
        mock_db = MagicMock()
        service = BatchStatusService(mock_db)
        assert service.db is mock_db
        assert service._ws_hub is not None

    def test_instantiation_with_injected_hub(self):
        mock_db = MagicMock()
        mock_hub = MagicMock()
        service = BatchStatusService(mock_db, ws_hub=mock_hub)
        assert service._ws_hub is mock_hub

    @pytest.mark.asyncio
    async def test_log_creates_entry_and_emits(self):
        mock_db = MagicMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()
        mock_hub = MagicMock()
        mock_hub.emit_processing_log = AsyncMock()

        service = BatchStatusService(mock_db, ws_hub=mock_hub)
        await service.log("batch-1", "cand-1", "info", "test", "Hello")

        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()
        mock_hub.emit_processing_log.assert_called_once()


class TestBatchOrchestratorStructure:
    """Verify the refactored BatchOrchestrator has correct service structure."""

    def test_orchestrator_creates_all_services(self):
        mock_db = MagicMock()
        orchestrator = BatchOrchestrator(mock_db)
        assert isinstance(orchestrator._discovery, DiscoveryService)
        assert isinstance(orchestrator._ingest, DocumentIngestService)
        assert isinstance(orchestrator._drive_upload, DriveUploadService)
        assert isinstance(orchestrator._status, BatchStatusService)

    def test_orchestrator_injects_ws_hub(self):
        mock_db = MagicMock()
        mock_hub = MagicMock()
        orchestrator = BatchOrchestrator(mock_db, ws_hub=mock_hub)
        assert orchestrator._status._ws_hub is mock_hub

    def test_orchestrator_accepts_pipeline_factory(self):
        mock_db = MagicMock()
        factory = MagicMock()
        orchestrator = BatchOrchestrator(mock_db, pipeline_factory=factory)
        assert orchestrator._pipeline_factory is factory

    def test_public_api_unchanged(self):
        mock_db = MagicMock()
        orchestrator = BatchOrchestrator(mock_db)
        assert hasattr(orchestrator, "process_batch")
        assert hasattr(orchestrator, "retry_candidate")
        assert callable(orchestrator.process_batch)
        assert callable(orchestrator.retry_candidate)

    @pytest.mark.asyncio
    async def test_process_batch_handles_missing_batch(self):
        """If batch doesn't exist, process_batch returns gracefully."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        orchestrator = BatchOrchestrator(mock_db)
        await orchestrator.process_batch("nonexistent-id")
        # Should not raise
