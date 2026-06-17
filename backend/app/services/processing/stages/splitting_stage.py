"""Splitting stage: creates child documents from multi-document PDFs after classification."""

import uuid
import asyncio
from pathlib import Path
from typing import List, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentPage
from app.models.ocr_result import OCRResult
from app.models.classification import AIClassification
from app.models.enums import ProcessingStatus, AuditAction
from app.services.processing.splitter import DocumentSplitter, DocumentGroup, PageClassification
from app.services.processing.stages.context import PipelineContext
from app.services.audit.logger import AuditService
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger("processing.stages.splitting")


class SplittingStage:
    """Splits a multi-document PDF into separate child Document records after classification.

    Only activates when page classifications reveal multiple document types.
    For single-type documents (or single-page docs), this stage is a no-op.
    """

    def __init__(self, db: AsyncSession, splitter: DocumentSplitter, audit: AuditService):
        self.db = db
        self.splitter = splitter
        self.audit = audit

    async def execute(self, ctx: PipelineContext) -> None:
        """Split classified pages into child documents if multiple types detected."""
        document = ctx.document
        document_id = ctx.document_id
        correlation_id = ctx.correlation_id

        # Group pages by classified type
        groups = self.splitter.group_pages_by_type(ctx.page_classifications)
        ctx.document_groups = groups

        # If only one group (all pages same type), no split needed
        if len(groups) <= 1:
            logger.info(
                "splitting_skipped",
                document_id=document_id,
                reason="single_document_type",
                doc_type=groups[0].document_type if groups else "unknown",
            )
            return

        # Multiple document types detected - create child documents
        logger.info(
            "splitting_start",
            document_id=document_id,
            groups=len(groups),
            types=[g.document_type for g in groups],
        )

        await self.audit.log(
            correlation_id=correlation_id,
            action=AuditAction.AI_COMPLETE.value,
            message=f"Splitting PDF into {len(groups)} documents: {[g.document_type for g in groups]}",
            document_id=document_id,
            processing_stage="splitting",
        )

        # Build a map of page_number -> DocumentPage
        page_map: Dict[int, DocumentPage] = {p.page_number: p for p in ctx.pages}

        child_doc_ids = []
        for group in groups:
            child_id = await self._create_child_document(
                parent=document,
                group=group,
                page_map=page_map,
                correlation_id=correlation_id,
            )
            child_doc_ids.append(child_id)

        ctx.child_document_ids = child_doc_ids
        ctx.is_split = True

        # Remove the full-doc classification from the parent (it's meaningless for multi-type PDFs)
        await self._remove_parent_full_doc_classification(document_id)

        # Mark parent as split
        document.processing_status = ProcessingStatus.COMPLETED.value

        logger.info(
            "splitting_complete",
            document_id=document_id,
            child_documents=len(child_doc_ids),
        )

    async def _remove_parent_full_doc_classification(self, document_id: str) -> None:
        """Remove the full-document classification from parent since each child has its own."""
        from sqlalchemy import select, delete

        await self.db.execute(
            delete(AIClassification).where(
                AIClassification.document_id == document_id,
                AIClassification.page_id == None,
            )
        )
        await self.db.flush()

    async def _create_child_document(
        self,
        parent: Document,
        group: DocumentGroup,
        page_map: Dict[int, DocumentPage],
        correlation_id: str,
    ) -> str:
        """Create a child Document record for a document group and reconstruct its PDF."""
        child_id = str(uuid.uuid4())

        # Collect page paths for this group
        group_pages = [page_map[pn] for pn in group.pages if pn in page_map]
        page_paths = [Path(p.file_path) for p in group_pages]

        # Reconstruct PDF from page images
        parent_dir_rel = Path(parent.file_path).parent
        child_dir_rel = parent_dir_rel / child_id
        
        child_dir_abs = settings.upload_path / child_dir_rel
        child_dir_abs.mkdir(parents=True, exist_ok=True)

        child_filename = f"{group.document_type}_{child_id[:8]}.pdf"
        child_pdf_path_rel = child_dir_rel / child_filename
        child_pdf_path_abs = child_dir_abs / child_filename

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, self.splitter.reconstruct_pdf_from_pages, page_paths, child_pdf_path_abs
        )

        # Get file size
        file_size = child_pdf_path_abs.stat().st_size

        # Create child Document record
        child_doc = Document(
            id=child_id,
            candidate_id=parent.candidate_id,
            upload_batch_id=parent.upload_batch_id,
            parent_document_id=parent.id,
            original_filename=f"{parent.original_filename} [{group.document_type}]",
            stored_filename=child_filename,
            file_path=str(child_pdf_path_rel),
            file_size_bytes=file_size,
            mime_type="application/pdf",
            total_pages=len(group.pages),
            is_multi_page=len(group.pages) > 1,
            processing_status=ProcessingStatus.AI_CLASSIFICATION_COMPLETE.value,
            correlation_id=correlation_id,
        )
        self.db.add(child_doc)
        await self.db.flush()

        # Create DocumentPage records for child (referencing the same page image files)
        for i, page in enumerate(group_pages):
            child_page = DocumentPage(
                document_id=child_id,
                page_number=i + 1,
                stored_filename=page.stored_filename,
                file_path=page.file_path,
                width=page.width,
                height=page.height,
                orientation_corrected=page.orientation_corrected,
                processing_status=ProcessingStatus.COMPLETED.value,
                correlation_id=correlation_id,
            )
            self.db.add(child_page)

        await self.db.flush()

        # Copy OCR results and classifications to child document
        await self._copy_ocr_and_classifications(parent, child_id, group_pages, correlation_id)

        logger.info(
            "child_document_created",
            child_id=child_id,
            parent_id=parent.id,
            doc_type=group.document_type,
            pages=group.pages,
        )

        return child_id

    async def _copy_ocr_and_classifications(
        self,
        parent: Document,
        child_id: str,
        group_pages: List[DocumentPage],
        correlation_id: str,
    ) -> None:
        """Copy OCR results and AI classifications from parent pages to child document."""
        from sqlalchemy import select

        page_ids = [p.id for p in group_pages]

        # Copy OCR results
        ocr_result = await self.db.execute(
            select(OCRResult).where(OCRResult.page_id.in_(page_ids))
        )
        ocr_records = ocr_result.scalars().all()

        for ocr in ocr_records:
            new_ocr = OCRResult(
                document_id=child_id,
                page_id=ocr.page_id,
                extracted_text=ocr.extracted_text,
                confidence_score=ocr.confidence_score,
                word_count=ocr.word_count,
                processing_duration_ms=ocr.processing_duration_ms,
                correlation_id=correlation_id,
            )
            self.db.add(new_ocr)

        # Copy classifications
        cls_result = await self.db.execute(
            select(AIClassification).where(AIClassification.page_id.in_(page_ids))
        )
        classifications = cls_result.scalars().all()

        for cls in classifications:
            new_cls = AIClassification(
                document_id=child_id,
                page_id=cls.page_id,
                document_type=cls.document_type,
                confidence_score=cls.confidence_score,
                ai_reasoning=cls.ai_reasoning,
                extracted_name=cls.extracted_name,
                extracted_dob=cls.extracted_dob,
                extracted_gender=cls.extracted_gender,
                extracted_id_number=cls.extracted_id_number,
                extracted_fields_json=cls.extracted_fields_json,
                model_used=cls.model_used,
                correlation_id=correlation_id,
            )
            self.db.add(new_cls)

        # Also create a full-document classification for the child
        if classifications:
            best_cls = max(classifications, key=lambda c: c.confidence_score or 0)
            full_doc_cls = AIClassification(
                document_id=child_id,
                page_id=None,
                document_type=best_cls.document_type,
                confidence_score=best_cls.confidence_score,
                ai_reasoning=f"Full-doc classification from split: {best_cls.ai_reasoning or ''}",
                extracted_name=best_cls.extracted_name,
                extracted_dob=best_cls.extracted_dob,
                extracted_gender=best_cls.extracted_gender,
                extracted_id_number=best_cls.extracted_id_number,
                extracted_fields_json=best_cls.extracted_fields_json,
                model_used=best_cls.model_used,
                correlation_id=correlation_id,
            )
            self.db.add(full_doc_cls)

        await self.db.flush()
