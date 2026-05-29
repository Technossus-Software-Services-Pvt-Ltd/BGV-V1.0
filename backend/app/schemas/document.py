from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DocumentResponse(BaseModel):
    id: str
    candidate_id: str
    upload_batch_id: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    total_pages: int
    processing_status: str
    is_multi_page: bool
    error_message: Optional[str]
    correlation_id: str
    created_at: datetime
    updated_at: datetime
    # Ownership verification (populated from validation result)
    validation_status: Optional[str] = None
    ownership_confirmed: Optional[bool] = None
    validated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentPageResponse(BaseModel):
    id: str
    document_id: str
    page_number: int
    width: Optional[int]
    height: Optional[int]
    orientation_corrected: bool
    processing_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class OCRResultResponse(BaseModel):
    id: str
    document_id: str
    page_id: Optional[str]
    ocr_engine: str
    extracted_text: Optional[str]
    confidence_score: Optional[float]
    word_count: int
    language_detected: Optional[str]
    orientation_angle: float
    processing_duration_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ClassificationResponse(BaseModel):
    id: str
    document_id: str
    page_id: Optional[str]
    document_type: str
    confidence_score: float
    ai_reasoning: Optional[str]
    extracted_name: Optional[str]
    extracted_dob: Optional[str]
    extracted_id_number: Optional[str]
    model_used: str
    processing_duration_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ValidationResultResponse(BaseModel):
    id: str
    document_id: str
    candidate_id: str
    validation_status: str
    name_match: Optional[bool]
    name_match_score: Optional[float]
    dob_match: Optional[bool]
    id_number_match: Optional[bool]
    ownership_confirmed: bool
    validation_reasoning: Optional[str]
    processing_duration_ms: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentDetailResponse(BaseModel):
    document: DocumentResponse
    candidate_name: Optional[str] = None
    pages: List[DocumentPageResponse]
    ocr_results: List[OCRResultResponse]
    classifications: List[ClassificationResponse]
    validation_results: List[ValidationResultResponse]
