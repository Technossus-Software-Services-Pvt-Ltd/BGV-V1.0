"""Tests for preprocessor, parser, discovery service, status service, and other utilities."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from app.services.ocr.preprocessor import DocumentPreprocessor
from app.services.batch.parser import parse_import_file, ParseError
from app.services.batch.discovery_service import DiscoveryService
from app.services.batch.status_service import BatchStatusService
from app.services.batch.checklist_matcher import ChecklistMatcher


# ─── DocumentPreprocessor ────────────────────────────────────────────────────


class TestDocumentPreprocessor:
    """Test DocumentPreprocessor methods."""

    def test_normalize_image_basic(self, tmp_path):
        """Test normalizing a simple RGB image."""
        img = Image.new("RGB", (200, 300), color=(128, 128, 128))
        img_path = tmp_path / "test.png"
        img.save(str(img_path))

        preprocessor = DocumentPreprocessor()
        result_array, metadata = preprocessor.normalize_image(img_path)

        assert isinstance(result_array, np.ndarray)
        assert result_array.shape[2] == 3  # RGB
        assert metadata["original_width"] == 200
        assert metadata["original_height"] == 300
        assert metadata["denoised"] is True

    def test_normalize_image_grayscale(self, tmp_path):
        """Test normalizing a grayscale image (should convert to RGB)."""
        img = Image.new("L", (100, 100), color=128)
        img_path = tmp_path / "gray.png"
        img.save(str(img_path))

        preprocessor = DocumentPreprocessor()
        result_array, metadata = preprocessor.normalize_image(img_path)

        assert result_array.shape[2] == 3  # Converted to RGB
        assert metadata["original_mode"] == "L"

    def test_normalize_image_oversized(self, tmp_path):
        """Test that oversized images get resized."""
        img = Image.new("RGB", (5000, 5000), color=(200, 200, 200))
        img_path = tmp_path / "big.png"
        img.save(str(img_path))

        preprocessor = DocumentPreprocessor()
        result_array, metadata = preprocessor.normalize_image(img_path)

        # Should be resized to MAX_DIMENSION
        assert result_array.shape[0] <= 4096
        assert result_array.shape[1] <= 4096

    def test_extract_pages_from_pdf(self, tmp_path):
        """Test PDF page extraction (using a minimal PDF)."""
        import fitz
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), "Hello World")
        pdf_path = tmp_path / "test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        preprocessor = DocumentPreprocessor()
        output_dir = tmp_path / "pages"
        output_dir.mkdir()
        pages = preprocessor.extract_pages_from_pdf(pdf_path, output_dir)

        assert len(pages) == 1
        assert pages[0].exists()

    def test_is_blank_page_white(self):
        """A fully white image should be detected as blank."""
        preprocessor = DocumentPreprocessor()
        white = np.full((100, 100, 3), 255, dtype=np.uint8)
        assert preprocessor.is_blank_page(white) == True

    def test_is_blank_page_with_content(self):
        """An image with content should not be blank."""
        preprocessor = DocumentPreprocessor()
        img = np.full((100, 100, 3), 128, dtype=np.uint8)  # Gray
        assert preprocessor.is_blank_page(img) == False

    def test_is_blank_page_grayscale(self):
        """Test blank detection on 2D array."""
        preprocessor = DocumentPreprocessor()
        white = np.full((100, 100), 250, dtype=np.uint8)
        assert preprocessor.is_blank_page(white) == True

    def test_fix_orientation_no_exif(self, tmp_path):
        """Image without EXIF should not be rotated."""
        preprocessor = DocumentPreprocessor()
        img = Image.new("RGB", (100, 200))
        result, was_rotated = preprocessor._fix_orientation(img)
        assert was_rotated is False

    def test_resize_if_needed_small_image(self):
        """Small images should not be resized."""
        preprocessor = DocumentPreprocessor()
        img = Image.new("RGB", (800, 600))
        result = preprocessor._resize_if_needed(img)
        assert result.width == 800
        assert result.height == 600

    def test_enhance_for_ocr(self):
        """Enhancement should not crash."""
        preprocessor = DocumentPreprocessor()
        img = Image.new("RGB", (100, 100), color=(100, 100, 100))
        result = preprocessor._enhance_for_ocr(img)
        assert result.size == (100, 100)


# ─── Parser ──────────────────────────────────────────────────────────────────


class TestParser:
    """Test parse_import_file."""

    def test_parse_csv_valid(self, tmp_path):
        csv_path = tmp_path / "test.csv"
        csv_path.write_text(
            "name,email,phone,candidate_id\n"
            "John Doe,john@test.com,1234567890,C001\n"
            "Jane Smith,jane@test.com,0987654321,C002\n"
        )

        candidates, errors = parse_import_file(str(csv_path), "test.csv")
        assert len(candidates) == 2
        assert candidates[0].name == "John Doe"
        assert candidates[0].email == "john@test.com"

    def test_parse_csv_missing_required_columns(self, tmp_path):
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("foo,bar\n1,2\n")

        with pytest.raises((ParseError, Exception)):
            parse_import_file(str(csv_path), "bad.csv")

    def test_parse_csv_empty_rows(self, tmp_path):
        csv_path = tmp_path / "empty.csv"
        csv_path.write_text(
            "name,email,phone,candidate_id\n"
            ",,,\n"
            "John,john@test.com,123,C001\n"
        )

        candidates, errors = parse_import_file(str(csv_path), "empty.csv")
        # At least one valid candidate
        assert len(candidates) >= 1

    def test_parse_nonexistent_file(self):
        with pytest.raises((FileNotFoundError, ParseError, Exception)):
            parse_import_file("/nonexistent/path.csv", "missing.csv")


# ─── DiscoveryService ────────────────────────────────────────────────────────


class TestDiscoveryService:
    """Test DiscoveryService."""

    @pytest.mark.asyncio
    async def test_get_gmail_scanner_no_config(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        svc = DiscoveryService(db)
        scanner = await svc.get_gmail_scanner()
        assert scanner is None

    @pytest.mark.asyncio
    async def test_get_drive_service_no_config(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        svc = DiscoveryService(db)
        drive = await svc.get_drive_service()
        assert drive is None

    @pytest.mark.asyncio
    async def test_get_gmail_scanner_with_config(self):
        db = AsyncMock()
        config = MagicMock(
            credentials_json='{"token":"t","refresh_token":"r","token_uri":"https://oauth2.googleapis.com/token","client_id":"c","client_secret":"s"}',
            is_enabled=True,
        )
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = config
        db.execute = AsyncMock(return_value=result_mock)

        svc = DiscoveryService(db)

        with patch("google.oauth2.credentials.Credentials") as mock_creds, \
             patch("googleapiclient.discovery.build"):
            mock_creds.from_authorized_user_info.return_value = MagicMock(valid=True)
            scanner = await svc.get_gmail_scanner()

        assert scanner is not None

    @pytest.mark.asyncio
    async def test_discover_documents_no_services(self):
        db = AsyncMock()
        svc = DiscoveryService(db)

        gmail_atts, drive_files = await svc.discover_documents(
            "John Doe", "john@test.com", None, None
        )
        assert gmail_atts == []
        assert drive_files == []

    @pytest.mark.asyncio
    async def test_discover_documents_with_gmail(self):
        db = AsyncMock()
        svc = DiscoveryService(db)

        mock_scanner = MagicMock()
        attachment = MagicMock(filename="doc.pdf")
        mock_scanner.search_for_candidate.return_value = [attachment]

        gmail_atts, drive_files = await svc.discover_documents(
            "John Doe", "john@test.com", mock_scanner, None
        )
        assert len(gmail_atts) == 1


# ─── BatchStatusService ──────────────────────────────────────────────────────


class TestBatchStatusService:
    """Test BatchStatusService."""

    @pytest.mark.asyncio
    async def test_log_creates_entry(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()

        svc = BatchStatusService(db, ws_hub=None)
        await svc.log("batch-1", "bc-1", "info", "test", "Test message")

        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_emit_candidate_status_no_hub(self):
        db = AsyncMock()
        svc = BatchStatusService(db, ws_hub=None)

        bc = MagicMock(id="bc-1", status="processing")
        # Should not raise even without ws_hub
        await svc.emit_candidate_status("batch-1", bc)

    @pytest.mark.asyncio
    async def test_emit_candidate_status_with_hub(self):
        db = AsyncMock()
        ws_hub = AsyncMock()
        ws_hub.emit_candidate_status = AsyncMock()

        svc = BatchStatusService(db, ws_hub=ws_hub)
        bc = MagicMock(
            id="bc-1", status="processing",
            documents_found=2, documents_processed=1,
            documents_failed=0, error_message=None,
        )

        await svc.emit_candidate_status("batch-1", bc)
        ws_hub.emit_candidate_status.assert_called_once()


# ─── ChecklistMatcher ────────────────────────────────────────────────────────


class TestChecklistMatcher:
    """Test ChecklistMatcher utility methods."""

    def test_normalize_doc_type(self):
        assert ChecklistMatcher.normalize_doc_type("Aadhaar Card") == "aadhaarcard"
        assert ChecklistMatcher.normalize_doc_type("PAN Card") == "pancard"
        assert ChecklistMatcher.normalize_doc_type("  Passport  ") == "passport"

    def test_doc_type_matches_checklist(self):
        mandatory = {"aadhaarcard", "pancard", "passport"}
        assert ChecklistMatcher.doc_type_matches_checklist("aadhaarcard", mandatory) is True
        assert ChecklistMatcher.doc_type_matches_checklist("voterid", mandatory) is False

    def test_get_matched_mandatory(self):
        uploaded = {"aadhaarcard", "pancard"}
        mandatory = {"aadhaarcard", "pancard", "passport"}
        matched, missing = ChecklistMatcher.get_matched_mandatory(uploaded, mandatory)
        assert "aadhaarcard" in matched
        assert "passport" in missing
