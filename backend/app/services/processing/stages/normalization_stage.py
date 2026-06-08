"""Normalization stage: extracts pages from uploaded documents."""

import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentPage
from app.models.enums import ProcessingStatus, AuditAction
from app.services.processing.normalizer import DocumentNormalizer
from app.services.processing.stages.context import PipelineContext
from app.services.audit.logger import AuditService
from app.core.logging import get_logger

logger = get_logger("processing.stages.normalization")


class NormalizationStage:
    """Extracts pages from a document file (PDF → images, image → single page)."""

    def __init__(self, db: AsyncSession, normalizer: DocumentNormalizer, audit: AuditService):
        self.db = db
        self.normalizer = normalizer
        self.audit = audit

    async def execute(self, ctx: PipelineContext) -> None:
        """Extract pages from the document and create DocumentPage records."""
        document = ctx.document
        document_id = ctx.document_id
        correlation_id = ctx.correlation_id

        logger.info("stage_start", stage="normalization", document_id=document_id, correlation_id=correlation_id)
        document.processing_status = ProcessingStatus.NORMALIZING.value
        await self.db.flush()

        await self.audit.record_processing_event(
            correlation_id=correlation_id,
            document_id=document_id,
            event_type="stage_start",
            stage="normalization",
            status="running",
            message="Document normalization started",
        )

        doc_dir = self.normalizer.get_document_dir(correlation_id, document_id)
        file_path = Path(document.file_path)
        loop = asyncio.get_running_loop()
        page_paths = await loop.run_in_executor(
            None, self.normalizer.extract_pages, file_path, doc_dir, document.mime_type
        )

        # Update document page count
        document.total_pages = len(page_paths)
        document.is_multi_page = len(page_paths) > 1

        # Create page records
        pages = []
        for i, page_path in enumerate(page_paths):
            page = DocumentPage(
                document_id=document_id,
                page_number=i + 1,
                stored_filename=page_path.name,
                file_path=str(page_path),
                processing_status=ProcessingStatus.PENDING.value,
                correlation_id=correlation_id,
            )
            self.db.add(page)
            pages.append(page)

        await self.db.flush()
        ctx.pages = pages

        logger.info("stage_complete", stage="normalization", document_id=document_id, total_pages=len(page_paths))
        await self.audit.record_processing_event(
            correlation_id=correlation_id,
            document_id=document_id,
            event_type="stage_complete",
            stage="normalization",
            status="completed",
            message=f"Extracted {len(page_paths)} pages",
            metadata={"total_pages": len(page_paths)},
        )
