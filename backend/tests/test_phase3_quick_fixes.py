"""Tests for Phase 3: PDF page limit, per-page OCR timeout, blank page skip."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import dataclass

import pytest
import numpy as np


# ─── PDF Page Limit Tests ───────────────────────────────────────────────────────


class TestPdfPageLimit:
    """Tests for max_pdf_pages configuration in DocumentPreprocessor."""

    @patch("app.services.ocr.preprocessor.settings")
    @patch("app.services.ocr.preprocessor.fitz")
    def test_extracts_all_pages_when_under_limit(self, mock_fitz, mock_settings):
        """When PDF has fewer pages than limit, all are extracted."""
        from app.services.ocr.preprocessor import DocumentPreprocessor

        mock_settings.max_pdf_pages = 50

        # Mock a 3-page PDF
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 3
        mock_fitz.open.return_value = mock_doc

        mock_page = MagicMock()
        mock_pixmap = MagicMock()
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_doc.__getitem__ = lambda self, idx: mock_page

        mock_fitz.Matrix.return_value = MagicMock()

        preprocessor = DocumentPreprocessor()
        output_dir = MagicMock(spec=Path)
        output_dir.__truediv__ = lambda self, name: MagicMock(spec=Path)

        result = preprocessor.extract_pages_from_pdf(Path("test.pdf"), output_dir)
        assert len(result) == 3

    @patch("app.services.ocr.preprocessor.settings")
    @patch("app.services.ocr.preprocessor.fitz")
    def test_truncates_pages_at_limit(self, mock_fitz, mock_settings):
        """When PDF has more pages than limit, only max_pdf_pages are extracted."""
        from app.services.ocr.preprocessor import DocumentPreprocessor

        mock_settings.max_pdf_pages = 5

        # Mock a 100-page PDF
        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 100
        mock_fitz.open.return_value = mock_doc

        mock_page = MagicMock()
        mock_pixmap = MagicMock()
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_doc.__getitem__ = lambda self, idx: mock_page

        mock_fitz.Matrix.return_value = MagicMock()

        preprocessor = DocumentPreprocessor()
        output_dir = MagicMock(spec=Path)
        output_dir.__truediv__ = lambda self, name: MagicMock(spec=Path)

        result = preprocessor.extract_pages_from_pdf(Path("test.pdf"), output_dir)
        assert len(result) == 5

    @patch("app.services.ocr.preprocessor.settings")
    @patch("app.services.ocr.preprocessor.fitz")
    def test_exactly_at_limit(self, mock_fitz, mock_settings):
        """When PDF page count equals limit, all pages are extracted."""
        from app.services.ocr.preprocessor import DocumentPreprocessor

        mock_settings.max_pdf_pages = 10

        mock_doc = MagicMock()
        mock_doc.__len__ = lambda self: 10
        mock_fitz.open.return_value = mock_doc

        mock_page = MagicMock()
        mock_pixmap = MagicMock()
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_doc.__getitem__ = lambda self, idx: mock_page

        mock_fitz.Matrix.return_value = MagicMock()

        preprocessor = DocumentPreprocessor()
        output_dir = MagicMock(spec=Path)
        output_dir.__truediv__ = lambda self, name: MagicMock(spec=Path)

        result = preprocessor.extract_pages_from_pdf(Path("test.pdf"), output_dir)
        assert len(result) == 10


# ─── Per-Page OCR Timeout Tests ─────────────────────────────────────────────────


class TestOcrPageTimeout:
    """Tests for per-page OCR timeout in OCRStage."""

    @pytest.fixture
    def ocr_stage(self):
        """Build OCRStage with mocked dependencies."""
        from app.services.processing.stages.ocr_stage import OCRStage

        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        ocr_engine = MagicMock()
        preprocessor = MagicMock()
        audit = AsyncMock()
        audit.record_processing_event = AsyncMock()

        stage = OCRStage(db=db, ocr_engine=ocr_engine, preprocessor=preprocessor, audit=audit)
        return stage

    @pytest.fixture
    def mock_page(self):
        page = MagicMock()
        page.id = "page-001"
        page.file_path = "/tmp/test/page_0001.png"
        page.processing_status = "pending"
        return page

    @pytest.fixture
    def mock_document(self):
        doc = MagicMock()
        doc.id = "doc-001"
        doc.mime_type = "application/pdf"
        return doc

    @pytest.mark.asyncio
    @patch("app.services.processing.stages.ocr_stage.settings")
    async def test_ocr_timeout_returns_error_record(self, mock_settings, ocr_stage, mock_page, mock_document):
        """When OCR exceeds page timeout, an error OCRResult is returned."""
        mock_settings.ocr_page_timeout_seconds = 1

        # Make normalize_image return valid data
        img_array = np.zeros((100, 100, 3), dtype=np.uint8)
        ocr_stage.preprocessor.normalize_image.return_value = (img_array, {"final_width": 100, "final_height": 100})
        ocr_stage.preprocessor.is_blank_page.return_value = False

        # Make OCR hang forever
        async def slow_ocr(*args, **kwargs):
            await asyncio.sleep(10)

        ocr_stage.ocr_engine.process_async = slow_ocr

        result = await ocr_stage._process_page_ocr(mock_document, mock_page, "corr-001")

        assert result is not None
        assert result.extracted_text == ""
        assert result.confidence_score == 0.0
        assert "timed out" in result.error_message
        assert mock_page.processing_status == "ocr_failed"

    @pytest.mark.asyncio
    @patch("app.services.processing.stages.ocr_stage.settings")
    async def test_ocr_completes_within_timeout(self, mock_settings, ocr_stage, mock_page, mock_document):
        """When OCR completes within timeout, result is returned normally."""
        mock_settings.ocr_page_timeout_seconds = 30

        img_array = np.zeros((100, 100, 3), dtype=np.uint8)
        ocr_stage.preprocessor.normalize_image.return_value = (img_array, {"final_width": 100, "final_height": 100})
        ocr_stage.preprocessor.is_blank_page.return_value = False

        @dataclass
        class FakeOCRResult:
            text: str = "Hello world"
            confidence: float = 0.95
            word_count: int = 2
            language_detected: str = "en"
            orientation_angle: float = 0.0
            processing_duration_ms: int = 500
            raw_output: list = None
            error: str = None

            def __post_init__(self):
                if self.raw_output is None:
                    self.raw_output = []

        async def fast_ocr(*args, **kwargs):
            return FakeOCRResult()

        ocr_stage.ocr_engine.process_async = fast_ocr

        result = await ocr_stage._process_page_ocr(mock_document, mock_page, "corr-001")

        assert result is not None
        assert result.extracted_text == "Hello world"
        assert result.confidence_score == 0.95
        assert mock_page.processing_status == "ocr_complete"


# ─── Blank Page Detection Tests ─────────────────────────────────────────────────


class TestBlankPageDetection:
    """Tests for blank page skip in preprocessor."""

    def test_blank_page_detected(self):
        """A nearly-all-white image should be detected as blank."""
        from app.services.ocr.preprocessor import DocumentPreprocessor

        preprocessor = DocumentPreprocessor()
        # Create 99% white image
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        assert preprocessor.is_blank_page(img) == True

    def test_content_page_not_blank(self):
        """An image with significant content should not be blank."""
        from app.services.ocr.preprocessor import DocumentPreprocessor

        preprocessor = DocumentPreprocessor()
        # Create image with 50% dark pixels
        img = np.full((100, 100, 3), 128, dtype=np.uint8)
        assert preprocessor.is_blank_page(img) == False

    def test_threshold_boundary(self):
        """Image at exactly the threshold should be detected as blank."""
        from app.services.ocr.preprocessor import DocumentPreprocessor

        preprocessor = DocumentPreprocessor()
        # 99% white (above 0.98 threshold)
        img = np.full((100, 100, 3), 255, dtype=np.uint8)
        img[:1, :, :] = 0  # Only 1% dark
        assert preprocessor.is_blank_page(img) == True

    def test_grayscale_blank(self):
        """Grayscale blank image should also be detected."""
        from app.services.ocr.preprocessor import DocumentPreprocessor

        preprocessor = DocumentPreprocessor()
        img = np.full((100, 100), 255, dtype=np.uint8)
        assert preprocessor.is_blank_page(img) == True


# ─── Config Tests ────────────────────────────────────────────────────────────────


class TestPhase3Config:
    """Tests for new Phase 3 config settings."""

    def test_max_pdf_pages_default(self):
        from app.core.config import Settings
        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            database_sync_url="postgresql://u:p@localhost/db",
            secret_key="test-secret-key-for-unit-testing-only",
        )
        assert s.max_pdf_pages == 50

    def test_ocr_page_timeout_default(self):
        from app.core.config import Settings
        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            database_sync_url="postgresql://u:p@localhost/db",
            secret_key="test-secret-key-for-unit-testing-only",
        )
        assert s.ocr_page_timeout_seconds == 30
