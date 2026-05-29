from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BatchImportResponse(BaseModel):
    id: str
    batch_code: str
    original_filename: str
    status: str
    total_candidates: int
    processed_candidates: int
    failed_candidates: int
    skipped_candidates: int
    total_documents_found: int
    total_documents_processed: int
    error_message: Optional[str]
    correlation_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchUploadResponse(BaseModel):
    batch_id: str
    batch_code: str
    total_candidates: int
    correlation_id: str
    message: str


class BatchCandidateResponse(BaseModel):
    id: str
    batch_import_id: str
    candidate_id: Optional[str]
    row_number: int
    source_candidate_id: str
    source_name: str
    source_email: Optional[str]
    source_phone: Optional[str]
    source_dob: Optional[str]
    source_gender: Optional[str]
    status: str
    documents_found: int
    documents_processed: int
    documents_failed: int
    gmail_emails_found: int
    drive_files_found: int
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchDetailResponse(BaseModel):
    batch: BatchImportResponse
    candidates: List[BatchCandidateResponse]


class BatchLogResponse(BaseModel):
    id: str
    batch_import_id: str
    batch_candidate_id: Optional[str]
    level: str
    stage: str
    message: str
    details: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class IntegrationConfigResponse(BaseModel):
    id: str
    provider: str
    is_enabled: bool
    has_credentials: bool
    config_json: Optional[str]
    last_validated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class IntegrationConfigUpdateRequest(BaseModel):
    is_enabled: Optional[bool] = None
    credentials_json: Optional[str] = None
    config_json: Optional[str] = None


class GmailStatusResponse(BaseModel):
    connected: bool
    has_client_config: bool
    email: Optional[str] = None
    scopes: List[str] = []
    is_enabled: bool = False
    last_validated_at: Optional[datetime] = None


class DriveConfigRequest(BaseModel):
    search_folder_ids: List[str] = []
    storage_root_folder_id: Optional[str] = None
