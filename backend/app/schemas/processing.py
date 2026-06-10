from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ProcessingEventResponse(BaseModel):
    id: str
    correlation_id: str
    document_id: str
    page_id: Optional[str]
    event_type: str
    stage: str
    status: str
    message: Optional[str]
    confidence: Optional[float]
    duration_ms: Optional[int]
    error_details: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProcessingTimelineResponse(BaseModel):
    document_id: str
    events: List[ProcessingEventResponse]
    current_status: str
    total_duration_ms: Optional[int]


class UploadBatchResponse(BaseModel):
    id: str
    candidate_id: str
    candidate_name: Optional[str] = None
    batch_reference: str
    total_files: int
    processed_files: int
    failed_files: int
    processing_status: str
    correlation_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UploadDocumentItem(BaseModel):
    id: str
    filename: str
    size_bytes: int
    mime_type: str
    status: str


class UploadResponse(BaseModel):
    batch_id: str
    batch_reference: str
    candidate_id: str
    documents: List[UploadDocumentItem]
    total_files: int
    correlation_id: str
    message: str
