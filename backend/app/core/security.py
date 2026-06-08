try:
    import magic
except ImportError:
    magic = None

from pathlib import Path
from fastapi import UploadFile, HTTPException, status
from app.core.config import settings

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}


def _detect_mime_from_magic_bytes(file_bytes: bytes) -> str:
    """Detect MIME type from file signature (magic bytes).

    Provides content-based validation even when python-magic is unavailable.
    """
    if len(file_bytes) < 4:
        return "application/octet-stream"

    # PDF: starts with %PDF
    if file_bytes[:4] == b"%PDF":
        return "application/pdf"
    # JPEG: starts with FF D8 FF
    if file_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    # PNG: starts with 89 50 4E 47 0D 0A 1A 0A
    if file_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    # WebP: RIFF....WEBP
    if len(file_bytes) >= 12 and file_bytes[:4] == b"RIFF" and file_bytes[8:12] == b"WEBP":
        return "image/webp"

    return "application/octet-stream"

MAX_FILENAME_LENGTH = 255


def validate_upload_file(file: UploadFile) -> None:
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    if len(file.filename) > MAX_FILENAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename too long",
        )

    ext = Path(file.filename).suffix.lower().lstrip(".")
    if ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' not allowed. Allowed: {settings.allowed_extensions_list}",
        )


def validate_file_content(file_bytes: bytes, filename: str, file_size: int = None) -> str:
    actual_size = file_size if file_size is not None else len(file_bytes)
    if actual_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded",
        )

    if actual_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {settings.max_upload_size_mb}MB limit",
        )

    if magic is not None:
        detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)
    else:
        # Fallback: validate using magic bytes (file signature) for content-based security
        detected_mime = _detect_mime_from_magic_bytes(file_bytes)
    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File content type '{detected_mime}' not allowed",
        )

    return detected_mime


def sanitize_filename(filename: str) -> str:
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_")
    sanitized = "".join(c if c in safe_chars else "_" for c in filename)
    sanitized = sanitized.strip("._")
    if not sanitized:
        sanitized = "unnamed_file"
    return sanitized[:200]
