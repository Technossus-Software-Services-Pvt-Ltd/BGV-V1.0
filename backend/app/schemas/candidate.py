from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CandidateCreate(BaseModel):
    candidate_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)


class CandidateResponse(BaseModel):
    id: str
    candidate_id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CandidateListResponse(BaseModel):
    candidates: list[CandidateResponse]
    total: int
