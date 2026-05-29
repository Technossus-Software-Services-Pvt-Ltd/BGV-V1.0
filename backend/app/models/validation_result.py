import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    validation_status = Column(String(50), nullable=False)  # matched, partial_match, unmatched, not_applicable
    ownership_score = Column(Float, nullable=True)
    confidence = Column(String(20), nullable=True)  # HIGH, MEDIUM, LOW
    # Name matching
    name_match_score = Column(Float, nullable=True)
    name_match_level = Column(String(20), nullable=True)  # exact, strong, partial, weak, none
    name_matched_tokens = Column(Float, nullable=True)
    name_total_tokens = Column(Float, nullable=True)
    # DOB matching
    dob_match = Column(Boolean, nullable=True)
    dob_partial = Column(Boolean, nullable=True)
    # Gender matching
    gender_match = Column(Boolean, nullable=True)
    # Conflict detection
    multi_person_detected = Column(Boolean, default=False)
    # Legacy
    name_match = Column(Boolean, nullable=True)
    id_number_match = Column(Boolean, nullable=True)
    ownership_confirmed = Column(Boolean, default=False)
    validation_reasoning = Column(Text, nullable=True)
    mismatches_json = Column(Text, nullable=True)
    # Review
    requires_manual_review = Column(Boolean, default=False)
    manual_review_reasons_json = Column(Text, nullable=True)
    # Meta
    processing_duration_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    correlation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    document = relationship("Document", back_populates="validation_results")
