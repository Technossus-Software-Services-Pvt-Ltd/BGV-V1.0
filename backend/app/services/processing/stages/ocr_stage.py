"""OCR stage: runs OCR on each page and produces text + confidence."""

import json
import asyncio
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentPage
from app.models.ocr_result import OCRResult
from app.models.enums import ProcessingStatus, AuditAction, LogLevel
from app.services.ocr.engine import PaddleOCREngine
from app.services.ocr.preprocessor import DocumentPreprocessor
from app.services.processing.stages.context import PipelineContext
from app.services.audit.logger import AuditService
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("processing.stages.ocr")


class OCRStage:
    """Runs OCR on each document page, producing text and confidence scores."""

    def __init__(
        self,
        db: AsyncSession,
        ocr_engine: PaddleOCREngine,
        preprocessor: DocumentPreprocessor,
        audit: AuditService,
    ):
        self.db = db
        self.ocr_engine = ocr_engine
        self.preprocessor = preprocessor
        self.audit = audit

    async def execute(self, ctx: PipelineContext) -> None:
        """Run OCR on all pages. Sets ctx.should_stop if no text extracted."""
        document = ctx.document
        document_id = ctx.document_id
        correlation_id = ctx.correlation_id
        pages = ctx.pages

        logger.info("stage_start", stage="ocr", document_id=document_id, page_count=len(pages))
        document.processing_status = ProcessingStatus.OCR_RUNNING.value
        await self.db.flush()

        await self.audit.log(
            correlation_id=correlation_id,
            action=AuditAction.OCR_START.value,
            message=f"OCR processing started for {len(pages)} pages",
            document_id=document_id,
            processing_stage="ocr",
        )

        all_ocr_text = []
        all_confidences = []

        for page in pages:
            ocr_result = await self._process_page_ocr(document, page, correlation_id)
            if ocr_result and ocr_result.extracted_text:
                all_ocr_text.append(ocr_result.extracted_text)
                if ocr_result.confidence_score:
                    all_confidences.append(ocr_result.confidence_score)

        if not all_ocr_text:
            await self._handle_no_text(document, document_id, correlation_id)
            ctx.should_stop = True
            ctx.stop_reason = "no_ocr_text"
            return

        combined_text = "\n---PAGE BREAK---\n".join(all_ocr_text)
        avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

        # Store results in context
        ctx.all_ocr_text = all_ocr_text
        ctx.all_confidences = all_confidences
        ctx.combined_text = combined_text
        ctx.avg_confidence = avg_confidence

        logger.info("stage_complete", stage="ocr", document_id=document_id, avg_confidence=f"{avg_confidence:.2f}", text_length=len(combined_text))
        document.processing_status = ProcessingStatus.OCR_COMPLETE.value
        await self.db.flush()

        await self.audit.log(
            correlation_id=correlation_id,
            action=AuditAction.OCR_COMPLETE.value,
            message=f"OCR complete. Avg confidence: {avg_confidence:.2f}",
            document_id=document_id,
            processing_stage="ocr",
            details={"avg_confidence": avg_confidence, "total_pages": len(pages)},
        )

    async def _process_page_ocr(
        self, document: Document, page: DocumentPage, correlation_id: str
    ) -> Optional[OCRResult]:
        """Process OCR for a single page."""
        try:
            page_path = Path(page.file_path)

            # Normalize image (CPU-bound, run in executor)
            loop = asyncio.get_running_loop()
            img_array, metadata = await loop.run_in_executor(
                None, self.preprocessor.normalize_image, page_path
            )

            # Check for blank page (CPU-bound, run in executor)
            is_blank = await loop.run_in_executor(
                None, self.preprocessor.is_blank_page, img_array
            )
            if is_blank:
                page.processing_status = ProcessingStatus.OCR_COMPLETE.value
                ocr_record = OCRResult(
                    document_id=document.id,
                    page_id=page.id,
                    ocr_engine="paddleocr",
                    extracted_text="",
                    confidence_score=0.0,
                    word_count=0,
                    processing_duration_ms=0,
                    correlation_id=correlation_id,
                    error_message="Blank page detected",
                )
                self.db.add(ocr_record)
                await self.db.flush()
                return ocr_record

            # Run OCR (CPU-bound, uses dedicated thread pool) with per-page timeout
            try:
                ocr_result = await asyncio.wait_for(
                    self.ocr_engine.process_async(img_array),
                    timeout=settings.ocr_page_timeout_seconds,
                )
            except asyncio.TimeoutError:
                page.processing_status = ProcessingStatus.OCR_FAILED.value
                ocr_record = OCRResult(
                    document_id=document.id,
                    page_id=page.id,
                    ocr_engine="paddleocr",
                    extracted_text="",
                    confidence_score=0.0,
                    word_count=0,
                    processing_duration_ms=settings.ocr_page_timeout_seconds * 1000,
                    correlation_id=correlation_id,
                    error_message=f"OCR timed out after {settings.ocr_page_timeout_seconds}s",
                )
                self.db.add(ocr_record)
                await self.db.flush()
                logger.warning("page_ocr_timeout", page_id=page.id, timeout=settings.ocr_page_timeout_seconds)
                return ocr_record

            # Retry with aggressive preprocessing if confidence is below threshold
            if ocr_result.confidence < settings.ocr_retry_confidence_threshold and ocr_result.confidence > 0:
                logger.info(
                    "ocr_low_confidence_retry",
                    page_id=page.id,
                    original_confidence=ocr_result.confidence,
                )
                enhanced_array = await loop.run_in_executor(
                    None, self.preprocessor.enhance_aggressive, img_array
                )
                try:
                    retry_result = await asyncio.wait_for(
                        self.ocr_engine.process_async(enhanced_array),
                        timeout=settings.ocr_page_timeout_seconds,
                    )
                    # Keep the better result
                    if retry_result.confidence > ocr_result.confidence:
                        logger.info(
                            "ocr_retry_improved",
                            page_id=page.id,
                            old_conf=ocr_result.confidence,
                            new_conf=retry_result.confidence,
                        )
                        ocr_result = retry_result
                except asyncio.TimeoutError:
                    logger.warning("ocr_retry_timeout", page_id=page.id)

            # Update page metadata
            page.width = metadata.get("final_width")
            page.height = metadata.get("final_height")
            page.orientation_corrected = metadata.get("orientation_corrected", False)
            page.processing_status = ProcessingStatus.OCR_COMPLETE.value

            # Store OCR result
            ocr_record = OCRResult(
                document_id=document.id,
                page_id=page.id,
                ocr_engine="paddleocr",
                extracted_text=ocr_result.text,
                confidence_score=ocr_result.confidence,
                word_count=ocr_result.word_count,
                language_detected=ocr_result.language_detected,
                orientation_angle=ocr_result.orientation_angle,
                processing_duration_ms=ocr_result.processing_duration_ms,
                raw_output_json=json.dumps(ocr_result.raw_output[:50]),  # Limit stored raw data
                error_message=ocr_result.error,
                correlation_id=correlation_id,
            )
            self.db.add(ocr_record)
            await self.db.flush()

            await self.audit.record_processing_event(
                correlation_id=correlation_id,
                document_id=document.id,
                page_id=page.id,
                event_type="ocr_complete",
                stage="ocr",
                status="completed",
                confidence=ocr_result.confidence,
                duration_ms=ocr_result.processing_duration_ms,
            )

            return ocr_record

        except Exception as e:
            page.processing_status = ProcessingStatus.OCR_FAILED.value
            logger.error("page_ocr_failed", page_id=page.id, error=str(e))
            await self.db.flush()
            return None

    async def _handle_no_text(
        self, document: Document, document_id: str, correlation_id: str
    ) -> None:
        """Handle case when OCR produces no text from any page."""
        photo_mime_types = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/bmp", "image/webp"}
        is_photo = document.mime_type and document.mime_type.lower() in photo_mime_types

        if is_photo:
            document.processing_status = ProcessingStatus.SKIPPED.value
            document.error_message = "Can't process photos"
            await self.audit.log(
                correlation_id=correlation_id,
                action=AuditAction.OCR_FAILED.value,
                message="Can't process photos - no text content",
                log_level=LogLevel.WARNING.value,
                document_id=document_id,
                processing_stage="ocr",
            )
        else:
            document.processing_status = ProcessingStatus.OCR_FAILED.value
            document.error_message = "OCR produced no text from any page"
            await self.audit.log(
                correlation_id=correlation_id,
                action=AuditAction.OCR_FAILED.value,
                message="OCR produced no text",
                log_level=LogLevel.ERROR.value,
                document_id=document_id,
                processing_stage="ocr",
            )
        await self.db.flush()
