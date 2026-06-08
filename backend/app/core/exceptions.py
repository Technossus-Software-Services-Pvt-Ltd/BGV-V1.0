"""Domain exceptions for the BGV application.

All domain exceptions inherit from BGVBaseException and are mapped to HTTP status codes
by the global exception handler in main.py. Services should raise these instead of
raw Exception or HTTPException.

Exception hierarchy:
    BGVBaseException (500)
    ├── DocumentNotFoundError (404)
    ├── CandidateNotFoundError (404)
    ├── BatchNotFoundError (404)
    ├── IntegrationNotFoundError (404)
    ├── ValidationError (422)
    ├── FileStorageError (500)
    ├── OCRProcessingError (500)
    ├── AIClassificationError (500)
    ├── OllamaConnectionError (503)
    ├── IntegrationConnectionError (503)
    ├── ProcessingTimeoutError (504)
    └── BatchParseError (400)
"""

from fastapi import HTTPException, status


class BGVBaseException(Exception):
    """Base exception for all domain errors. Maps to HTTP 500 by default."""

    status_code: int = 500

    def __init__(self, message: str, correlation_id: str = None, details: dict = None):
        self.message = message
        self.correlation_id = correlation_id
        self.details = details or {}
        super().__init__(message)


# --- 404 Not Found ---

class DocumentNotFoundError(BGVBaseException):
    """Raised when a document ID does not exist."""
    status_code = 404


class CandidateNotFoundError(BGVBaseException):
    """Raised when a candidate ID does not exist."""
    status_code = 404


class BatchNotFoundError(BGVBaseException):
    """Raised when a batch import ID does not exist."""
    status_code = 404


class IntegrationNotFoundError(BGVBaseException):
    """Raised when a required integration config is missing."""
    status_code = 404


# --- 400 Bad Request ---

class BatchParseError(BGVBaseException):
    """Raised when CSV/Excel parsing fails due to invalid input."""
    status_code = 400


# --- 422 Validation Error ---

class ValidationError(BGVBaseException):
    """Raised when domain validation fails (not schema validation)."""
    status_code = 422


# --- 500 Internal Server Error ---

class FileStorageError(BGVBaseException):
    """Raised when file I/O (read/write/delete) fails."""
    status_code = 500


class OCRProcessingError(BGVBaseException):
    """Raised when OCR engine fails to process a document."""
    status_code = 500


class AIClassificationError(BGVBaseException):
    """Raised when AI classification fails irrecoverably."""
    status_code = 500


# --- 503 Service Unavailable ---

class OllamaConnectionError(BGVBaseException):
    """Raised when the Ollama LLM service is unreachable."""
    status_code = 503


class IntegrationConnectionError(BGVBaseException):
    """Raised when an external integration (Gmail, Drive) is unreachable."""
    status_code = 503


# --- 504 Gateway Timeout ---

class ProcessingTimeoutError(BGVBaseException):
    """Raised when a processing operation exceeds its time limit."""
    status_code = 504
