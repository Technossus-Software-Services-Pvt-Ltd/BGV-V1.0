"""Tests for app.services.websocket.hub module."""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.websocket.hub import WebSocketHub


class TestWebSocketHub:
    def setup_method(self):
        self.hub = WebSocketHub()

    @pytest.mark.asyncio
    async def test_connect_adds_to_room(self):
        ws = AsyncMock()
        await self.hub.connect(ws, "batch-1")
        ws.accept.assert_called_once()
        assert "batch-1" in self.hub._rooms
        assert ws in self.hub._rooms["batch-1"]

    @pytest.mark.asyncio
    async def test_connect_existing_no_accept(self):
        ws = AsyncMock()
        await self.hub.connect_existing(ws, "batch-2")
        ws.accept.assert_not_called()
        assert ws in self.hub._rooms["batch-2"]

    @pytest.mark.asyncio
    async def test_disconnect_removes_from_room(self):
        ws = AsyncMock()
        await self.hub.connect(ws, "batch-3")
        await self.hub.disconnect(ws, "batch-3")
        assert "batch-3" not in self.hub._rooms

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_room(self):
        ws = AsyncMock()
        # Should not raise
        await self.hub.disconnect(ws, "nonexistent")

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_clients(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await self.hub.connect(ws1, "batch-4")
        await self.hub.connect_existing(ws2, "batch-4")

        await self.hub.broadcast("batch-4", "test-event", {"key": "value"})

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

        # Verify message format
        msg = json.loads(ws1.send_text.call_args[0][0])
        assert msg["event"] == "test-event"
        assert msg["data"] == {"key": "value"}
        assert "timestamp" in msg

    @pytest.mark.asyncio
    async def test_broadcast_empty_room(self):
        # Should not raise
        await self.hub.broadcast("empty-room", "event", {})

    @pytest.mark.asyncio
    async def test_broadcast_cleans_dead_connections(self):
        ws_good = AsyncMock()
        ws_dead = AsyncMock()
        ws_dead.send_text.side_effect = RuntimeError("connection closed")

        await self.hub.connect(ws_good, "batch-5")
        await self.hub.connect_existing(ws_dead, "batch-5")

        await self.hub.broadcast("batch-5", "event", {"data": 1})

        # Dead connection should be removed
        assert ws_dead not in self.hub._rooms.get("batch-5", set())
        # Good connection should remain
        assert ws_good in self.hub._rooms["batch-5"]

    @pytest.mark.asyncio
    async def test_multiple_rooms_independent(self):
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        await self.hub.connect(ws1, "room-a")
        await self.hub.connect(ws2, "room-b")

        await self.hub.broadcast("room-a", "event", {})

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()
