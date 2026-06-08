import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import WebSocket
from app.core.logging import get_logger

logger = get_logger("websocket.hub")


class WebSocketHub:
    """Manages WebSocket connections grouped by batch_id rooms.

    Supports broadcasting events to all clients subscribed to a specific batch.
    Thread-safe for use from background tasks via asyncio.
    """

    def __init__(self):
        # dict[batch_id, set[WebSocket]]
        self._rooms: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, batch_id: str) -> None:
        """Accept a WebSocket connection and add it to the batch room."""
        await websocket.accept()
        async with self._lock:
            if batch_id not in self._rooms:
                self._rooms[batch_id] = set()
            self._rooms[batch_id].add(websocket)
        logger.info("ws_connected", batch_id=batch_id, clients=len(self._rooms[batch_id]))

    async def connect_existing(self, websocket: WebSocket, batch_id: str) -> None:
        """Add an already-accepted WebSocket to the batch room (no accept call)."""
        async with self._lock:
            if batch_id not in self._rooms:
                self._rooms[batch_id] = set()
            self._rooms[batch_id].add(websocket)
        logger.info("ws_connected", batch_id=batch_id, clients=len(self._rooms[batch_id]))

    async def disconnect(self, websocket: WebSocket, batch_id: str) -> None:
        """Remove a WebSocket connection from the batch room."""
        async with self._lock:
            if batch_id in self._rooms:
                self._rooms[batch_id].discard(websocket)
                if not self._rooms[batch_id]:
                    del self._rooms[batch_id]
        logger.info("ws_disconnected", batch_id=batch_id)

    async def broadcast(self, batch_id: str, event: str, payload: dict) -> None:
        """Broadcast an event to all clients in a batch room."""
        async with self._lock:
            clients = list(self._rooms.get(batch_id, set()))

        if not clients:
            return

        message = json.dumps({
            "event": event,
            "data": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        disconnected = []
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)

        # Clean up dead connections
        if disconnected:
            async with self._lock:
                room = self._rooms.get(batch_id)
                if room:
                    for ws in disconnected:
                        room.discard(ws)
                    if not room:
                        del self._rooms[batch_id]

    async def emit_processing_log(
        self,
        batch_id: str,
        log_id: str,
        batch_candidate_id: Optional[str],
        level: str,
        stage: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        """Emit a processing-log event."""
        await self.broadcast(batch_id, "processing-log", {
            "id": log_id,
            "batch_import_id": batch_id,
            "batch_candidate_id": batch_candidate_id,
            "level": level,
            "stage": stage,
            "message": message,
            "details": details,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    async def emit_candidate_status(
        self,
        batch_id: str,
        candidate_id: str,
        status: str,
        documents_found: int = 0,
        documents_processed: int = 0,
        documents_failed: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Emit a candidate-status-updated event."""
        await self.broadcast(batch_id, "candidate-status-updated", {
            "batch_import_id": batch_id,
            "candidate_id": candidate_id,
            "status": status,
            "documents_found": documents_found,
            "documents_processed": documents_processed,
            "documents_failed": documents_failed,
            "error_message": error_message,
        })

    async def emit_processing_summary(
        self,
        batch_id: str,
        total: int,
        completed: int,
        failed: int,
        in_progress: int,
        partial: int,
        pending: int,
        no_documents: int,
        batch_status: str,
    ) -> None:
        """Emit a processing-summary-updated event."""
        await self.broadcast(batch_id, "processing-summary-updated", {
            "batch_import_id": batch_id,
            "total": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "partial": partial,
            "pending": pending,
            "no_documents": no_documents,
            "batch_status": batch_status,
        })

    @property
    def active_connections(self) -> int:
        """Total number of active WebSocket connections."""
        return sum(len(clients) for clients in self._rooms.values())


# Singleton instance
ws_hub = WebSocketHub()
