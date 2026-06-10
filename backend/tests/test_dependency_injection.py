"""Tests for dependency injection infrastructure (Phase 1).

Verifies that:
1. Protocols define correct interfaces
2. Concrete implementations satisfy protocols
3. ProcessingPipeline accepts injected dependencies
4. BatchOrchestrator accepts injected dependencies
5. AIClassifier accepts injected client
6. Default behavior is preserved when no DI params provided
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.protocols import (
    OCREngine,
    AIClassifierProtocol,
    OwnershipValidatorProtocol,
    AuditServiceProtocol,
    WebSocketHubProtocol,
    DocumentNormalizerProtocol,
    DocumentPreprocessorProtocol,
)
from app.services.dependencies import (
    get_ocr_engine,
    get_preprocessor,
    get_ai_classifier,
    get_ownership_validator,
    get_normalizer,
    get_splitter,
    get_ws_hub,
    get_processing_pipeline,
    get_batch_orchestrator,
)


class TestProtocolCompliance:
    """Verify that concrete implementations satisfy their protocols."""

    def test_ocr_engine_satisfies_protocol(self):
        from app.services.ocr.engine import PaddleOCREngine

        engine = PaddleOCREngine()
        assert isinstance(engine, OCREngine)

    def test_ai_classifier_satisfies_protocol(self):
        from app.services.ai.classifier import AIClassifier

        classifier = AIClassifier()
        assert isinstance(classifier, AIClassifierProtocol)

    def test_ownership_validator_satisfies_protocol(self):
        from app.services.validation.ownership import OwnershipValidator

        validator = OwnershipValidator()
        assert isinstance(validator, OwnershipValidatorProtocol)

    def test_websocket_hub_satisfies_protocol(self):
        from app.services.websocket.hub import WebSocketHub

        hub = WebSocketHub()
        assert isinstance(hub, WebSocketHubProtocol)

    def test_normalizer_satisfies_protocol(self):
        from app.services.processing.normalizer import DocumentNormalizer

        normalizer = DocumentNormalizer()
        assert isinstance(normalizer, DocumentNormalizerProtocol)

    def test_preprocessor_satisfies_protocol(self):
        from app.services.ocr.preprocessor import DocumentPreprocessor

        preprocessor = DocumentPreprocessor()
        assert isinstance(preprocessor, DocumentPreprocessorProtocol)


class TestDependencyProviders:
    """Verify that dependency providers return correct singleton instances."""

    def test_get_ocr_engine_returns_singleton(self):
        engine1 = get_ocr_engine()
        engine2 = get_ocr_engine()
        assert engine1 is engine2

    def test_get_preprocessor_returns_singleton(self):
        p1 = get_preprocessor()
        p2 = get_preprocessor()
        assert p1 is p2

    def test_get_ai_classifier_returns_singleton(self):
        c1 = get_ai_classifier()
        c2 = get_ai_classifier()
        assert c1 is c2

    def test_get_ownership_validator_returns_singleton(self):
        v1 = get_ownership_validator()
        v2 = get_ownership_validator()
        assert v1 is v2

    def test_get_normalizer_returns_singleton(self):
        n1 = get_normalizer()
        n2 = get_normalizer()
        assert n1 is n2

    def test_get_splitter_returns_singleton(self):
        s1 = get_splitter()
        s2 = get_splitter()
        assert s1 is s2

    def test_get_ws_hub_returns_singleton(self):
        h1 = get_ws_hub()
        h2 = get_ws_hub()
        assert h1 is h2


class TestProcessingPipelineDI:
    """Verify ProcessingPipeline constructor injection."""

    def test_default_construction_requires_services(self):
        """ProcessingPipeline requires all services to be passed explicitly."""
        mock_db = MagicMock()
        from app.services.processing.pipeline import ProcessingPipeline

        # Verify it works when all services are provided via factory
        from app.services.dependencies import get_processing_pipeline
        pipeline = get_processing_pipeline(mock_db)
        assert pipeline.db is mock_db
        assert pipeline.ocr_engine is not None
        assert pipeline.ai_classifier is not None
        assert pipeline.ownership_validator is not None
        assert pipeline.normalizer is not None
        assert pipeline.splitter is not None
        assert pipeline.audit is not None

    def test_injected_dependencies_are_used(self):
        """Injected services are used instead of defaults."""
        mock_db = MagicMock()
        mock_ocr = MagicMock()
        mock_classifier = MagicMock()
        mock_validator = MagicMock()
        mock_normalizer = MagicMock()
        mock_splitter = MagicMock()
        mock_preprocessor = MagicMock()
        mock_audit = MagicMock()

        from app.services.processing.pipeline import ProcessingPipeline

        pipeline = ProcessingPipeline(
            mock_db,
            ocr_engine=mock_ocr,
            preprocessor=mock_preprocessor,
            confidence_evaluator=MagicMock(),
            ai_classifier=mock_classifier,
            ownership_validator=mock_validator,
            normalizer=mock_normalizer,
            splitter=mock_splitter,
            audit_service=mock_audit,
        )

        assert pipeline.ocr_engine is mock_ocr
        assert pipeline.preprocessor is mock_preprocessor
        assert pipeline.ai_classifier is mock_classifier
        assert pipeline.ownership_validator is mock_validator
        assert pipeline.normalizer is mock_normalizer
        assert pipeline.splitter is mock_splitter
        assert pipeline.audit is mock_audit

    def test_get_processing_pipeline_factory(self):
        """Factory function creates pipeline with shared singletons."""
        mock_db = MagicMock()
        pipeline = get_processing_pipeline(mock_db)

        from app.services.processing.pipeline import ProcessingPipeline

        assert isinstance(pipeline, ProcessingPipeline)
        assert pipeline.db is mock_db
        # Should use shared singletons from dependencies module
        assert pipeline.ocr_engine is get_ocr_engine()
        assert pipeline.ai_classifier is get_ai_classifier()


class TestBatchOrchestratorDI:
    """Verify BatchOrchestrator constructor injection."""

    def test_default_construction_still_works(self):
        """Backward compat: BatchOrchestrator(db) still works."""
        mock_db = MagicMock()
        from app.services.batch.orchestrator import BatchOrchestrator

        orchestrator = BatchOrchestrator(mock_db)
        assert orchestrator.db is mock_db
        assert orchestrator._status._ws_hub is not None
        assert orchestrator.audit is not None

    def test_injected_ws_hub_is_used(self):
        """Injected WebSocket hub is used instead of default."""
        mock_db = MagicMock()
        mock_ws_hub = MagicMock()

        from app.services.batch.orchestrator import BatchOrchestrator

        orchestrator = BatchOrchestrator(mock_db, ws_hub=mock_ws_hub)
        assert orchestrator._status._ws_hub is mock_ws_hub

    def test_injected_pipeline_factory_is_used(self):
        """Injected pipeline factory is stored."""
        mock_db = MagicMock()
        mock_factory = MagicMock()

        from app.services.batch.orchestrator import BatchOrchestrator

        orchestrator = BatchOrchestrator(mock_db, pipeline_factory=mock_factory)
        assert orchestrator._pipeline_factory is mock_factory

    def test_get_batch_orchestrator_factory(self):
        """Factory function creates orchestrator with injected ws_hub."""
        mock_db = MagicMock()
        orchestrator = get_batch_orchestrator(mock_db)

        from app.services.batch.orchestrator import BatchOrchestrator

        assert isinstance(orchestrator, BatchOrchestrator)
        assert orchestrator.db is mock_db
        assert orchestrator._status._ws_hub is get_ws_hub()


class TestAIClassifierDI:
    """Verify AIClassifier constructor injection."""

    def test_default_construction_still_works(self):
        """Backward compat: AIClassifier() still works."""
        from app.services.ai.classifier import AIClassifier

        classifier = AIClassifier()
        assert classifier.client is not None

    def test_injected_client_is_used(self):
        """Injected OllamaClient is used instead of default."""
        mock_client = MagicMock()
        from app.services.ai.classifier import AIClassifier

        classifier = AIClassifier(client=mock_client)
        assert classifier.client is mock_client
