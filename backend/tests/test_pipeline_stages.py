"""Tests for pipeline stages (Phase 2).

Verifies that:
1. PipelineContext carries state correctly
2. Each stage can be instantiated independently
3. Pipeline orchestrator delegates to stages correctly
4. Stages respect ctx.should_stop signal
5. Public API (process_document) remains unchanged
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import fields as dataclass_fields

from app.services.processing.stages.context import PipelineContext
from app.services.processing.stages.normalization_stage import NormalizationStage
from app.services.processing.stages.ocr_stage import OCRStage
from app.services.processing.stages.classification_stage import ClassificationStage
from app.services.processing.stages.validation_stage import ValidationStage
from app.services.processing.stages.persistence_stage import PersistenceStage


class TestPipelineContext:
    """Verify PipelineContext dataclass."""

    def test_context_creation_with_minimal_fields(self):
        ctx = PipelineContext(document_id="doc-123")
        assert ctx.document_id == "doc-123"
        assert ctx.document is None
        assert ctx.pages == []
        assert ctx.all_ocr_text == []
        assert ctx.combined_text == ""
        assert ctx.avg_confidence == 0.0
        assert ctx.page_classifications == []
        assert ctx.full_classification is None
        assert ctx.should_stop is False

    def test_context_is_mutable(self):
        ctx = PipelineContext(document_id="doc-123")
        ctx.combined_text = "Hello world"
        ctx.avg_confidence = 0.95
        ctx.should_stop = True
        assert ctx.combined_text == "Hello world"
        assert ctx.avg_confidence == 0.95
        assert ctx.should_stop is True

    def test_context_lists_are_independent(self):
        """Each context instance should have its own lists."""
        ctx1 = PipelineContext(document_id="doc-1")
        ctx2 = PipelineContext(document_id="doc-2")
        ctx1.all_ocr_text.append("text")
        assert ctx2.all_ocr_text == []


class TestNormalizationStage:
    """Verify NormalizationStage can be instantiated."""

    def test_instantiation(self):
        mock_db = MagicMock()
        mock_normalizer = MagicMock()
        mock_audit = MagicMock()
        stage = NormalizationStage(mock_db, mock_normalizer, mock_audit)
        assert stage.db is mock_db
        assert stage.normalizer is mock_normalizer
        assert stage.audit is mock_audit


class TestOCRStage:
    """Verify OCRStage can be instantiated."""

    def test_instantiation(self):
        mock_db = MagicMock()
        mock_engine = MagicMock()
        mock_preprocessor = MagicMock()
        mock_audit = MagicMock()
        stage = OCRStage(mock_db, mock_engine, mock_preprocessor, mock_audit)
        assert stage.db is mock_db
        assert stage.ocr_engine is mock_engine
        assert stage.preprocessor is mock_preprocessor
        assert stage.audit is mock_audit


class TestClassificationStage:
    """Verify ClassificationStage can be instantiated."""

    def test_instantiation(self):
        mock_db = MagicMock()
        mock_classifier = MagicMock()
        mock_audit = MagicMock()
        stage = ClassificationStage(mock_db, mock_classifier, mock_audit)
        assert stage.db is mock_db
        assert stage.ai_classifier is mock_classifier
        assert stage.audit is mock_audit


class TestValidationStage:
    """Verify ValidationStage can be instantiated."""

    def test_instantiation(self):
        mock_db = MagicMock()
        mock_validator = MagicMock()
        mock_audit = MagicMock()
        stage = ValidationStage(mock_db, mock_validator, mock_audit)
        assert stage.db is mock_db
        assert stage.ownership_validator is mock_validator
        assert stage.audit is mock_audit


class TestPersistenceStage:
    """Verify PersistenceStage can be instantiated."""

    def test_instantiation(self):
        mock_db = MagicMock()
        mock_audit = MagicMock()
        stage = PersistenceStage(mock_db, mock_audit)
        assert stage.db is mock_db
        assert stage.audit is mock_audit


class TestPipelineOrchestratorStructure:
    """Verify the refactored ProcessingPipeline has correct stage structure."""

    def test_pipeline_creates_all_stages(self):
        mock_db = MagicMock()
        from app.services.processing.pipeline import ProcessingPipeline
        from app.services.dependencies import get_processing_pipeline

        pipeline = get_processing_pipeline(mock_db)
        assert isinstance(pipeline._normalization_stage, NormalizationStage)
        assert isinstance(pipeline._ocr_stage, OCRStage)
        assert isinstance(pipeline._classification_stage, ClassificationStage)
        assert isinstance(pipeline._validation_stage, ValidationStage)
        assert isinstance(pipeline._persistence_stage, PersistenceStage)

    def test_pipeline_passes_injected_deps_to_stages(self):
        """Injected dependencies flow through to stages."""
        mock_db = MagicMock()
        mock_ocr = MagicMock()
        mock_preprocessor = MagicMock()
        mock_classifier = MagicMock()
        mock_validator = MagicMock()
        mock_normalizer = MagicMock()
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
            splitter=MagicMock(),
            audit_service=mock_audit,
        )

        # Verify stages got the right dependencies
        assert pipeline._normalization_stage.normalizer is mock_normalizer
        assert pipeline._normalization_stage.audit is mock_audit
        assert pipeline._ocr_stage.ocr_engine is mock_ocr
        assert pipeline._ocr_stage.preprocessor is mock_preprocessor
        assert pipeline._ocr_stage.audit is mock_audit
        assert pipeline._classification_stage.ai_classifier is mock_classifier
        assert pipeline._classification_stage.audit is mock_audit
        assert pipeline._validation_stage.ownership_validator is mock_validator
        assert pipeline._validation_stage.audit is mock_audit
        assert pipeline._persistence_stage.audit is mock_audit

    def test_pipeline_public_api_unchanged(self):
        """process_document is still the main entry point."""
        mock_db = MagicMock()
        from app.services.processing.pipeline import ProcessingPipeline
        from app.services.dependencies import get_processing_pipeline

        pipeline = get_processing_pipeline(mock_db)
        assert hasattr(pipeline, "process_document")
        assert callable(pipeline.process_document)


class TestPipelineStopSignal:
    """Verify the pipeline respects ctx.should_stop."""

    @pytest.mark.asyncio
    async def test_pipeline_stops_after_ocr_if_no_text(self):
        """If OCR produces no text, later stages should not execute."""
        mock_db = MagicMock()
        mock_db.execute = AsyncMock()
        mock_db.flush = AsyncMock()

        # Mock document lookup
        mock_document = MagicMock()
        mock_document.id = "doc-1"
        mock_document.correlation_id = "corr-1"
        mock_document.original_filename = "test.pdf"
        mock_document.file_path = "/tmp/test.pdf"
        mock_document.upload_batch_id = "batch-1"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_document
        mock_db.execute.return_value = mock_result

        from app.services.processing.pipeline import ProcessingPipeline
        from app.services.dependencies import get_processing_pipeline

        pipeline = get_processing_pipeline(mock_db)

        # Mock stages
        pipeline._normalization_stage.execute = AsyncMock()
        pipeline._ocr_stage.execute = AsyncMock(
            side_effect=lambda ctx: setattr(ctx, "should_stop", True)
        )
        pipeline._classification_stage.execute = AsyncMock()
        pipeline._validation_stage.execute = AsyncMock()
        pipeline._persistence_stage.execute = AsyncMock()

        await pipeline.process_document("doc-1")

        # Normalization and OCR should have been called
        pipeline._normalization_stage.execute.assert_called_once()
        pipeline._ocr_stage.execute.assert_called_once()

        # Classification and validation should NOT have been called
        pipeline._classification_stage.execute.assert_not_called()
        pipeline._validation_stage.execute.assert_not_called()
        pipeline._persistence_stage.execute.assert_not_called()
