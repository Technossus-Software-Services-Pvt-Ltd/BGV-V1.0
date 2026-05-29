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


def validate_file_content(file_bytes: bytes, filename: str) -> str:
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded",
        )

    if len(file_bytes) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {settings.max_upload_size_mb}MB limit",
        )

    if magic is None:
        # Fallback: infer MIME from file extension when python-magic is unavailable
        ext = Path(filename).suffix.lower() if filename else ""
        mime_map = {
            ".pdf": "application/pdf",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        detected_mime = mime_map.get(ext, "application/octet-stream")
    else:
        detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)
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
