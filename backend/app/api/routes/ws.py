import json
import secrets
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from app.services.websocket.hub import ws_hub
from app.core.logging import get_logger
from app.api.deps import get_current_user

router = APIRouter()
logger = get_logger("api.ws")

# Short-lived single-use WebSocket tickets (ticket -> expiry timestamp)
_ws_tickets: dict[str, float] = {}
_WS_TICKET_TTL_SECONDS = 30


@router.post("/ws/ticket")
async def create_ws_ticket(current_user=Depends(get_current_user)):
    """Issue a short-lived single-use ticket for WebSocket authentication."""
    ticket = secrets.token_urlsafe(32)
    _ws_tickets[ticket] = time.time() + _WS_TICKET_TTL_SECONDS
    # Prune expired tickets opportunistically
    now = time.time()
    expired = [k for k, v in _ws_tickets.items() if v < now]
    for k in expired:
        _ws_tickets.pop(k, None)
    return {"ticket": ticket}


def _consume_ws_ticket(ticket: str) -> bool:
    """Validate and consume a single-use WebSocket ticket. Returns True if valid."""
    expiry = _ws_tickets.pop(ticket, None)
    if expiry is None:
        return False
    return time.time() < expiry


async def _validate_ws_token(token: str) -> bool:
    """Validate session token against the database."""
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.auth_session import AuthSession
    from datetime import datetime, timezone

    if not token:
        return False

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AuthSession).where(AuthSession.session_token == token)
        )
        session = result.scalar_one_or_none()
        if not session:
            return False
        if session.revoked_at is not None:
            return False
        if session.expires_at and session.expires_at < datetime.now(timezone.utc):
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
        if not (_consume_ws_ticket(token) or await _validate_ws_token(token)):
            await websocket.close(code=4003, reason="Invalid token")
            return
        await ws_hub.connect(websocket, batch_id)
    else:
        # Accept connection and wait for auth message
        await websocket.accept()

        try:
            # Wait for the first message which must be an auth message
            # Give client 10 seconds to authenticate
            import asyncio
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            msg = json.loads(raw)

            if msg.get("type") != "auth" or not msg.get("token"):
                await websocket.close(code=4001, reason="First message must be auth")
                return

            if not (_consume_ws_ticket(msg["token"]) or await _validate_ws_token(msg["token"])):
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
