import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from app.db.base import Base


class OAuthState(Base):
    """Stores OAuth2 state parameters in the database for multi-worker safety.

    Replaces in-memory dicts that fail when multiple uvicorn workers are used.
    """
    __tablename__ = "oauth_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    state = Column(String(100), unique=True, nullable=False, index=True)
    redirect_uri = Column(String(500), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
