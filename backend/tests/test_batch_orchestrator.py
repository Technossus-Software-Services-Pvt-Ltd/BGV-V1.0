"""Tests for BatchOrchestrator, DiscoveryService, IngestService, DriveUploadService."""

from pathlib import Path
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.batch.orchestrator import BatchOrchestrator
from app.services.batch.discovery_service import DiscoveryService
from app.services.batch.ingest_service import DocumentIngestService
from app.services.batch.drive_upload_service import DriveUploadService
from app.services.batch.status_service import BatchStatusService
from app.models.enums import BatchImportStatus, BatchCandidateStatus


class TestBatchOrchestratorProcessBatch:
    @pytest.mark.asyncio
    async def test_process_batch_not_found(self):
        db = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        orch = BatchOrchestrator(db)
        await orch.process_batch("nonexistent-id")
        # No crash, just logs error

    @pytest.mark.asyncio
    async def test_process_batch_no_integrations(self):
        db = AsyncMock(spec=AsyncSession)

        batch = MagicMock()
        batch.id = "batch-1"
        batch.batch_code = "BATCH-001"
        batch.status = BatchImportStatus.UPLOADED.value
        batch.correlation_id = "corr-1"
        batch.error_message = None

        orch = BatchOrchestrator(db)
        orch._get_batch = AsyncMock(return_value=batch)
        orch._discovery = MagicMock()
        orch._discovery.get_gmail_scanner = AsyncMock(return_value=None)
        orch._discovery.get_drive_service = AsyncMock(return_value=None)
        orch._status = MagicMock()
        orch._status.log = AsyncMock()
        orch._status.emit_summary = AsyncMock()

        await orch.process_batch("batch-1")

        assert batch.status == BatchImportStatus.FAILED.value
        assert "No integrations" in batch.error_message

    @pytest.mark.asyncio
    async def test_process_batch_success_no_candidates(self):
        db = AsyncMock(spec=AsyncSession)

        batch = MagicMock()
        batch.id = "batch-1"
        batch.batch_code = "BATCH-001"
        batch.status = BatchImportStatus.UPLOADED.value
        batch.correlation_id = "corr-1"
        batch.failed_candidates = 0
        batch.processed_candidates = 0
        batch.skipped_candidates = 0

        orch = BatchOrchestrator(db)
        orch._get_batch = AsyncMock(return_value=batch)
        orch._get_batch_candidates = AsyncMock(return_value=[])
        orch._discovery = MagicMock()
        orch._discovery.get_gmail_scanner = AsyncMock(return_value=MagicMock())
        orch._discovery.get_drive_service = AsyncMock(return_value=MagicMock())
        orch._status = MagicMock()
        orch._status.log = AsyncMock()
        orch._status.emit_summary = AsyncMock()
        orch._status.update_batch_totals = AsyncMock()
        orch._cleanup_batch_local_files = AsyncMock()

        await orch.process_batch("batch-1")

        assert batch.status == BatchImportStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_process_batch_handles_exception(self):
        db = AsyncMock(spec=AsyncSession)

        batch = MagicMock()
        batch.id = "batch-1"
        batch.batch_code = "BATCH-001"
        batch.status = BatchImportStatus.UPLOADED.value
        batch.correlation_id = "corr-1"
        batch.error_message = None

        orch = BatchOrchestrator(db)
        orch._get_batch = AsyncMock(return_value=batch)
        orch._discovery = MagicMock()
        orch._discovery.get_gmail_scanner = AsyncMock(side_effect=RuntimeError("Gmail broke"))
        orch._status = MagicMock()
        orch._status.log = AsyncMock()
        orch._status.emit_summary = AsyncMock()
        orch._cleanup_batch_local_files = AsyncMock()

        await orch.process_batch("batch-1")

        assert batch.status == BatchImportStatus.FAILED.value
        assert "Gmail broke" in batch.error_message


class TestBatchOrchestratorRetryCandidate:
    @pytest.mark.asyncio
    async def test_retry_candidate_batch_not_found(self):
        db = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        orch = BatchOrchestrator(db)
        await orch.retry_candidate("bad-batch", "bad-candidate")
        # Should not crash

    @pytest.mark.asyncio
    async def test_retry_candidate_candidate_not_found(self):
        db = AsyncMock(spec=AsyncSession)
        batch = MagicMock(id="batch-1")

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        orch = BatchOrchestrator(db)
        orch._get_batch = AsyncMock(return_value=batch)

        await orch.retry_candidate("batch-1", "bad-candidate")


class TestBatchOrchestratorProcessCandidate:
    @pytest.mark.asyncio
    async def test_process_candidate_no_documents(self):
        db = AsyncMock(spec=AsyncSession)

        batch = MagicMock(id="batch-1", batch_code="B001", correlation_id="corr-1")
        bc = MagicMock(
            id="bc-1",
            source_name="John Doe",
            source_email="john@example.com",
            source_candidate_id="CAND-001",
            status=BatchCandidateStatus.PENDING.value,
            gmail_emails_found=0,
            documents_found=0,
        )

        orch = BatchOrchestrator(db)
        orch._status = MagicMock()
        orch._status.log = AsyncMock()
        orch._status.emit_candidate_status = AsyncMock()
        orch._status.emit_summary = AsyncMock()
        orch._ensure_candidate = AsyncMock(return_value=MagicMock(id="cand-1"))

        gmail_scanner = MagicMock()
        drive_service = MagicMock()
        orch._discovery = MagicMock()
        orch._discovery.discover_documents = AsyncMock(return_value=([], []))

        await orch._process_candidate(batch, bc, gmail_scanner, drive_service, 1, 1)

        assert bc.status == BatchCandidateStatus.NO_DOCUMENTS.value


class TestDiscoveryServiceInit:
    def test_instantiation(self):
        db = AsyncMock()
        svc = DiscoveryService(db)
        assert svc.db is db

    @pytest.mark.asyncio
    async def test_get_gmail_scanner_no_config(self):
        db = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = DiscoveryService(db)
        scanner = await svc.get_gmail_scanner()
        assert scanner is None

    @pytest.mark.asyncio
    async def test_get_drive_service_no_config(self):
        db = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = DiscoveryService(db)
        drive = await svc.get_drive_service()
        assert drive is None


class TestDocumentIngestServiceInit:
    def test_instantiation(self):
        db = AsyncMock()
        audit = AsyncMock()
        svc = DocumentIngestService(db, audit)
        assert svc.db is db

    @pytest.mark.asyncio
    async def test_save_document_creates_record(self, tmp_path):
        db = AsyncMock(spec=AsyncSession)
        db.flush = AsyncMock()
        audit = AsyncMock()
        audit.log = AsyncMock()

        svc = DocumentIngestService(db, audit)

        candidate = MagicMock(id="cand-1")
        upload_batch = MagicMock(id="ub-1")

        with patch("app.services.batch.ingest_service.settings") as mock_settings, \
             patch("app.services.batch.ingest_service.aiofiles") as mock_aiofiles:
            mock_settings.upload_path = tmp_path
            # Mock aiofiles.open context manager
            mock_file = AsyncMock()
            mock_aiofiles.open.return_value.__aenter__ = AsyncMock(return_value=mock_file)
            mock_aiofiles.open.return_value.__aexit__ = AsyncMock(return_value=False)

            await svc._save_document(
                candidate, upload_batch, "test.pdf",
                "application/pdf", b"fake-content", "corr-1"
            )

        # Document was added to db and flushed
        db.add.assert_called()
        db.flush.assert_called()
        saved_document = db.add.call_args.args[0]
        saved_path = Path(saved_document.file_path)
        assert saved_path.parts[0] == "corr-1"
        assert "uploads" not in saved_path.parts


class TestDriveUploadServiceInit:
    def test_instantiation(self):
        db = AsyncMock()
        svc = DriveUploadService(db)
        assert svc.db is db


class TestBatchStatusServiceExtended:
    @pytest.mark.asyncio
    async def test_emit_candidate_status(self):
        db = AsyncMock()
        ws_hub = AsyncMock()
        ws_hub.emit_candidate_status = AsyncMock()

        svc = BatchStatusService(db, ws_hub=ws_hub)
        bc = MagicMock(
            id="bc-1", status="processing",
            documents_found=2, documents_processed=1,
            documents_failed=0, error_message=None,
        )

        await svc.emit_candidate_status("batch-1", bc)
        ws_hub.emit_candidate_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_summary(self):
        db = AsyncMock()
        ws_hub = AsyncMock()
        ws_hub.emit_processing_summary = AsyncMock()

        svc = BatchStatusService(db, ws_hub=ws_hub)
        svc._get_batch_candidates = AsyncMock(return_value=[])
        batch = MagicMock(
            id="batch-1",
            status="completed",
            total_candidates=5,
            processed_candidates=4,
            failed_candidates=1,
            skipped_candidates=0,
        )

        await svc.emit_summary(batch)
        ws_hub.emit_processing_summary.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_batch_totals(self):
        db = AsyncMock(spec=AsyncSession)
        # Mock scalars().all() for candidate counts
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [
            MagicMock(status=BatchCandidateStatus.COMPLETED.value),
            MagicMock(status=BatchCandidateStatus.FAILED.value),
            MagicMock(status=BatchCandidateStatus.NO_DOCUMENTS.value),
        ]
        db.execute.return_value = result_mock

        svc = BatchStatusService(db)
        batch = MagicMock(id="batch-1")

        await svc.update_batch_totals(batch)
        # Should have set processed, failed, skipped counts
