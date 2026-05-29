import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Integer, Text
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import BatchImportStatus


class BatchImport(Base):
    __tablename__ = "batch_imports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_code = Column(String(100), unique=True, nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    status = Column(String(50), default=BatchImportStatus.UPLOADED.value, nullable=False, index=True)
    total_candidates = Column(Integer, default=0)
    processed_candidates = Column(Integer, default=0)
    failed_candidates = Column(Integer, default=0)
    skipped_candidates = Column(Integer, default=0)
    total_documents_found = Column(Integer, default=0)
    total_documents_processed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    correlation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    candidates = relationship("BatchImportCandidate", back_populates="batch_import", lazy="selectin")
    logs = relationship("BatchLog", back_populates="batch_import", lazy="noload")
