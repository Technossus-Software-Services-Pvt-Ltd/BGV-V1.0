import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import ProcessingStatus


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    batch_reference = Column(String(100), unique=True, nullable=False, index=True)
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)
    failed_files = Column(Integer, default=0)
    processing_status = Column(String(50), default=ProcessingStatus.PENDING.value, nullable=False)
    correlation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    candidate = relationship("Candidate", back_populates="upload_batches")
    documents = relationship("Document", back_populates="upload_batch", lazy="selectin")
