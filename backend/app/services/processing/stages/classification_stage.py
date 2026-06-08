"""Classification stage: AI-powered document type classification."""

import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document, DocumentPage
from app.models.ocr_result import OCRResult
from app.models.classification import AIClassification
from app.models.enums import ProcessingStatus, AuditAction
from app.services.ai.classifier import AIClassifier
from app.services.processing.splitter import PageClassification
from app.services.processing.stages.context import PipelineContext
from app.services.audit.logger import AuditService
from app.core.logging import get_logger

logger = get_logger("processing.stages.classification")


class ClassificationStage:
    """Classifies document pages and the full document using AI."""

    def __init__(self, db: AsyncSession, ai_classifier: AIClassifier, audit: AuditService):
        self.db = db
        self.ai_classifier = ai_classifier
        self.audit = audit

    async def execute(self, ctx: PipelineContext) -> None:
        """Classify each page individually and the full document."""
        document = ctx.document
        document_id = ctx.document_id
        correlation_id = ctx.correlation_id
        pages = ctx.pages

        logger.info("stage_start", stage="ai_classification", document_id=document_id)
        document.processing_status = ProcessingStatus.AI_CLASSIFYING.value
        await self.db.flush()

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
            document, ctx.combined_text, ctx.avg_confidence, correlation_id
        )

        # Store results in context
        ctx.page_classifications = page_classifications
        ctx.full_classification = full_classification

        logger.info("stage_complete", stage="ai_classification", document_id=document_id, document_type=full_classification.document_type if full_classification else "unknown", confidence=f"{full_classification.confidence_score:.2f}" if full_classification else "0.00")
        document.processing_status = ProcessingStatus.AI_CLASSIFICATION_COMPLETE.value
        await self.db.flush()

        await self.audit.log(
            correlation_id=correlation_id,
            action=AuditAction.AI_COMPLETE.value,
            message=f"AI classification complete: {full_classification.document_type if full_classification else 'unknown'}",
            document_id=document_id,
            processing_stage="ai_classification",
        )

    async def _classify_page(
        self, document: Document, page: DocumentPage, correlation_id: str
    ) -> Optional[AIClassification]:
        """Classify a single page based on its OCR text."""
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
        """Classify the entire document based on combined OCR text."""
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
