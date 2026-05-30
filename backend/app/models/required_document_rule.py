import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.db.base import Base


class RequiredDocumentRule(Base):
    __tablename__ = "required_document_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    is_mandatory = Column(Boolean, default=True, nullable=False)
    accepted_formats_json = Column(Text, nullable=False, default="[]")
    sort_order = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)