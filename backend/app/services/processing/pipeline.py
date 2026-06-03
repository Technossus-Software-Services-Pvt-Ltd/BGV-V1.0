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

from app.services.processing.stages.context import PipelineContext
from app.services.processing.stages.normalization_stage import NormalizationStage
from app.services.processing.stages.ocr_stage import OCRStage
from app.services.processing.stages.classification_stage import ClassificationStage
from app.services.processing.stages.validation_stage import ValidationStage
from app.services.processing.stages.persistence_stage import PersistenceStage

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger("processing.pipeline")


class ProcessingPipeline:
    """Orchestrates the full document processing pipeline:
    Upload → Normalize → OCR → AI Classification → Validation → Result

    This class is now a thin orchestrator that delegates to individual stages.
    The public API (process_document) remains unchanged.
    """

    # Class-level singletons for heavy/stateless services (used as defaults)
    _ocr_engine = PaddleOCREngine()
    _preprocessor = DocumentPreprocessor()
    _confidence_evaluator = OCRConfidenceEvaluator()
    _ai_classifier = AIClassifier()
    _ownership_validator = OwnershipValidator()
    _normalizer = DocumentNormalizer()
    _splitter = DocumentSplitter()

    def __init__(
        self,
        db: AsyncSession,
        *,
        ocr_engine: Optional[PaddleOCREngine] = None,
        preprocessor: Optional[DocumentPreprocessor] = None,
        confidence_evaluator: Optional[OCRConfidenceEvaluator] = None,
        ai_classifier: Optional[AIClassifier] = None,
        ownership_validator: Optional[OwnershipValidator] = None,
        normalizer: Optional[DocumentNormalizer] = None,
        splitter: Optional[DocumentSplitter] = None,
        audit_service: Optional[AuditService] = None,
    ):
        self.db = db
        self.ocr_engine = ocr_engine or self._ocr_engine
        self.preprocessor = preprocessor or self._preprocessor
        self.confidence_evaluator = confidence_evaluator or self._confidence_evaluator
        self.ai_classifier = ai_classifier or self._ai_classifier
        self.ownership_validator = ownership_validator or self._ownership_validator
        self.normalizer = normalizer or self._normalizer
        self.splitter = splitter or self._splitter
        self.audit = audit_service or AuditService(db)

        # Initialize stages
        self._normalization_stage = NormalizationStage(db, self.normalizer, self.audit)
        self._ocr_stage = OCRStage(db, self.ocr_engine, self.preprocessor, self.audit)
        self._classification_stage = ClassificationStage(db, self.ai_classifier, self.audit)
        self._validation_stage = ValidationStage(db, self.ownership_validator, self.audit)
        self._persistence_stage = PersistenceStage(db, self.audit)

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

        # Build context
        ctx = PipelineContext(
            document_id=document_id,
            document=document,
            correlation_id=correlation_id,
        )

        try:
            # Stage 1: Normalization
            await self._normalization_stage.execute(ctx)

            # Stage 2: OCR Processing
            await self._ocr_stage.execute(ctx)
            if ctx.should_stop:
                return

            # Stage 3: AI Classification
            await self._classification_stage.execute(ctx)

            # Stage 4: Ownership Validation
            await self._validation_stage.execute(ctx)

            # Stage 5: Final persistence
            await self._persistence_stage.execute(ctx, start_time)

        except Exception as e:
            await self._persistence_stage.execute_failure(ctx, e)

            await self.db.flush()
