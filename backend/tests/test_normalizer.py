"""Tests for app.services.processing.normalizer module."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from app.services.processing.normalizer import DocumentNormalizer


class TestDocumentNormalizer:
    def setup_method(self):
        self.normalizer = DocumentNormalizer()

    def test_get_document_dir_creates_path(self, tmp_path, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
        doc_dir = self.normalizer.get_document_dir("corr-123", "doc-456")
        assert doc_dir.exists()
        assert "corr-123" in str(doc_dir)
        assert "doc-456" in str(doc_dir)

    def test_get_pages_dir_creates_path(self, tmp_path):
        pages_dir = self.normalizer.get_pages_dir(tmp_path)
        assert pages_dir.exists()
        assert pages_dir.name == "pages"

    def test_extract_pages_image(self, tmp_path):
        """Single image file should be copied as page 1."""
        # Create a fake image file
        img_file = tmp_path / "test.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0fake image data")

        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()

        pages = self.normalizer.extract_pages(img_file, doc_dir, "image/jpeg")
        assert len(pages) == 1
        assert pages[0].name == "page_0001.jpg"
        assert pages[0].exists()

    def test_extract_pages_png(self, tmp_path):
        """PNG image should be copied as page 1."""
        img_file = tmp_path / "scan.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\nfake png data")

        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()

        pages = self.normalizer.extract_pages(img_file, doc_dir, "image/png")
        assert len(pages) == 1
        assert pages[0].name == "page_0001.png"

    @patch("app.services.processing.normalizer.DocumentPreprocessor")
    def test_extract_pages_pdf_delegates_to_preprocessor(self, mock_preprocessor_cls, tmp_path):
        """PDF extraction should delegate to preprocessor."""
        mock_preprocessor = MagicMock()
        mock_preprocessor.extract_pages_from_pdf.return_value = [
            tmp_path / "page_0001.png",
            tmp_path / "page_0002.png",
        ]
        normalizer = DocumentNormalizer()
        normalizer.preprocessor = mock_preprocessor

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 content")
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()

        pages = normalizer.extract_pages(pdf_file, doc_dir, "application/pdf")
        assert len(pages) == 2
        mock_preprocessor.extract_pages_from_pdf.assert_called_once()
