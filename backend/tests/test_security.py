"""Tests for app.core.security module."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.core.security import (
    validate_upload_file,
    validate_file_content,
    sanitize_filename,
    _detect_mime_from_magic_bytes,
    ALLOWED_MIME_TYPES,
)


class TestDetectMimeFromMagicBytes:
    def test_pdf_detection(self):
        assert _detect_mime_from_magic_bytes(b"%PDF-1.4\nrest of file") == "application/pdf"

    def test_jpeg_detection(self):
        assert _detect_mime_from_magic_bytes(b"\xff\xd8\xff\xe0rest") == "image/jpeg"

    def test_png_detection(self):
        assert _detect_mime_from_magic_bytes(b"\x89PNG\r\n\x1a\nrest") == "image/png"

    def test_webp_detection(self):
        assert _detect_mime_from_magic_bytes(b"RIFF\x00\x00\x00\x00WEBP") == "image/webp"

    def test_unknown_returns_octet_stream(self):
        assert _detect_mime_from_magic_bytes(b"MZ\x90\x00random") == "application/octet-stream"

    def test_short_bytes_returns_octet_stream(self):
        assert _detect_mime_from_magic_bytes(b"ab") == "application/octet-stream"


class TestValidateUploadFile:
    def test_no_filename_raises(self):
        file = MagicMock()
        file.filename = ""
        with pytest.raises(HTTPException) as exc:
            validate_upload_file(file)
        assert exc.value.status_code == 400

    def test_filename_too_long_raises(self):
        file = MagicMock()
        file.filename = "a" * 300 + ".pdf"
        with pytest.raises(HTTPException) as exc:
            validate_upload_file(file)
        assert exc.value.status_code == 400
        assert "too long" in exc.value.detail

    def test_disallowed_extension_raises(self):
        file = MagicMock()
        file.filename = "virus.exe"
        with pytest.raises(HTTPException) as exc:
            validate_upload_file(file)
        assert exc.value.status_code == 400
        assert "not allowed" in exc.value.detail

    def test_valid_pdf_passes(self):
        file = MagicMock()
        file.filename = "document.pdf"
        validate_upload_file(file)  # Should not raise

    def test_valid_jpg_passes(self):
        file = MagicMock()
        file.filename = "photo.jpg"
        validate_upload_file(file)

    def test_valid_png_passes(self):
        file = MagicMock()
        file.filename = "scan.png"
        validate_upload_file(file)


class TestValidateFileContent:
    def test_empty_file_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_file_content(b"", "test.pdf")
        assert exc.value.status_code == 400
        assert "Empty" in exc.value.detail

    def test_oversized_file_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_file_content(b"x" * 100, "test.pdf", file_size=999_999_999)
        assert exc.value.status_code == 413

    @patch("app.core.security.magic", None)
    def test_uses_magic_bytes_fallback_for_pdf(self):
        result = validate_file_content(b"%PDF-1.4\n" + b"x" * 100, "doc.pdf")
        assert result == "application/pdf"

    @patch("app.core.security.magic", None)
    def test_uses_magic_bytes_fallback_for_jpeg(self):
        result = validate_file_content(b"\xff\xd8\xff\xe0" + b"x" * 100, "photo.jpg")
        assert result == "image/jpeg"

    @patch("app.core.security.magic", None)
    def test_disallowed_content_type_raises(self):
        with pytest.raises(HTTPException) as exc:
            validate_file_content(b"MZ\x90\x00" + b"x" * 100, "bad.pdf")
        assert exc.value.status_code == 400
        assert "not allowed" in exc.value.detail


class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("report.pdf") == "report.pdf"

    def test_spaces_replaced(self):
        assert sanitize_filename("my report.pdf") == "my_report.pdf"

    def test_special_chars_replaced(self):
        assert sanitize_filename("file@#$%.pdf") == "file____.pdf"

    def test_empty_becomes_unnamed(self):
        assert sanitize_filename("...") == "unnamed_file"

    def test_truncated_to_200(self):
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_leading_dots_stripped(self):
        assert sanitize_filename(".hidden") == "hidden"
