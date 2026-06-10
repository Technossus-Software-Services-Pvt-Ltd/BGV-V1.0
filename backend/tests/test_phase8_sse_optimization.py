"""Tests for Phase 8: SSE optimization with Redis Pub/Sub."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── Pub/Sub publish tests ───────────────────────────────────────────────────────


class TestPublishBatchEvent:
    """Tests for publish_batch_event function."""

    @pytest.mark.asyncio
    @patch("app.services.pubsub.settings")
    async def test_returns_false_when_redis_disabled(self, mock_settings):
        from app.services.pubsub import publish_batch_event
        mock_settings.redis_enabled = False

        result = await publish_batch_event("batch-1", {"message": "test"})
        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    @patch("app.services.pubsub.settings")
    async def test_returns_false_when_redis_unavailable(self, mock_settings, mock_get_redis):
        from app.services.pubsub import publish_batch_event
        mock_settings.redis_enabled = True
        mock_get_redis.return_value = None

        result = await publish_batch_event("batch-1", {"message": "test"})
        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    @patch("app.services.pubsub.settings")
    async def test_publishes_to_correct_channel(self, mock_settings, mock_get_redis):
        from app.services.pubsub import publish_batch_event
        mock_settings.redis_enabled = True

        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        event = {"id": "log-1", "message": "Processing started"}
        result = await publish_batch_event("batch-123", event)

        assert result is True
        mock_redis.publish.assert_awaited_once_with(
            "bgv:batch_logs:batch-123",
            json.dumps(event, default=str),
        )

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    @patch("app.services.pubsub.settings")
    async def test_returns_false_on_publish_error(self, mock_settings, mock_get_redis):
        from app.services.pubsub import publish_batch_event
        mock_settings.redis_enabled = True

        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = ConnectionError("Redis down")
        mock_get_redis.return_value = mock_redis

        result = await publish_batch_event("batch-1", {"message": "test"})
        assert result is False


# ─── Pub/Sub subscribe tests ─────────────────────────────────────────────────────


class TestSubscribeBatchEvents:
    """Tests for subscribe_batch_events function."""

    @pytest.mark.asyncio
    @patch("app.services.pubsub.settings")
    async def test_returns_empty_when_redis_disabled(self, mock_settings):
        from app.services.pubsub import subscribe_batch_events
        mock_settings.redis_enabled = False

        events = []
        async for event in subscribe_batch_events("batch-1"):
            events.append(event)

        assert events == []

    @pytest.mark.asyncio
    @patch("redis.asyncio.from_url")
    @patch("app.services.pubsub.settings")
    async def test_yields_parsed_messages(self, mock_settings, mock_from_url):
        from app.services.pubsub import subscribe_batch_events
        mock_settings.redis_enabled = True
        mock_settings.redis_url = "redis://localhost:6379/0"

        # Mock the pubsub listener - from_url is sync, returns a Redis instance
        mock_redis = MagicMock()
        mock_pubsub = MagicMock()

        async def mock_listen():
            yield {"type": "message", "data": json.dumps({"id": "log-1", "message": "test"})}
            yield {"type": "message", "data": json.dumps({"id": "log-2", "message": "done"})}

        mock_pubsub.listen = mock_listen
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.unsubscribe = AsyncMock()
        mock_pubsub.close = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        mock_redis.close = AsyncMock()
        mock_from_url.return_value = mock_redis

        events = []
        async for event in subscribe_batch_events("batch-1"):
            events.append(event)
            if len(events) >= 2:
                break

        assert len(events) == 2
        assert events[0] == {"id": "log-1", "message": "test"}
        assert events[1] == {"id": "log-2", "message": "done"}


# ─── Channel name tests ─────────────────────────────────────────────────────────


class TestChannelName:
    """Tests for channel name generation."""

    def test_channel_name_format(self):
        from app.services.pubsub import _channel_name
        assert _channel_name("batch-123") == "bgv:batch_logs:batch-123"

    def test_channel_name_unique_per_batch(self):
        from app.services.pubsub import _channel_name
        assert _channel_name("a") != _channel_name("b")


# ─── BatchStatusService Pub/Sub integration ──────────────────────────────────────


class TestBatchStatusServicePubSub:
    """Tests that BatchStatusService publishes to Redis Pub/Sub."""

    @pytest.mark.asyncio
    @patch("app.services.pubsub.settings")
    @patch("app.services.cache.get_redis")
    async def test_log_publishes_to_pubsub(self, mock_get_redis, mock_pubsub_settings):
        from app.services.batch.status_service import BatchStatusService

        mock_pubsub_settings.redis_enabled = True
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        mock_ws_hub = AsyncMock()

        svc = BatchStatusService(db=mock_db, ws_hub=mock_ws_hub)
        await svc.log(
            batch_import_id="batch-1",
            batch_candidate_id="cand-1",
            level="info",
            stage="processing",
            message="Started processing",
            details=None,
        )

        # Should have published to redis
        mock_redis.publish.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("app.services.pubsub.settings")
    @patch("app.services.cache.get_redis")
    async def test_log_continues_on_pubsub_failure(self, mock_get_redis, mock_pubsub_settings):
        """Pub/Sub failure should not break the log method."""
        from app.services.batch.status_service import BatchStatusService

        mock_pubsub_settings.redis_enabled = True
        mock_redis = AsyncMock()
        mock_redis.publish.side_effect = Exception("Redis exploded")
        mock_get_redis.return_value = mock_redis

        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        mock_ws_hub = AsyncMock()

        svc = BatchStatusService(db=mock_db, ws_hub=mock_ws_hub)
        # Should not raise
        await svc.log(
            batch_import_id="batch-1",
            batch_candidate_id=None,
            level="error",
            stage="init",
            message="Something went wrong",
        )

        # WebSocket should still be called
        mock_ws_hub.emit_processing_log.assert_awaited_once()


# ─── SSE generator helper tests ──────────────────────────────────────────────────


class TestCatchupLogs:
    """Tests for the _catchup_logs helper."""

    @pytest.mark.asyncio
    async def test_catchup_yields_log_events(self):
        from app.api.routes.batch import _catchup_logs

        mock_db = AsyncMock()
        mock_log = MagicMock()
        mock_log.id = "log-1"
        mock_log.level = "info"
        mock_log.stage = "ocr"
        mock_log.message = "Processing page 1"
        mock_log.details = None
        mock_log.batch_candidate_id = "cand-1"
        mock_log.created_at = MagicMock()
        mock_log.created_at.isoformat.return_value = "2026-06-09T10:00:00+00:00"

        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [mock_log]
        mock_db.execute = AsyncMock(return_value=result_mock)

        events = []
        async for event in _catchup_logs(mock_db, "batch-1", None):
            events.append(event)

        assert len(events) == 1
        data = json.loads(events[0].replace("data: ", "").strip())
        assert data["id"] == "log-1"
        assert data["level"] == "info"
        assert data["message"] == "Processing page 1"

    @pytest.mark.asyncio
    async def test_catchup_empty_when_no_logs(self):
        from app.api.routes.batch import _catchup_logs

        mock_db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=result_mock)

        events = []
        async for event in _catchup_logs(mock_db, "batch-1", None):
            events.append(event)

        assert events == []


# ─── Pub/Sub listener tests ──────────────────────────────────────────────────────


class TestPubSubListener:
    """Tests for the _pubsub_listener helper."""

    @pytest.mark.asyncio
    async def test_listener_puts_events_in_queue(self):
        from app.api.routes.batch import _pubsub_listener

        queue = asyncio.Queue()

        # Mock subscribe_batch_events to yield 2 events then stop
        async def mock_subscribe(batch_id):
            yield {"id": "log-1", "message": "event 1"}
            yield {"id": "log-2", "message": "event 2"}

        with patch("app.services.pubsub.subscribe_batch_events", mock_subscribe):
            await _pubsub_listener("batch-1", queue)

        assert queue.qsize() == 2
        assert (await queue.get())["id"] == "log-1"
        assert (await queue.get())["id"] == "log-2"
