import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import BatchCandidateStatus


class BatchImportCandidate(Base):
    __tablename__ = "batch_import_candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_import_id = Column(String(36), ForeignKey("batch_imports.id"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=True, index=True)
    row_number = Column(Integer, nullable=False)

    # Data from Excel/CSV row
    source_candidate_id = Column(String(100), nullable=False)
    source_name = Column(String(255), nullable=False)
    source_email = Column(String(255), nullable=True)
    source_phone = Column(String(50), nullable=True)
    source_dob = Column(String(20), nullable=True)
    source_gender = Column(String(20), nullable=True)

    # Processing state
    status = Column(String(50), default=BatchCandidateStatus.PENDING.value, nullable=False, index=True)
    documents_found = Column(Integer, default=0)
    documents_processed = Column(Integer, default=0)
    documents_failed = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)

    # Discovery metadata
    gmail_emails_found = Column(Integer, default=0)
    drive_files_found = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    batch_import = relationship("BatchImport", back_populates="candidates")
    candidate = relationship("Candidate", backref="batch_import_entries")
