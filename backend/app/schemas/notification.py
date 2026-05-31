from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class NotifyRequest(BaseModel):
    candidate_ids: List[str]


class NotifyResponse(BaseModel):
    queued: int
    skipped: int
    message: str


class NotificationLogItem(BaseModel):
    id: str
    candidate_id: str
    recipient_email: str
    subject: str
    body_html: str
    status: str
    error_message: Optional[str]
    sent_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
