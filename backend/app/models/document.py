import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Integer, Float, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import ProcessingStatus


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id = Column(String(36), ForeignKey("candidates.id"), nullable=False, index=True)
    upload_batch_id = Column(String(36), ForeignKey("upload_batches.id"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False, unique=True)
    file_path = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    total_pages = Column(Integer, default=1)
    processing_status = Column(String(50), default=ProcessingStatus.UPLOADED.value, nullable=False, index=True)
    is_multi_page = Column(Boolean, default=False)
    correlation_id = Column(String(36), nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    candidate = relationship("Candidate", back_populates="documents")
    upload_batch = relationship("UploadBatch", back_populates="documents")
    pages = relationship("DocumentPage", back_populates="document", lazy="selectin", order_by="DocumentPage.page_number")
    ocr_results = relationship("OCRResult", back_populates="document", lazy="selectin")
    classifications = relationship("AIClassification", back_populates="document", lazy="selectin")
    validation_results = relationship("ValidationResult", back_populates="document", lazy="selectin")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    orientation_corrected = Column(Boolean, default=False)
    processing_status = Column(String(50), default=ProcessingStatus.PENDING.value, nullable=False)
    correlation_id = Column(String(36), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    document = relationship("Document", back_populates="pages")
    ocr_result = relationship("OCRResult", back_populates="page", uselist=False, lazy="selectin")
    classification = relationship("AIClassification", back_populates="page", uselist=False, lazy="selectin")
