"""Service responsible for batch progress tracking, logging, and WebSocket emissions."""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.protocols import WebSocketHubProtocol

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.batch_import import BatchImport
from app.models.batch_import_candidate import BatchImportCandidate
from app.models.batch_log import BatchLog
from app.models.enums import BatchCandidateStatus
from app.services.websocket.hub import ws_hub as _default_ws_hub
from app.core.logging import get_logger

logger = get_logger("batch.status")


class BatchStatusService:
    """Manages batch progress tracking, logging, and real-time WebSocket emissions."""

    def __init__(self, db: AsyncSession, ws_hub: Optional["WebSocketHubProtocol"] = None):
        self.db = db
        self._ws_hub = ws_hub if ws_hub is not None else _default_ws_hub

    async def log(
        self,
        batch_import_id: str,
        batch_candidate_id: Optional[str],
        level: str,
        stage: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        """Write a batch log entry and emit via WebSocket."""
        log_entry = BatchLog(
            batch_import_id=batch_import_id,
            batch_candidate_id=batch_candidate_id,
            level=level,
            stage=stage,
            message=message,
            details=details,
        )
        self.db.add(log_entry)
        await self.db.flush()
        logger.info("batch_log", batch_id=batch_import_id, level=level, stage=stage, message=message)

        await self._ws_hub.emit_processing_log(
            batch_id=batch_import_id,
            log_id=log_entry.id,
            batch_candidate_id=batch_candidate_id,
            level=level,
            stage=stage,
            message=message,
            details=details,
        )

    async def emit_candidate_status(self, batch_id: str, bc: BatchImportCandidate) -> None:
        """Emit candidate status change via WebSocket."""
        await self._ws_hub.emit_candidate_status(
            batch_id=batch_id,
            candidate_id=bc.id,
            status=bc.status,
            documents_found=bc.documents_found or 0,
            documents_processed=bc.documents_processed or 0,
            documents_failed=bc.documents_failed or 0,
            error_message=bc.error_message,
        )

    async def emit_summary(self, batch: BatchImport) -> None:
        """Emit processing summary counts via WebSocket."""
        candidates = await self._get_batch_candidates(batch.id)
        in_progress = sum(
            1 for c in candidates
            if c.status in (
                BatchCandidateStatus.PROCESSING.value,
                BatchCandidateStatus.DISCOVERING.value,
                BatchCandidateStatus.DOWNLOADING.value,
                BatchCandidateStatus.DOCUMENTS_FOUND.value,
            )
        )
        completed = sum(1 for c in candidates if c.status == BatchCandidateStatus.COMPLETED.value)
        failed = sum(1 for c in candidates if c.status == BatchCandidateStatus.FAILED.value)
        partial = sum(
            1 for c in candidates
            if c.status in (
                BatchCandidateStatus.PARTIAL.value,
                BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value,
            )
        )
        pending = sum(1 for c in candidates if c.status == BatchCandidateStatus.PENDING.value)
        no_documents = sum(1 for c in candidates if c.status == BatchCandidateStatus.NO_DOCUMENTS.value)

        await self._ws_hub.emit_processing_summary(
            batch_id=batch.id,
            total=batch.total_candidates or len(candidates),
            completed=completed,
            failed=failed,
            in_progress=in_progress,
            partial=partial,
            pending=pending,
            no_documents=no_documents,
            batch_status=batch.status,
        )

    async def update_batch_totals(self, batch: BatchImport) -> None:
        """Recompute batch-level totals from candidate statuses."""
        candidates = await self._get_batch_candidates(batch.id)
        batch.processed_candidates = sum(1 for c in candidates if c.status == BatchCandidateStatus.COMPLETED.value)
        batch.failed_candidates = sum(1 for c in candidates if c.status == BatchCandidateStatus.FAILED.value)
        batch.skipped_candidates = sum(
            1 for c in candidates
            if c.status in (BatchCandidateStatus.NO_DOCUMENTS.value, BatchCandidateStatus.SKIPPED.value)
        )
        batch.total_documents_found = sum(c.documents_found for c in candidates)
        batch.total_documents_processed = sum(c.documents_processed for c in candidates)
        await self.db.flush()

    async def _get_batch_candidates(self, batch_import_id: str) -> list[BatchImportCandidate]:
        result = await self.db.execute(
            select(BatchImportCandidate)
            .where(BatchImportCandidate.batch_import_id == batch_import_id)
            .order_by(BatchImportCandidate.row_number)
        )
        return list(result.scalars().all())
