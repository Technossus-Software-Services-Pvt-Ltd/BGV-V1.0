"""FastAPI dependency injection providers.

Provides factory functions that create service instances with their
dependencies properly wired. Routes use these via `Depends(...)`.

All providers return protocol types (not concrete classes) to enforce
loose coupling. Consumers depend on interfaces, not implementations.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.ocr.engine import PaddleOCREngine
from app.services.ocr.preprocessor import DocumentPreprocessor
from app.services.ocr.confidence import OCRConfidenceEvaluator
from app.services.ai.classifier import AIClassifier
from app.services.validation.ownership import OwnershipValidator
from app.services.processing.normalizer import DocumentNormalizer
from app.services.processing.splitter import DocumentSplitter
from app.services.audit.logger import AuditService
from app.services.websocket.hub import ws_hub
from app.services.protocols import (
    OCREngine,
    DocumentPreprocessorProtocol,
    AIClassifierProtocol,
    OwnershipValidatorProtocol,
    AuditServiceProtocol,
    WebSocketHubProtocol,
)


# ---------------------------------------------------------------------------
# Singleton instances (stateless / thread-safe services reused across requests)
# These match the previous class-level singletons in ProcessingPipeline.
# ---------------------------------------------------------------------------

_ocr_engine = PaddleOCREngine()
_preprocessor = DocumentPreprocessor()
_confidence_evaluator = OCRConfidenceEvaluator()
_ai_classifier = AIClassifier()
_ownership_validator = OwnershipValidator()
_normalizer = DocumentNormalizer()
_splitter = DocumentSplitter()


# ---------------------------------------------------------------------------
# Accessor functions (for use without FastAPI Depends)
# ---------------------------------------------------------------------------


def get_ocr_engine() -> "OCREngine":
    """Return the shared OCR engine instance."""
    return _ocr_engine


def get_preprocessor() -> "DocumentPreprocessorProtocol":
    """Return the shared document preprocessor instance."""
    return _preprocessor


def get_confidence_evaluator() -> OCRConfidenceEvaluator:
    """Return the shared OCR confidence evaluator instance."""
    return _confidence_evaluator


def get_ai_classifier() -> "AIClassifierProtocol":
    """Return the shared AI classifier instance."""
    return _ai_classifier


def get_ownership_validator() -> "OwnershipValidatorProtocol":
    """Return the shared ownership validator instance."""
    return _ownership_validator


def get_normalizer() -> DocumentNormalizer:
    """Return the shared document normalizer instance."""
    return _normalizer


def get_splitter() -> DocumentSplitter:
    """Return the shared document splitter instance."""
    return _splitter


def get_ws_hub() -> "WebSocketHubProtocol":
    """Return the WebSocket hub singleton."""
    return ws_hub


# ---------------------------------------------------------------------------
# Session-scoped factories (create per-request instances)
# ---------------------------------------------------------------------------


def get_audit_service(db: AsyncSession) -> AuditService:
    """Create an AuditService bound to the given session."""
    return AuditService(db)


def get_processing_pipeline(db: AsyncSession):
    """Create a ProcessingPipeline with all dependencies injected."""
    from app.services.processing.pipeline import ProcessingPipeline

    return ProcessingPipeline(
        db=db,
        ocr_engine=_ocr_engine,
        preprocessor=_preprocessor,
        confidence_evaluator=_confidence_evaluator,
        ai_classifier=_ai_classifier,
        ownership_validator=_ownership_validator,
        normalizer=_normalizer,
        splitter=_splitter,
    )


def get_batch_orchestrator(db: AsyncSession):
    """Create a BatchOrchestrator with all dependencies injected."""
    from app.services.batch.orchestrator import BatchOrchestrator

    return BatchOrchestrator(
        db=db,
        ws_hub=ws_hub,
    )
