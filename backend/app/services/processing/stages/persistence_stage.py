"""Persistence stage: final status update and batch progress tracking."""

import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document
from app.models.upload_batch import UploadBatch
from app.models.enums import ProcessingStatus, AuditAction
from app.services.processing.stages.context import PipelineContext
from app.services.audit.logger import AuditService
from app.core.logging import get_logger

logger = get_logger("processing.stages.persistence")


class PersistenceStage:
    """Marks document as completed and updates batch progress."""

    def __init__(self, db: AsyncSession, audit: AuditService):
        self.db = db
        self.audit = audit

    async def execute(self, ctx: PipelineContext, start_time: float) -> None:
        """Mark document as completed and update batch counters."""
        document = ctx.document
        document_id = ctx.document_id
        correlation_id = ctx.correlation_id

        document.processing_status = ProcessingStatus.COMPLETED.value
        total_duration = int((time.time() - start_time) * 1000)

        # If split, also mark child documents as completed
        if ctx.is_split and ctx.child_document_ids:
            for child_id in ctx.child_document_ids:
                result = await self.db.execute(
                    select(Document).where(Document.id == child_id)
                )
                child_doc = result.scalar_one_or_none()
                if child_doc:
                    child_doc.processing_status = ProcessingStatus.COMPLETED.value

        logger.info("pipeline_complete", document_id=document_id, total_duration_ms=total_duration, is_split=ctx.is_split, child_count=len(ctx.child_document_ids))
        await self.audit.log(
            correlation_id=correlation_id,
            action=AuditAction.PROCESSING_COMPLETE.value,
            message=f"Document processing complete in {total_duration}ms",
            document_id=document_id,
            processing_stage="complete",
            duration_ms=total_duration,
        )
        await self.audit.record_processing_event(
            correlation_id=correlation_id,
            document_id=document_id,
            event_type="pipeline_complete",
            stage="complete",
            status="completed",
            duration_ms=total_duration,
        )

        # Update batch progress
        await self._update_batch_progress(document.upload_batch_id, success=True)
        await self.db.flush()

    async def execute_failure(self, ctx: PipelineContext, error: Exception) -> None:
        """Handle pipeline failure: update status and batch counters."""
        document = ctx.document
        document_id = ctx.document_id
        correlation_id = ctx.correlation_id

        logger.error("pipeline_failed", document_id=document_id, error=str(error))
        document.processing_status = ProcessingStatus.FAILED.value
        document.error_message = str(error)[:500]

        await self.audit.log(
            correlation_id=correlation_id,
            action=AuditAction.PROCESSING_FAILED.value,
            message=f"Pipeline failed: {str(error)[:200]}",
            log_level="ERROR",
            document_id=document_id,
            processing_stage="error",
            error_details=str(error),
        )
        await self._update_batch_progress(document.upload_batch_id, success=False)
        await self.db.flush()

    async def _update_batch_progress(self, batch_id: str, success: bool) -> None:
        """Update upload batch counters."""
        result = await self.db.execute(select(UploadBatch).where(UploadBatch.id == batch_id))
        batch = result.scalar_one_or_none()
        if batch:
            if success:
                batch.processed_files = (batch.processed_files or 0) + 1
            else:
                batch.failed_files = (batch.failed_files or 0) + 1

            total_done = (batch.processed_files or 0) + (batch.failed_files or 0)
            if total_done >= batch.total_files:
                batch.processing_status = ProcessingStatus.COMPLETED.value
            else:
                batch.processing_status = ProcessingStatus.OCR_RUNNING.value

            await self.db.flush()
