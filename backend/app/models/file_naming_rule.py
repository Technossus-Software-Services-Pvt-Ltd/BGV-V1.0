import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String

from app.db.base import Base


class FileNamingRule(Base):
    __tablename__ = "file_naming_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    folder_structure_pattern = Column(String(255), nullable=False)
    file_rename_pattern = Column(String(255), nullable=False)
    example_output = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
