"""Service protocols (interfaces) for dependency injection.

These protocols define the contracts that services must implement,
enabling loose coupling and testability without changing behavior.
"""

from typing import Optional, Protocol, runtime_checkable

import numpy as np


# ---------------------------------------------------------------------------
# OCR Engine Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class OCREngineResult(Protocol):
    """Result returned by an OCR engine."""

    text: str
    confidence: float
    word_count: int
    raw_output: list
    processing_duration_ms: int
    language_detected: Optional[str]
    orientation_angle: float
    error: Optional[str]

    @property
    def is_successful(self) -> bool: ...


@runtime_checkable
class OCREngine(Protocol):
    """Protocol for OCR text extraction engines."""

    def process(self, image_array: np.ndarray) -> "OCREngineResult": ...

    async def process_async(self, image_array: np.ndarray) -> "OCREngineResult": ...


# ---------------------------------------------------------------------------
# Document Preprocessor Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DocumentPreprocessorProtocol(Protocol):
    """Protocol for document image preprocessing."""

    def normalize_image(self, image_path) -> tuple: ...

    def is_blank_page(self, image_array: np.ndarray) -> bool: ...

    def extract_pages_from_pdf(self, file_path, output_dir) -> list: ...


# ---------------------------------------------------------------------------
# AI Classifier Protocol
# ---------------------------------------------------------------------------


class ClassificationResultProtocol(Protocol):
    """Result returned by an AI classifier."""

    document_type: str
    confidence: float
    reasoning: str
    extracted_name: Optional[str]
    extracted_dob: Optional[str]
    extracted_gender: Optional[str]
    extracted_id_number: Optional[str]
    key_identifiers: list
    model_used: str
    prompt_tokens: int
    completion_tokens: int
    processing_duration_ms: int
    error: Optional[str]


@runtime_checkable
class AIClassifierProtocol(Protocol):
    """Protocol for AI-powered document classification."""

    async def classify_document(
        self,
        ocr_text: str,
        ocr_confidence: float,
        word_count: int,
    ) -> ClassificationResultProtocol: ...


# ---------------------------------------------------------------------------
# Ownership Validator Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class OwnershipValidatorProtocol(Protocol):
    """Protocol for document ownership validation."""

    def validate(
        self,
        candidate_name: str,
        candidate_dob: Optional[str],
        candidate_gender: Optional[str],
        extracted_name: Optional[str],
        extracted_dob: Optional[str],
        extracted_gender: Optional[str],
        ocr_text: Optional[str],
        document_type: str,
        ocr_confidence: float = 0.0,
        candidate_pan: Optional[str] = None,
        candidate_aadhaar_last_four: Optional[str] = None,
        extracted_id_number: Optional[str] = None,
    ): ...


# ---------------------------------------------------------------------------
# Notification Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class NotificationServiceProtocol(Protocol):
    """Protocol for sending notifications."""

    @staticmethod
    async def queue_notifications(db, candidate_ids: list) -> list: ...


# ---------------------------------------------------------------------------
# Audit Service Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class AuditServiceProtocol(Protocol):
    """Protocol for audit logging."""

    async def log(
        self,
        correlation_id: str,
        action: str,
        message: str,
        **kwargs,
    ): ...

    async def record_processing_event(
        self,
        correlation_id: str,
        document_id: str,
        event_type: str,
        stage: str,
        status: str,
        **kwargs,
    ): ...


# ---------------------------------------------------------------------------
# WebSocket Hub Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class WebSocketHubProtocol(Protocol):
    """Protocol for WebSocket event broadcasting."""

    async def emit_processing_log(
        self,
        batch_id: str,
        log_id: str,
        batch_candidate_id: Optional[str],
        level: str,
        stage: str,
        message: str,
        details: Optional[str] = None,
    ) -> None: ...

    async def emit_candidate_status(
        self,
        batch_id: str,
        candidate_id: str,
        status: str,
        documents_found: int = 0,
        documents_processed: int = 0,
        documents_failed: int = 0,
        error_message: Optional[str] = None,
    ) -> None: ...

    async def emit_processing_summary(
        self,
        batch_id: str,
        total: int,
        completed: int,
        failed: int,
        in_progress: int,
        partial: int,
        pending: int,
        no_documents: int,
        batch_status: str,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Document Normalizer Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class DocumentNormalizerProtocol(Protocol):
    """Protocol for document normalization (page extraction)."""

    def get_document_dir(self, correlation_id: str, document_id: str): ...

    def extract_pages(self, file_path, doc_dir, mime_type: str) -> list: ...
