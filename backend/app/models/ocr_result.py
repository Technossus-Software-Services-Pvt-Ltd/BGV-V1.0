import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, Text, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.db.base import Base


class OCRResult(Base):
    __tablename__ = "ocr_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    page_id = Column(String(36), ForeignKey("document_pages.id"), nullable=True, index=True)
    ocr_engine = Column(String(50), nullable=False, default="paddleocr")
    extracted_text = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    word_count = Column(Integer, default=0)
    language_detected = Column(String(10), nullable=True)
    orientation_angle = Column(Float, default=0.0)
    processing_duration_ms = Column(Integer, nullable=True)
    raw_output_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    correlation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    document = relationship("Document", back_populates="ocr_results")
    page = relationship("DocumentPage", back_populates="ocr_result")
