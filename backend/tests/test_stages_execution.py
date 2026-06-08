"""Tests for pipeline stage execution logic."""

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.processing.stages.context import PipelineContext
from app.services.processing.stages.normalization_stage import NormalizationStage
from app.services.processing.stages.ocr_stage import OCRStage
from app.services.processing.stages.classification_stage import ClassificationStage
from app.services.processing.stages.validation_stage import ValidationStage
from app.services.processing.stages.persistence_stage import PersistenceStage
from app.models.enums import ProcessingStatus


def _make_ctx(**overrides):
    defaults = dict(
        document=MagicMock(
            id="doc-1",
            file_path="/tmp/test.pdf",
            mime_type="application/pdf",
            candidate_id="cand-1",
            processing_status=ProcessingStatus.PENDING.value,
            total_pages=0,
            is_multi_page=False,
        ),
        document_id="doc-1",
        correlation_id="corr-1",
        pages=[],
        should_stop=False,
        stop_reason=None,
        all_ocr_text=[],
        all_confidences=[],
        combined_text="",
        avg_confidence=0.0,
        full_classification=None,
    )
    defaults.update(overrides)
    ctx = PipelineContext(**defaults)
    return ctx


class TestNormalizationStageExecution:
    @pytest.mark.asyncio
    async def test_execute_extracts_pages_and_creates_records(self):
        db = AsyncMock()
        normalizer = MagicMock()
        normalizer.get_document_dir.return_value = Path("/tmp/docs/doc-1")
        normalizer.extract_pages.return_value = [
            Path("/tmp/docs/doc-1/page_0001.png"),
            Path("/tmp/docs/doc-1/page_0002.png"),
        ]
        audit = AsyncMock()
        audit.record_processing_event = AsyncMock()

        stage = NormalizationStage(db=db, normalizer=normalizer, audit=audit)
        ctx = _make_ctx()

        await stage.execute(ctx)

        assert ctx.document.total_pages == 2
        assert ctx.document.is_multi_page is True
        assert len(ctx.pages) == 2
        assert db.add.call_count == 2
        db.flush.assert_called()

    @pytest.mark.asyncio
    async def test_execute_single_page_document(self):
        db = AsyncMock()
        normalizer = MagicMock()
        normalizer.get_document_dir.return_value = Path("/tmp/docs/doc-1")
        normalizer.extract_pages.return_value = [Path("/tmp/docs/doc-1/page_0001.png")]
        audit = AsyncMock()
        audit.record_processing_event = AsyncMock()

        stage = NormalizationStage(db=db, normalizer=normalizer, audit=audit)
        ctx = _make_ctx()

        await stage.execute(ctx)

        assert ctx.document.total_pages == 1
        assert ctx.document.is_multi_page is False
        assert len(ctx.pages) == 1


class TestOCRStageExecution:
    @pytest.mark.asyncio
    async def test_execute_successful_ocr(self):
        db = AsyncMock()
        ocr_engine = MagicMock()
        preprocessor = MagicMock()
        audit = AsyncMock()
        audit.log = AsyncMock()

        stage = OCRStage(db=db, ocr_engine=ocr_engine, preprocessor=preprocessor, audit=audit)

        # Mock _process_page_ocr
        mock_ocr_result = MagicMock()
        mock_ocr_result.extracted_text = "Hello World"
        mock_ocr_result.confidence_score = 0.95
        stage._process_page_ocr = AsyncMock(return_value=mock_ocr_result)

        page = MagicMock(page_number=1)
        ctx = _make_ctx(pages=[page])

        await stage.execute(ctx)

        assert ctx.should_stop is False
        assert ctx.combined_text == "Hello World"
        assert ctx.avg_confidence == 0.95
        assert ctx.all_ocr_text == ["Hello World"]

    @pytest.mark.asyncio
    async def test_execute_no_text_sets_should_stop(self):
        db = AsyncMock()
        ocr_engine = MagicMock()
        preprocessor = MagicMock()
        audit = AsyncMock()
        audit.log = AsyncMock()

        stage = OCRStage(db=db, ocr_engine=ocr_engine, preprocessor=preprocessor, audit=audit)
        stage._process_page_ocr = AsyncMock(return_value=None)
        stage._handle_no_text = AsyncMock()

        page = MagicMock(page_number=1)
        ctx = _make_ctx(pages=[page])

        await stage.execute(ctx)

        assert ctx.should_stop is True
        assert ctx.stop_reason == "no_ocr_text"

    @pytest.mark.asyncio
    async def test_execute_multiple_pages(self):
        db = AsyncMock()
        ocr_engine = MagicMock()
        preprocessor = MagicMock()
        audit = AsyncMock()
        audit.log = AsyncMock()

        stage = OCRStage(db=db, ocr_engine=ocr_engine, preprocessor=preprocessor, audit=audit)

        results = [MagicMock(extracted_text="Page 1", confidence_score=0.9),
                   MagicMock(extracted_text="Page 2", confidence_score=0.8)]
        stage._process_page_ocr = AsyncMock(side_effect=results)

        pages = [MagicMock(page_number=1), MagicMock(page_number=2)]
        ctx = _make_ctx(pages=pages)

        await stage.execute(ctx)

        assert len(ctx.all_ocr_text) == 2
        assert ctx.avg_confidence == pytest.approx(0.85)
        assert "---PAGE BREAK---" in ctx.combined_text


class TestClassificationStageExecution:
    @pytest.mark.asyncio
    async def test_execute_classifies_pages(self):
        db = AsyncMock()
        ai_classifier = AsyncMock()
        audit = AsyncMock()
        audit.log = AsyncMock()

        stage = ClassificationStage(db=db, ai_classifier=ai_classifier, audit=audit)

        mock_classification = MagicMock(document_type="aadhaar_card", confidence_score=0.92)
        stage._classify_page = AsyncMock(return_value=mock_classification)
        stage._classify_full_document = AsyncMock(return_value=mock_classification)

        page = MagicMock(page_number=1)
        ctx = _make_ctx(pages=[page], combined_text="Some text")

        await stage.execute(ctx)

        stage._classify_page.assert_called_once()
        stage._classify_full_document.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_no_page_classifications(self):
        db = AsyncMock()
        ai_classifier = AsyncMock()
        audit = AsyncMock()
        audit.log = AsyncMock()

        stage = ClassificationStage(db=db, ai_classifier=ai_classifier, audit=audit)
        stage._classify_page = AsyncMock(return_value=None)
        stage._classify_full_document = AsyncMock(return_value=None)

        page = MagicMock(page_number=1)
        ctx = _make_ctx(pages=[page], combined_text="Some text")

        await stage.execute(ctx)

        # Should not crash even with no classifications
        stage._classify_page.assert_called_once()


class TestValidationStageExecution:
    @pytest.mark.asyncio
    async def test_execute_runs_validation(self):
        db = AsyncMock()
        ownership_validator = MagicMock()
        audit = AsyncMock()
        audit.log = AsyncMock()

        stage = ValidationStage(db=db, ownership_validator=ownership_validator, audit=audit)
        stage._validate_ownership = AsyncMock()

        classification = MagicMock()
        ctx = _make_ctx(full_classification=classification)

        await stage.execute(ctx)

        stage._validate_ownership.assert_called_once()
        assert ctx.document.processing_status == ProcessingStatus.VALIDATION_COMPLETE.value

    @pytest.mark.asyncio
    async def test_execute_updates_status(self):
        db = AsyncMock()
        ownership_validator = MagicMock()
        audit = AsyncMock()
        audit.log = AsyncMock()

        stage = ValidationStage(db=db, ownership_validator=ownership_validator, audit=audit)
        stage._validate_ownership = AsyncMock()

        ctx = _make_ctx(full_classification=None)

        await stage.execute(ctx)

        # Should have set VALIDATING then VALIDATION_COMPLETE
        db.flush.assert_called()


class TestPersistenceStageExecution:
    @pytest.mark.asyncio
    async def test_execute_marks_completed(self):
        db = AsyncMock()
        audit = AsyncMock()
        audit.log = AsyncMock()
        audit.record_processing_event = AsyncMock()

        stage = PersistenceStage(db=db, audit=audit)
        stage._update_batch_progress = AsyncMock()
        ctx = _make_ctx()
        start_time = time.time() - 1.0  # 1 second ago

        await stage.execute(ctx, start_time=start_time)

        assert ctx.document.processing_status == ProcessingStatus.COMPLETED.value
        audit.log.assert_called_once()
        audit.record_processing_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_duration_tracked(self):
        db = AsyncMock()
        audit = AsyncMock()
        audit.log = AsyncMock()
        audit.record_processing_event = AsyncMock()

        stage = PersistenceStage(db=db, audit=audit)
        stage._update_batch_progress = AsyncMock()
        ctx = _make_ctx()
        start_time = time.time() - 2.5

        await stage.execute(ctx, start_time=start_time)

        call_kwargs = audit.log.call_args.kwargs
        assert call_kwargs["duration_ms"] >= 2400
