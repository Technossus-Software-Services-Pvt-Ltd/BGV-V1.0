import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket.hub import ws_hub
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("api.ws")


@router.websocket("/ws/batch/{batch_id}")
async def websocket_batch(
    websocket: WebSocket,
    batch_id: str,
    token: str = Query(default=""),
):
    """WebSocket endpoint for real-time batch processing updates.

    Clients connect with: ws://host/api/v1/ws/batch/{batch_id}?token=xxx
    Server pushes events: processing-log, candidate-status-updated, processing-summary-updated
    """
    # Auth validation: accept same session token as REST API
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    # Validate token against DB
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.auth_session import AuthSession
    from datetime import datetime, timezone

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(AuthSession).where(AuthSession.session_token == token)
        )
        session = result.scalar_one_or_none()
        if not session:
            await websocket.close(code=4003, reason="Invalid token")
            return
        if session.revoked_at is not None:
            await websocket.close(code=4003, reason="Token revoked")
            return
        if session.expires_at and session.expires_at < datetime.now(timezone.utc):
            await websocket.close(code=4003, reason="Token expired")
            return

    await ws_hub.connect(websocket, batch_id)

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
