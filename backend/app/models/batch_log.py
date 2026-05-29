import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base
from app.models.enums import LogLevel


class BatchLog(Base):
    __tablename__ = "batch_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_import_id = Column(String(36), ForeignKey("batch_imports.id"), nullable=False, index=True)
    batch_candidate_id = Column(String(36), ForeignKey("batch_import_candidates.id"), nullable=True, index=True)
    level = Column(String(20), default=LogLevel.INFO.value, nullable=False)
    stage = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    batch_import = relationship("BatchImport", back_populates="logs")
