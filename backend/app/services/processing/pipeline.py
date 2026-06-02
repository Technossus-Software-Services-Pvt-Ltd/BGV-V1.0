import json
import time
import uuid
import asyncio
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document, DocumentPage
from app.models.ocr_result import OCRResult
from app.models.classification import AIClassification
from app.models.validation_result import ValidationResult
from app.models.candidate import Candidate
from app.models.upload_batch import UploadBatch
from app.models.enums import ProcessingStatus, AuditAction, LogLevel

from app.services.ocr.engine import PaddleOCREngine
from app.services.ocr.preprocessor import DocumentPreprocessor
from app.services.ocr.confidence import OCRConfidenceEvaluator
from app.services.ai.classifier import AIClassifier
from app.services.validation.ownership import OwnershipValidator
from app.services.processing.normalizer import DocumentNormalizer
from app.services.processing.splitter import DocumentSplitter, PageClassification
from app.services.audit.logger import AuditService

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger("processing.pipeline")


class ProcessingPipeline:
    """Orchestrates the full document processing pipeline:
    Upload → Normalize → OCR → AI Classification → Validation → Result
    """

    # Class-level singletons for heavy/stateless services
    _ocr_engine = PaddleOCREngine()
    _preprocessor = DocumentPreprocessor()
    _confidence_evaluator = OCRConfidenceEvaluator()
    _ai_classifier = AIClassifier()
    _ownership_validator = OwnershipValidator()
    _normalizer = DocumentNormalizer()
    _splitter = DocumentSplitter()

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ocr_engine = self._ocr_engine
        self.preprocessor = self._preprocessor
        self.confidence_evaluator = self._confidence_evaluator
        self.ai_classifier = self._ai_classifier
        self.ownership_validator = self._ownership_validator
        self.normalizer = self._normalizer
        self.splitter = self._splitter
        self.audit = AuditService(db)

    async def process_document(self, document_id: str) -> None:
        """Main entry point: processes a single document through all stages."""
        start_time = time.time()

        # Load document
        logger.info("pipeline_start", document_id=document_id)
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            logger.error("document_not_found", document_id=document_id)
            return

        correlation_id = document.correlation_id
        logger.info("document_loaded", document_id=document_id, filename=document.original_filename, correlation_id=correlation_id)

        try:
            # Stage 1: Normalization
            logger.info("stage_start", stage="normalization", document_id=document_id, correlation_id=correlation_id)
            await self._update_status(document, ProcessingStatus.NORMALIZING)
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

            # Stage 2: OCR Processing
            logger.info("stage_start", stage="ocr", document_id=document_id, page_count=len(pages))
            await self._update_status(document, ProcessingStatus.OCR_RUNNING)
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
                # Check if this is a photo/image file that simply can't be processed for text
                photo_mime_types = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/bmp", "image/webp"}
                is_photo = document.mime_type and document.mime_type.lower() in photo_mime_types

                if is_photo:
                    await self._update_status(document, ProcessingStatus.SKIPPED)
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
                    await self._update_status(document, ProcessingStatus.OCR_FAILED)
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
                return

            combined_text = "\n---PAGE BREAK---\n".join(all_ocr_text)
            avg_confidence = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

            logger.info("stage_complete", stage="ocr", document_id=document_id, avg_confidence=f"{avg_confidence:.2f}", text_length=len(combined_text))
            await self._update_status(document, ProcessingStatus.OCR_COMPLETE)
            await self.audit.log(
                correlation_id=correlation_id,
                action=AuditAction.OCR_COMPLETE.value,
                message=f"OCR complete. Avg confidence: {avg_confidence:.2f}",
                document_id=document_id,
                processing_stage="ocr",
                details={"avg_confidence": avg_confidence, "total_pages": len(pages)},
            )

            # Stage 3: AI Classification
            logger.info("stage_start", stage="ai_classification", document_id=document_id)
            await self._update_status(document, ProcessingStatus.AI_CLASSIFYING)
            await self.audit.log(
                correlation_id=correlation_id,
                action=AuditAction.AI_START.value,
                message="AI classification started",
                document_id=document_id,
                processing_stage="ai_classification",
            )

            # Classify each page individually for multi-page docs
            page_classifications = []
            for page in pages:
                classification = await self._classify_page(document, page, correlation_id)
                if classification:
                    page_classifications.append(PageClassification(
                        page_number=page.page_number,
                        document_type=classification.document_type,
                        confidence=classification.confidence_score,
                    ))

            # Also classify the full document
            full_classification = await self._classify_full_document(
                document, combined_text, avg_confidence, correlation_id
            )

            logger.info("stage_complete", stage="ai_classification", document_id=document_id, document_type=full_classification.document_type if full_classification else "unknown", confidence=f"{full_classification.confidence_score:.2f}" if full_classification else "0.00")
            await self._update_status(document, ProcessingStatus.AI_CLASSIFICATION_COMPLETE)
            await self.audit.log(
                correlation_id=correlation_id,
                action=AuditAction.AI_COMPLETE.value,
                message=f"AI classification complete: {full_classification.document_type if full_classification else 'unknown'}",
                document_id=document_id,
                processing_stage="ai_classification",
            )

            # Stage 4: Ownership Validation
            logger.info("stage_start", stage="validation", document_id=document_id)
            await self._update_status(document, ProcessingStatus.VALIDATING)
            await self.audit.log(
                correlation_id=correlation_id,
                action=AuditAction.VALIDATION_START.value,
                message="Ownership validation started",
                document_id=document_id,
                processing_stage="validation",
            )

            await self._validate_ownership(document, full_classification, correlation_id)

            logger.info("stage_complete", stage="validation", document_id=document_id)
            await self._update_status(document, ProcessingStatus.VALIDATION_COMPLETE)
            await self.audit.log(
                correlation_id=correlation_id,
                action=AuditAction.VALIDATION_COMPLETE.value,
                message="Ownership validation complete",
                document_id=document_id,
                processing_stage="validation",
            )

            # Stage 5: Final
            await self._update_status(document, ProcessingStatus.COMPLETED)
            total_duration = int((time.time() - start_time) * 1000)
            logger.info("pipeline_complete", document_id=document_id, total_duration_ms=total_duration)
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

        except Exception as e:
            logger.error("pipeline_failed", document_id=document_id, error=str(e))
            await self._update_status(document, ProcessingStatus.FAILED)
            document.error_message = str(e)[:500]
            await self.audit.log(
                correlation_id=correlation_id,
                action=AuditAction.PROCESSING_FAILED.value,
                message=f"Pipeline failed: {str(e)[:200]}",
                log_level=LogLevel.ERROR.value,
                document_id=document_id,
                processing_stage="error",
                error_details=str(e),
            )
            await self._update_batch_progress(document.upload_batch_id, success=False)
            await self.db.flush()

    async def _process_page_ocr(
        self, document: Document, page: DocumentPage, correlation_id: str
    ) -> Optional[OCRResult]:
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

            # Run OCR (CPU-bound, uses dedicated thread pool)
            ocr_result = await self.ocr_engine.process_async(img_array)

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

    async def _classify_page(
        self, document: Document, page: DocumentPage, correlation_id: str
    ) -> Optional[AIClassification]:
        # Get OCR result for this page
        result = await self.db.execute(
            select(OCRResult).where(OCRResult.page_id == page.id)
        )
        ocr_record = result.scalar_one_or_none()

        if not ocr_record or not ocr_record.extracted_text:
            return None

        classification_result = await self.ai_classifier.classify_document(
            ocr_text=ocr_record.extracted_text,
            ocr_confidence=ocr_record.confidence_score or 0.0,
            word_count=ocr_record.word_count,
        )

        classification = AIClassification(
            document_id=document.id,
            page_id=page.id,
            document_type=classification_result.document_type,
            confidence_score=classification_result.confidence,
            ai_reasoning=classification_result.reasoning,
            extracted_name=classification_result.extracted_name,
            extracted_dob=classification_result.extracted_dob,
            extracted_gender=classification_result.extracted_gender,
            extracted_id_number=classification_result.extracted_id_number,
            extracted_fields_json=json.dumps({"key_identifiers": classification_result.key_identifiers, "extracted_gender": classification_result.extracted_gender}),
            model_used=classification_result.model_used,
            prompt_tokens=classification_result.prompt_tokens,
            completion_tokens=classification_result.completion_tokens,
            processing_duration_ms=classification_result.processing_duration_ms,
            error_message=classification_result.error,
            correlation_id=correlation_id,
        )
        self.db.add(classification)
        await self.db.flush()

        return classification

    async def _classify_full_document(
        self, document: Document, combined_text: str, avg_confidence: float, correlation_id: str
    ) -> Optional[AIClassification]:
        word_count = len(combined_text.split())

        classification_result = await self.ai_classifier.classify_document(
            ocr_text=combined_text,
            ocr_confidence=avg_confidence,
            word_count=word_count,
        )

        classification = AIClassification(
            document_id=document.id,
            page_id=None,  # Full document classification
            document_type=classification_result.document_type,
            confidence_score=classification_result.confidence,
            ai_reasoning=classification_result.reasoning,
            extracted_name=classification_result.extracted_name,
            extracted_dob=classification_result.extracted_dob,
            extracted_gender=classification_result.extracted_gender,
            extracted_id_number=classification_result.extracted_id_number,
            extracted_fields_json=json.dumps({"key_identifiers": classification_result.key_identifiers, "extracted_gender": classification_result.extracted_gender}),
            model_used=classification_result.model_used,
            prompt_tokens=classification_result.prompt_tokens,
            completion_tokens=classification_result.completion_tokens,
            processing_duration_ms=classification_result.processing_duration_ms,
            error_message=classification_result.error,
            correlation_id=correlation_id,
        )
        self.db.add(classification)
        await self.db.flush()

        return classification

    async def _validate_ownership(
        self, document: Document, classification: Optional[AIClassification], correlation_id: str
    ) -> None:
        # Load candidate
        result = await self.db.execute(
            select(Candidate).where(Candidate.id == document.candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            return

        # Get full OCR text for this document
        ocr_results = await self.db.execute(
            select(OCRResult).where(OCRResult.document_id == document.id)
        )
        ocr_records = ocr_results.scalars().all()
        combined_ocr_text = "\n".join(r.extracted_text for r in ocr_records if r.extracted_text)
        avg_confidence = (
            sum(r.confidence_score for r in ocr_records if r.confidence_score)
            / len(ocr_records) if ocr_records else 0.0
        )

        # === BEST-MATCH STRATEGY ===
        # Query ALL classifications for this document (per-page + full-doc).
        # Validate ownership against each classification that has an extracted_name.
        # Use the result with the highest ownership score.
        all_classifications_result = await self.db.execute(
            select(AIClassification).where(
                AIClassification.document_id == document.id
            ).order_by(AIClassification.confidence_score.desc())
        )
        all_classifications = all_classifications_result.scalars().all()

        # Collect candidates for validation: classifications with extracted_name
        classifications_with_name = [
            c for c in all_classifications if c.extracted_name
        ]

        # If no classification has extracted_name, fall back to the full-doc classification
        if not classifications_with_name and classification:
            classifications_with_name = [classification]

        best_result = None
        best_score = -1.0
        best_classification = None

        for cls in classifications_with_name:
            extracted_name = cls.extracted_name
            extracted_dob = cls.extracted_dob
            doc_type = cls.document_type or "unknown"

            # Extract gender
            extracted_gender = None
            if cls.extracted_gender:
                extracted_gender = cls.extracted_gender
            elif cls.extracted_fields_json:
                try:
                    fields = json.loads(cls.extracted_fields_json)
                    extracted_gender = fields.get("extracted_gender")
                except (json.JSONDecodeError, TypeError):
                    pass

            vr = self.ownership_validator.validate(
                candidate_name=candidate.name,
                candidate_dob=candidate.dob,
                candidate_gender=candidate.gender,
                extracted_name=extracted_name,
                extracted_dob=extracted_dob,
                extracted_gender=extracted_gender,
                ocr_text=combined_ocr_text,
                document_type=doc_type,
                ocr_confidence=avg_confidence,
            )

            if vr.ownership_score > best_score:
                best_score = vr.ownership_score
                best_result = vr
                best_classification = cls

        # If no classifications at all, run validation with no extracted data
        if best_result is None:
            doc_type = classification.document_type if classification else "unknown"
            best_result = self.ownership_validator.validate(
                candidate_name=candidate.name,
                candidate_dob=candidate.dob,
                candidate_gender=candidate.gender,
                extracted_name=None,
                extracted_dob=None,
                extracted_gender=None,
                ocr_text=combined_ocr_text,
                document_type=doc_type,
                ocr_confidence=avg_confidence,
            )
            best_classification = classification

        # If multi-person detected and only partial match, require manual review
        if best_result.multi_person_detected and not best_result.ownership_confirmed:
            best_result.requires_manual_review = True
            if "Multi-person document with partial match" not in best_result.manual_review_reasons:
                best_result.manual_review_reasons.append("Multi-person document with partial match")

        validation_result = best_result

        logger.info(
            "ownership_best_match",
            document_id=document.id,
            classifications_checked=len(classifications_with_name),
            best_score=f"{validation_result.ownership_score:.1f}",
            best_source="page" if (best_classification and best_classification.page_id) else "full_doc",
            confirmed=validation_result.ownership_confirmed,
        )

        validation_record = ValidationResult(
            document_id=document.id,
            candidate_id=candidate.id,
            validation_status=validation_result.validation_status,
            ownership_score=validation_result.ownership_score,
            confidence=validation_result.confidence,
            name_match_score=validation_result.name_match_score,
            name_match_level=validation_result.name_match_level,
            name_matched_tokens=validation_result.name_matched_tokens,
            name_total_tokens=validation_result.name_total_tokens,
            dob_match=validation_result.dob_match,
            dob_partial=validation_result.dob_partial,
            gender_match=validation_result.gender_match,
            multi_person_detected=validation_result.multi_person_detected,
            name_match=validation_result.ownership_confirmed,
            id_number_match=validation_result.id_number_match,
            ownership_confirmed=validation_result.ownership_confirmed,
            validation_reasoning=validation_result.reasoning,
            mismatches_json=json.dumps(validation_result.mismatches),
            requires_manual_review=validation_result.requires_manual_review,
            manual_review_reasons_json=json.dumps(validation_result.manual_review_reasons),
            processing_duration_ms=validation_result.processing_duration_ms,
            correlation_id=correlation_id,
        )
        self.db.add(validation_record)
        await self.db.flush()

        await self.audit.record_processing_event(
            correlation_id=correlation_id,
            document_id=document.id,
            event_type="validation_complete",
            stage="validation",
            status="completed",
            message=validation_result.reasoning,
            metadata={
                "name_score": validation_result.name_match_score,
                "ownership_score": validation_result.ownership_score,
                "ownership_confirmed": validation_result.ownership_confirmed,
                "classifications_checked": len(classifications_with_name),
                "best_source_page_id": best_classification.page_id if best_classification else None,
            },
        )

    async def _update_status(self, document: Document, status: ProcessingStatus) -> None:
        document.processing_status = status.value
        await self.db.flush()

    async def _update_batch_progress(self, batch_id: str, success: bool) -> None:
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
