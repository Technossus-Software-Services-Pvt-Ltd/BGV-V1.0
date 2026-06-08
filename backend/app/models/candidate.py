import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.orm import relationship
from app.db.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    dob = Column(String(20), nullable=True)  # DD/MM/YYYY format
    gender = Column(String(20), nullable=True)  # Male/Female/Transgender
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    notes = Column(Text, nullable=True)
    correlation_id = Column(String(36), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    upload_batches = relationship("UploadBatch", back_populates="candidate", lazy="noload")
    documents = relationship("Document", back_populates="candidate", lazy="noload")
