from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ReviewQueueItem(BaseModel):
    id: str
    batch_import_id: str
    batch_code: str
    candidate_id: Optional[str]
    source_candidate_id: str
    source_name: str
    source_email: Optional[str]
    status: str
    documents_found: int
    documents_processed: int
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewQueueResponse(BaseModel):
    items: List[ReviewQueueItem]
    total: int
