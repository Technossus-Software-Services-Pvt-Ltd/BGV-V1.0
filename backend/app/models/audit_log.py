import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Integer
from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id = Column(String(36), nullable=False, index=True)
    candidate_id = Column(String(36), nullable=True, index=True)
    document_id = Column(String(36), nullable=True, index=True)
    page_id = Column(String(36), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    log_level = Column(String(20), nullable=False, default="info")
    processing_stage = Column(String(100), nullable=True)
    message = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
