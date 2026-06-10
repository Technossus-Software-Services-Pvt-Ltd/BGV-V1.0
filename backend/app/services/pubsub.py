"""Redis Pub/Sub service for real-time event broadcasting.

Used by the SSE streaming endpoint to receive batch log events immediately
instead of polling the database every second.
"""

import asyncio
import json
from typing import AsyncGenerator, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("pubsub.redis")


def _channel_name(batch_id: str) -> str:
    """Build Redis channel name for a batch."""
    return f"bgv:batch_logs:{batch_id}"


async def publish_batch_event(batch_id: str, event_data: dict) -> bool:
    """Publish a batch log event to Redis Pub/Sub.

    Called by the batch orchestrator/logger when a new log is created.
    Returns True if published, False if Redis unavailable.
    """
    if not settings.redis_enabled:
        return False

    try:
        from app.services.cache import get_redis
        redis = await get_redis()
        if redis is None:
            return False

        channel = _channel_name(batch_id)
        message = json.dumps(event_data, default=str)
        await redis.publish(channel, message)
        return True
    except Exception as e:
        logger.warning("pubsub_publish_failed", batch_id=batch_id, error=str(e))
        return False


async def subscribe_batch_events(batch_id: str) -> AsyncGenerator[dict, None]:
    """Subscribe to batch log events via Redis Pub/Sub.

    Yields event dicts as they arrive. Exits when the channel is unsubscribed
    or Redis connection drops.
    """
    if not settings.redis_enabled:
        return

    try:
        from redis.asyncio import from_url
        # Use a dedicated connection for Pub/Sub (not shared with cache)
        redis = from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=5,
        )

        pubsub = redis.pubsub()
        channel = _channel_name(batch_id)
        await pubsub.subscribe(channel)
        logger.info("pubsub_subscribed", batch_id=batch_id, channel=channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        yield data
                    except (json.JSONDecodeError, TypeError):
                        continue
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            await redis.close()
            logger.info("pubsub_unsubscribed", batch_id=batch_id)

    except Exception as e:
        logger.warning("pubsub_subscribe_failed", batch_id=batch_id, error=str(e))
        return
