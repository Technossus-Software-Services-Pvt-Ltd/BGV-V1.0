from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class AuditLogResponse(BaseModel):
    id: str
    correlation_id: str
    candidate_id: Optional[str]
    document_id: Optional[str]
    action: str
    log_level: str
    processing_stage: Optional[str]
    message: str
    duration_ms: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    correlation_id: Optional[str] = None


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    error_code: Optional[str] = None
    correlation_id: Optional[str] = None
