import uuid
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.core.config import settings


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the application secret_key."""
    import base64
    import hashlib
    # Derive a 32-byte key from secret_key for Fernet (which needs url-safe base64 of 32 bytes)
    key_bytes = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def _encrypt_token(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return _get_fernet().encrypt(value.encode()).decode()


def _decrypt_token(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        return _get_fernet().decrypt(value.encode()).decode()
    except Exception:
        # Return raw value if decryption fails (legacy unencrypted data)
        return value


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("auth_users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String(255), unique=True, nullable=False, index=True)
    _access_token = Column("access_token", Text, nullable=True)
    _refresh_token = Column("refresh_token", Text, nullable=True)
    token_type = Column(String(50), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("AuthUser", back_populates="sessions")

    @property
    def access_token(self) -> Optional[str]:
        return _decrypt_token(self._access_token)

    @access_token.setter
    def access_token(self, value: Optional[str]):
        self._access_token = _encrypt_token(value)

    @property
    def refresh_token(self) -> Optional[str]:
        return _decrypt_token(self._refresh_token)

    @refresh_token.setter
    def refresh_token(self, value: Optional[str]):
        self._refresh_token = _encrypt_token(value)
