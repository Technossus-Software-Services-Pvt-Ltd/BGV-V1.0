import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Integer, Float
from app.db.base import Base


class ProcessingEvent(Base):
    __tablename__ = "processing_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id = Column(String(36), nullable=False, index=True)
    document_id = Column(String(36), nullable=False, index=True)
    page_id = Column(String(36), nullable=True)
    event_type = Column(String(100), nullable=False)
    stage = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)
    message = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    metadata_json = Column(Text, nullable=True)
    error_details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
