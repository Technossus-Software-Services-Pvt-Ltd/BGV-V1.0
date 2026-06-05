"""Tests for FileNamingRuleService and OCR preprocessor."""

import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.settings.file_naming_service import (
    FileNamingRuleService,
    DEFAULT_FOLDER_STRUCTURE_PATTERN,
    DEFAULT_FILE_RENAME_PATTERN,
)
from app.services.ocr.preprocessor import DocumentPreprocessor


class TestBuildExampleOutput:
    def test_default_patterns(self):
        result = FileNamingRuleService.build_example_output(
            DEFAULT_FOLDER_STRUCTURE_PATTERN,
            DEFAULT_FILE_RENAME_PATTERN,
        )
        assert "BVA-0042" in result
        assert "Ravi" in result
        assert "Aadhaar" in result
        assert result.endswith(".pdf")

    def test_custom_patterns(self):
        result = FileNamingRuleService.build_example_output(
            "{FirstName}_{Date}",
            "{DocType}_{CandidateID}",
        )
        assert result == "Ravi_20260530/Aadhaar_BVA-0042.pdf"


class TestResolveFolderName:
    def test_basic_resolution(self):
        result = FileNamingRuleService.resolve_folder_name(
            "{CandidateID}_{FirstName}_{Date}",
            candidate_id="BVA-100",
            candidate_name="Ravi Kumar",
            batch_date=datetime(2025, 6, 15, tzinfo=timezone.utc),
        )
        assert result == "BVA-100_Ravi_20250615"

    def test_empty_pattern_uses_default(self):
        result = FileNamingRuleService.resolve_folder_name(
            "",
            candidate_id="BVA-100",
            candidate_name="Ravi Kumar",
        )
        assert "BVA-100" in result
        assert "Ravi" in result

    def test_sanitizes_dangerous_chars(self):
        result = FileNamingRuleService.resolve_folder_name(
            "{CandidateID}:{FirstName}",
            candidate_id="BVA/100",
            candidate_name="Test<Name>",
        )
        # Colons, slashes, angle brackets should be replaced
        assert ":" not in result
        assert "<" not in result
        assert ">" not in result

    def test_no_candidate_name(self):
        result = FileNamingRuleService.resolve_folder_name(
            "{CandidateID}_{FirstName}",
            candidate_id="BVA-1",
            candidate_name="",
        )
        assert "Unknown" in result


class TestResolveFileName:
    def test_basic_resolution(self):
        result = FileNamingRuleService.resolve_file_name(
            "{CandidateID}_{FirstName}_{DocType}",
            candidate_id="BVA-100",
            candidate_name="Ravi Kumar",
            document_type="Aadhaar",
            original_filename="scan.pdf",
        )
        assert result == "BVA-100_Ravi_Aadhaar.pdf"

    def test_preserves_extension(self):
        result = FileNamingRuleService.resolve_file_name(
            "{DocType}",
            candidate_id="X",
            candidate_name="Test",
            document_type="PAN",
            original_filename="photo.jpg",
        )
        assert result.endswith(".jpg")

    def test_empty_pattern_uses_default(self):
        result = FileNamingRuleService.resolve_file_name(
            "",
            candidate_id="BVA-1",
            candidate_name="Test User",
            document_type="Passport",
            original_filename="doc.pdf",
        )
        assert "BVA-1" in result
        assert "Passport" in result

    def test_no_document_type(self):
        result = FileNamingRuleService.resolve_file_name(
            "{DocType}",
            candidate_id="X",
            candidate_name="Test",
            document_type="",
            original_filename="doc.pdf",
        )
        assert "Document" in result


class TestGetActiveRule:
    @pytest.mark.asyncio
    async def test_returns_existing_rule(self):
        db = AsyncMock()
        existing_rule = MagicMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.first.return_value = existing_rule
        db.execute.return_value = result_mock

        rule = await FileNamingRuleService.get_active_rule(db)
        assert rule is existing_rule

    @pytest.mark.asyncio
    async def test_creates_default_rule_when_none_exists(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.first.return_value = None
        db.execute.return_value = result_mock

        rule = await FileNamingRuleService.get_active_rule(db)
        db.add.assert_called_once()
        db.commit.assert_called_once()


class TestSaveRule:
    @pytest.mark.asyncio
    async def test_updates_existing_rule(self):
        db = AsyncMock()
        existing = MagicMock()
        existing.folder_structure_pattern = "old"
        existing.file_rename_pattern = "old"
        existing.is_active = True

        with patch.object(FileNamingRuleService, "get_active_rule", return_value=existing):
            result = await FileNamingRuleService.save_rule(
                db, "{CandidateID}", "{DocType}"
            )

        assert existing.folder_structure_pattern == "{CandidateID}"
        assert existing.file_rename_pattern == "{DocType}"
        db.commit.assert_called_once()


class TestDocumentPreprocessorPages:
    def test_extract_pages_from_pdf(self, tmp_path):
        """Test PDF extraction with a mock fitz module."""
        preprocessor = DocumentPreprocessor()
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with patch("app.services.ocr.preprocessor.fitz") as mock_fitz:
            mock_doc = MagicMock()
            mock_doc.__len__ = lambda self: 2
            mock_doc.__iter__ = lambda self: iter(range(2))

            mock_page = MagicMock()
            mock_pixmap = MagicMock()
            mock_doc.__getitem__ = lambda self, idx: mock_page
            mock_page.get_pixmap.return_value = mock_pixmap
            mock_pixmap.save = MagicMock()

            mock_fitz.open.return_value = mock_doc
            mock_fitz.Matrix.return_value = MagicMock()

            pages = preprocessor.extract_pages_from_pdf(Path("/tmp/test.pdf"), output_dir)

        assert len(pages) == 2
        assert all(str(p).endswith(".png") for p in pages)

    def test_normalize_image(self, tmp_path):
        """Test image normalization with a real numpy array."""
        preprocessor = DocumentPreprocessor()

        # Create a small test image
        img_path = tmp_path / "test.png"
        from PIL import Image
        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img.save(str(img_path))

        result_array, metadata = preprocessor.normalize_image(img_path)

        assert isinstance(result_array, np.ndarray)
        assert result_array.shape[2] == 3  # RGB
        assert metadata["original_width"] == 100
        assert metadata["original_height"] == 100
        assert metadata["denoised"] is True

    def test_normalize_image_large_resize(self, tmp_path):
        """Test that large images are resized."""
        preprocessor = DocumentPreprocessor()

        img_path = tmp_path / "large.png"
        from PIL import Image
        img = Image.new("RGB", (5000, 5000), color=(128, 128, 128))
        img.save(str(img_path))

        result_array, metadata = preprocessor.normalize_image(img_path)

        # Should have been resized to fit MAX_DIMENSION
        assert max(result_array.shape[:2]) <= preprocessor.MAX_DIMENSION

    def test_normalize_image_grayscale_converted(self, tmp_path):
        """Test that grayscale images are converted to RGB."""
        preprocessor = DocumentPreprocessor()

        img_path = tmp_path / "gray.png"
        from PIL import Image
        img = Image.new("L", (100, 100), color=128)
        img.save(str(img_path))

        result_array, metadata = preprocessor.normalize_image(img_path)

        assert result_array.shape[2] == 3  # Converted to RGB
        assert metadata["original_mode"] == "L"
