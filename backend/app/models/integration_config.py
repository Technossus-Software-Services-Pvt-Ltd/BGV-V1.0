import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, String, DateTime, Text, Boolean
from app.db.base import Base
from app.models.enums import IntegrationProvider
from app.models.auth_session import _encrypt_token, _decrypt_token


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(50), unique=True, nullable=False, index=True)
    is_enabled = Column(Boolean, default=False, nullable=False)
    _credentials_json = Column("credentials_json", Text, nullable=True)
    config_json = Column(Text, nullable=True)  # Provider-specific config (folder IDs, search params)
    last_validated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def credentials_json(self) -> Optional[str]:
        """Decrypt credentials on read."""
        return _decrypt_token(self._credentials_json)

    @credentials_json.setter
    def credentials_json(self, value: Optional[str]):
        """Encrypt credentials on write."""
        self._credentials_json = _encrypt_token(value)
