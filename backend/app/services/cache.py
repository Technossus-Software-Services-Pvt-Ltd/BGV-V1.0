"""Redis cache service for application-level caching.

Provides a simple async interface for get/set/delete with TTL support.
Falls back gracefully to no-op when Redis is unavailable or disabled.
"""

import json
from typing import Any, Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("cache.redis")

_redis_client = None


async def get_redis():
    """Get or create the shared Redis connection."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if not settings.redis_enabled:
        return None

    try:
        from redis.asyncio import from_url
        _redis_client = from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Verify connection
        await _redis_client.ping()
        logger.info("redis_connected", url=settings.redis_url.split("@")[-1])
        return _redis_client
    except Exception as e:
        logger.warning("redis_connection_failed", error=str(e))
        _redis_client = None
        return None


async def close_redis():
    """Close the Redis connection pool."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
        logger.info("redis_disconnected")


class CacheService:
    """Async cache service backed by Redis with graceful fallback."""

    KEY_PREFIX = "bgv:"

    async def get(self, key: str) -> Optional[Any]:
        """Get a cached value. Returns None on miss or Redis unavailability."""
        redis = await get_redis()
        if redis is None:
            return None

        try:
            full_key = f"{self.KEY_PREFIX}{key}"
            raw = await redis.get(full_key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning("cache_get_error", key=key, error=str(e))
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int = 30) -> bool:
        """Set a cached value with TTL. Returns False if Redis unavailable."""
        redis = await get_redis()
        if redis is None:
            return False

        try:
            full_key = f"{self.KEY_PREFIX}{key}"
            raw = json.dumps(value, default=str)
            await redis.setex(full_key, ttl_seconds, raw)
            return True
        except Exception as e:
            logger.warning("cache_set_error", key=key, error=str(e))
            return False

    async def delete(self, key: str) -> bool:
        """Delete a cached key. Returns False if Redis unavailable."""
        redis = await get_redis()
        if redis is None:
            return False

        try:
            full_key = f"{self.KEY_PREFIX}{key}"
            await redis.delete(full_key)
            return True
        except Exception as e:
            logger.warning("cache_delete_error", key=key, error=str(e))
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern. Returns count of deleted keys."""
        redis = await get_redis()
        if redis is None:
            return 0

        try:
            full_pattern = f"{self.KEY_PREFIX}{pattern}"
            count = 0
            async for key in redis.scan_iter(match=full_pattern, count=100):
                await redis.delete(key)
                count += 1
            return count
        except Exception as e:
            logger.warning("cache_delete_pattern_error", pattern=pattern, error=str(e))
            return 0


# Module-level singleton
cache_service = CacheService()
