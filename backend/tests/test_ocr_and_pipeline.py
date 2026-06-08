"""Tests for OCR engine, preprocessor, pipeline stages, and processing services."""

import pytest
import asyncio
import numpy as np
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
from pathlib import Path

from app.services.ocr.engine import PaddleOCREngine, OCREngineResult
from app.services.processing.stages.context import PipelineContext


class TestOCREngineResult:
    def test_successful_result(self):
        result = OCREngineResult(
            text="Hello World",
            confidence=0.95,
            word_count=2,
            raw_output=[],
            processing_duration_ms=100,
        )
        assert result.is_successful is True

    def test_failed_result_with_error(self):
        result = OCREngineResult(
            text="",
            confidence=0.0,
            word_count=0,
            raw_output=[],
            processing_duration_ms=50,
            error="OCR engine crashed",
        )
        assert result.is_successful is False

    def test_failed_result_empty_text(self):
        result = OCREngineResult(
            text="   ",
            confidence=0.0,
            word_count=0,
            raw_output=[],
            processing_duration_ms=50,
        )
        assert result.is_successful is False


class TestPaddleOCREngine:
    def test_min_confidence_threshold(self):
        engine = PaddleOCREngine()
        assert engine.MIN_CONFIDENCE_THRESHOLD == 0.3

    @patch("app.services.ocr.engine._get_paddle_ocr")
    def test_process_empty_result(self, mock_get_ocr):
        """OCR returns empty results."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[]]
        mock_get_ocr.return_value = mock_ocr

        engine = PaddleOCREngine()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.process(img)
        assert result.text == ""
        assert result.word_count == 0
        assert result.confidence == 0.0

    @patch("app.services.ocr.engine._get_paddle_ocr")
    def test_process_with_results(self, mock_get_ocr):
        """OCR returns valid results."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[
            [[[0, 0], [100, 0], [100, 20], [0, 20]], ("Hello World", 0.95)],
            [[[0, 30], [100, 30], [100, 50], [0, 50]], ("Second Line", 0.88)],
        ]]
        mock_get_ocr.return_value = mock_ocr

        engine = PaddleOCREngine()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.process(img)
        assert "Hello World" in result.text
        assert "Second Line" in result.text
        assert result.word_count >= 4
        assert result.confidence > 0.8

    @patch("app.services.ocr.engine._get_paddle_ocr")
    def test_process_filters_low_confidence(self, mock_get_ocr):
        """Lines below threshold are filtered out."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = [[
            [[[0, 0], [100, 0], [100, 20], [0, 20]], ("Good", 0.95)],
            [[[0, 30], [100, 30], [100, 50], [0, 50]], ("Bad", 0.1)],  # Below threshold
        ]]
        mock_get_ocr.return_value = mock_ocr

        engine = PaddleOCREngine()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.process(img)
        assert "Good" in result.text
        assert "Bad" not in result.text

    @patch("app.services.ocr.engine._get_paddle_ocr")
    def test_process_none_result(self, mock_get_ocr):
        """OCR returns None."""
        mock_ocr = MagicMock()
        mock_ocr.ocr.return_value = None
        mock_get_ocr.return_value = mock_ocr

        engine = PaddleOCREngine()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = engine.process(img)
        assert result.text == ""
        assert result.word_count == 0


class TestOCRConfidence:
    def test_confidence_evaluator(self):
        from app.services.ocr.confidence import OCRConfidenceEvaluator
        evaluator = OCRConfidenceEvaluator()
        result = evaluator.evaluate(0.95, 50, "Hello world " * 25)
        assert result is not None
        assert result.is_reliable is True
        assert result.overall_score == 0.95

    def test_low_confidence(self):
        from app.services.ocr.confidence import OCRConfidenceEvaluator
        evaluator = OCRConfidenceEvaluator()
        result = evaluator.evaluate(0.3, 50, "text " * 50)
        assert result.is_reliable is False

    def test_insufficient_words(self):
        from app.services.ocr.confidence import OCRConfidenceEvaluator
        evaluator = OCRConfidenceEvaluator()
        result = evaluator.evaluate(0.95, 2, "hi")
        assert result.is_reliable is False
        assert "Insufficient" in result.recommendation

    def test_medium_confidence(self):
        from app.services.ocr.confidence import OCRConfidenceEvaluator
        evaluator = OCRConfidenceEvaluator()
        result = evaluator.evaluate(0.7, 20, "text " * 20)
        assert result.is_reliable is True
        assert result.low_confidence_regions == 1


class TestPipelineContextExtended:
    def test_default_values(self):
        ctx = PipelineContext(document_id="test-123")
        assert ctx.document_id == "test-123"
        assert ctx.should_stop is False
        assert ctx.pages == []
        assert ctx.all_ocr_text == []

    def test_mutation(self):
        ctx = PipelineContext(document_id="test-123")
        ctx.combined_text = "Hello"
        ctx.avg_confidence = 0.9
        ctx.should_stop = True
        assert ctx.combined_text == "Hello"
        assert ctx.should_stop is True


class TestProcessingPipeline:
    """Test processing pipeline orchestration."""

    @pytest.mark.asyncio
    async def test_pipeline_missing_document(self):
        """Pipeline should handle missing document gracefully."""
        from app.services.processing.pipeline import ProcessingPipeline

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        pipeline = ProcessingPipeline(db=mock_db)
        # Should not crash on missing document
        await pipeline.process_document("nonexistent-doc-id")


class TestProcessingSplitter:
    """Test document splitting logic."""

    def test_splitter_instantiation(self):
        from app.services.processing.splitter import DocumentSplitter
        splitter = DocumentSplitter()
        assert splitter is not None
