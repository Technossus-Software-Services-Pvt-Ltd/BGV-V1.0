import json
import secrets
import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.websocket.hub import ws_hub
from app.core.logging import get_logger
from app.core.config import settings
from app.api.deps import get_current_user
from app.db.session import get_db, AsyncSessionLocal
from app.models.ws_ticket import WebSocketTicket

router = APIRouter()
logger = get_logger("api.ws")

_WS_TICKET_TTL_SECONDS = settings.ws_ticket_ttl_seconds


@router.post("/ws/ticket")
async def create_ws_ticket(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Issue a short-lived single-use ticket for WebSocket authentication."""
    ticket = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_WS_TICKET_TTL_SECONDS)

    ws_ticket = WebSocketTicket(ticket=ticket, expires_at=expires_at)
    db.add(ws_ticket)

    # Prune expired tickets opportunistically
    await db.execute(
        delete(WebSocketTicket).where(WebSocketTicket.expires_at < datetime.now(timezone.utc))
    )
    await db.commit()

    return {"ticket": ticket}


async def _consume_ws_ticket(ticket: str) -> bool:
    """Validate and consume a single-use WebSocket ticket from the database."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WebSocketTicket).where(WebSocketTicket.ticket == ticket)
        )
        ws_ticket = result.scalar_one_or_none()
        if not ws_ticket:
            return False

        # Check expiry
        if ws_ticket.expires_at < datetime.now(timezone.utc):
            await db.delete(ws_ticket)
            await db.commit()
            return False

        # Consume (single-use)
        await db.delete(ws_ticket)
        await db.commit()
        return True


async def _validate_ws_token(token: str) -> bool:
    """Validate session token against the database."""
    from app.models.auth_session import AuthSession
    from sqlalchemy.orm import selectinload

    if not token:
        return False

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AuthSession).options(selectinload(AuthSession.user))
            .where(AuthSession.session_token == token)
        )
        session = result.scalar_one_or_none()
        if not session:
            return False
        if session.revoked_at is not None:
            return False
        if session.expires_at and session.expires_at < datetime.now(timezone.utc):
            return False
        if not session.user or not session.user.is_active:
            return False
    return True


@router.websocket("/ws/batch/{batch_id}")
async def websocket_batch(
    websocket: WebSocket,
    batch_id: str,
    token: str = Query(default=""),
):
    """WebSocket endpoint for real-time batch processing updates.

    Authentication:
      - Preferred: Connect without token in URL, then send {"type": "auth", "token": "xxx"}
        as the first message after connection opens.
      - Legacy (deprecated): Pass token as query param ?token=xxx

    Server pushes events: processing-log, candidate-status-updated, processing-summary-updated
    """
    # If token provided via query param (legacy support), validate immediately
    if token:
        # Try as single-use ticket first, fall back to session token
        if not (await _consume_ws_ticket(token) or await _validate_ws_token(token)):
            await websocket.close(code=4003, reason="Invalid token")
            return
        await ws_hub.connect(websocket, batch_id)
    else:
        # Accept connection and wait for auth message
        await websocket.accept()

        try:
            # Wait for the first message which must be an auth message
            # Give client 10 seconds to authenticate
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            msg = json.loads(raw)

            if msg.get("type") != "auth" or not msg.get("token"):
                await websocket.close(code=4001, reason="First message must be auth")
                return

            if not (await _consume_ws_ticket(msg["token"]) or await _validate_ws_token(msg["token"])):
                await websocket.close(code=4003, reason="Invalid token")
                return

            # Authentication successful — register with hub
            await ws_hub.connect_existing(websocket, batch_id)
        except (asyncio.TimeoutError, json.JSONDecodeError, TypeError):
            await websocket.close(code=4001, reason="Authentication timeout or invalid format")
            return

    try:
        while True:
            # Listen for client messages (ping/pong keep-alive)
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except (json.JSONDecodeError, TypeError):
                pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("ws_error", batch_id=batch_id, error=str(e))
    finally:
        await ws_hub.disconnect(websocket, batch_id)
