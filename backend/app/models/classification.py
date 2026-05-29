import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.db.base import Base


class AIClassification(Base):
    __tablename__ = "ai_classifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    page_id = Column(String(36), ForeignKey("document_pages.id"), nullable=True, index=True)
    document_type = Column(String(50), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False)
    ai_reasoning = Column(Text, nullable=True)
    extracted_name = Column(String(255), nullable=True)
    extracted_dob = Column(String(20), nullable=True)
    extracted_gender = Column(String(20), nullable=True)
    extracted_id_number = Column(String(100), nullable=True)
    extracted_fields_json = Column(Text, nullable=True)
    model_used = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    processing_duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    correlation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    document = relationship("Document", back_populates="classifications")
    page = relationship("DocumentPage", back_populates="classification")
