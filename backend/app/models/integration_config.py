import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, Boolean
from app.db.base import Base
from app.models.enums import IntegrationProvider


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(50), unique=True, nullable=False, index=True)
    is_enabled = Column(Boolean, default=False, nullable=False)
    credentials_json = Column(Text, nullable=True)  # Encrypted OAuth2 credentials
    config_json = Column(Text, nullable=True)  # Provider-specific config (folder IDs, search params)
    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
