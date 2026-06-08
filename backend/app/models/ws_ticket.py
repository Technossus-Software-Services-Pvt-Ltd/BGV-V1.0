import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from app.db.base import Base


class WebSocketTicket(Base):
    """Database-backed single-use WebSocket authentication tickets.

    Replaces in-memory dict that fails with multiple uvicorn workers.
    """
    __tablename__ = "ws_tickets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticket = Column(String(100), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
