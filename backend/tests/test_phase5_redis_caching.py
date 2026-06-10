"""Tests for Phase 5: Redis caching service."""

import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─── CacheService unit tests ────────────────────────────────────────────────────


class TestCacheServiceGet:
    """Tests for CacheService.get()."""

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_returns_none_when_redis_unavailable(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_get_redis.return_value = None
        svc = CacheService()

        result = await svc.get("some_key")
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_returns_none_on_cache_miss(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        mock_get_redis.return_value = mock_redis
        svc = CacheService()

        result = await svc.get("missing_key")
        assert result is None
        mock_redis.get.assert_awaited_once_with("bgv:missing_key")

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_returns_deserialized_value_on_hit(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_redis = AsyncMock()
        mock_redis.get.return_value = json.dumps({"count": 42})
        mock_get_redis.return_value = mock_redis
        svc = CacheService()

        result = await svc.get("hit_key")
        assert result == {"count": 42}

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_returns_none_on_redis_error(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ConnectionError("Redis down")
        mock_get_redis.return_value = mock_redis
        svc = CacheService()

        result = await svc.get("error_key")
        assert result is None


class TestCacheServiceSet:
    """Tests for CacheService.set()."""

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_returns_false_when_redis_unavailable(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_get_redis.return_value = None
        svc = CacheService()

        result = await svc.set("key", {"data": 1})
        assert result is False

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_sets_value_with_ttl(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        svc = CacheService()

        result = await svc.set("my_key", {"data": 1}, ttl_seconds=60)
        assert result is True
        mock_redis.setex.assert_awaited_once_with(
            "bgv:my_key", 60, json.dumps({"data": 1})
        )

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_returns_false_on_redis_error(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = ConnectionError("Redis down")
        mock_get_redis.return_value = mock_redis
        svc = CacheService()

        result = await svc.set("key", "val")
        assert result is False


class TestCacheServiceDelete:
    """Tests for CacheService.delete()."""

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_deletes_key(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        svc = CacheService()

        result = await svc.delete("old_key")
        assert result is True
        mock_redis.delete.assert_awaited_once_with("bgv:old_key")

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_returns_false_when_redis_unavailable(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_get_redis.return_value = None
        svc = CacheService()

        result = await svc.delete("key")
        assert result is False


class TestCacheServiceDeletePattern:
    """Tests for CacheService.delete_pattern()."""

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_deletes_matching_keys(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_redis = AsyncMock()

        # Mock scan_iter as async generator
        async def mock_scan_iter(**kwargs):
            for key in ["bgv:candidates:list:0:50", "bgv:candidates:list:50:50"]:
                yield key

        mock_redis.scan_iter = mock_scan_iter
        mock_get_redis.return_value = mock_redis
        svc = CacheService()

        count = await svc.delete_pattern("candidates:list:*")
        assert count == 2
        assert mock_redis.delete.await_count == 2

    @pytest.mark.asyncio
    @patch("app.services.cache.get_redis")
    async def test_returns_zero_when_redis_unavailable(self, mock_get_redis):
        from app.services.cache import CacheService
        mock_get_redis.return_value = None
        svc = CacheService()

        count = await svc.delete_pattern("anything:*")
        assert count == 0


# ─── Redis connection tests ──────────────────────────────────────────────────────


class TestRedisConnection:
    """Tests for Redis connection management."""

    @pytest.mark.asyncio
    @patch("app.services.cache.settings")
    async def test_returns_none_when_disabled(self, mock_settings):
        from app.services.cache import get_redis
        import app.services.cache as cache_module

        # Reset global state
        cache_module._redis_client = None
        mock_settings.redis_enabled = False

        result = await get_redis()
        assert result is None

    @pytest.mark.asyncio
    async def test_close_redis_is_safe_when_not_connected(self):
        from app.services.cache import close_redis
        import app.services.cache as cache_module

        cache_module._redis_client = None
        await close_redis()  # Should not raise


# ─── Config tests ────────────────────────────────────────────────────────────────


class TestPhase5Config:
    """Tests for Phase 5 Redis config settings."""

    def test_redis_url_default(self):
        from app.core.config import Settings
        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            database_sync_url="postgresql://u:p@localhost/db",
            secret_key="test-secret-key-for-unit-testing-only",
        )
        assert s.redis_url == "redis://localhost:6379/0"

    def test_redis_enabled_default(self):
        from app.core.config import Settings
        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            database_sync_url="postgresql://u:p@localhost/db",
            secret_key="test-secret-key-for-unit-testing-only",
        )
        assert s.redis_enabled is True


# ─── Dashboard cache integration tests ───────────────────────────────────────────


class TestDashboardCacheIntegration:
    """Tests that dashboard uses Redis cache when available."""

    @pytest.mark.asyncio
    @patch("app.api.routes.dashboard.cache_service")
    async def test_dashboard_returns_redis_cached_result(self, mock_cache):
        """When Redis has cached data, dashboard should return it immediately."""
        mock_cache.get = AsyncMock(return_value={"summary": {"total_documents": 5}})

        from app.api.routes.dashboard import get_dashboard_stats

        # Create mock dependencies
        mock_db = AsyncMock()
        mock_user = MagicMock()

        result = await get_dashboard_stats(db=mock_db, _current_user=mock_user)
        assert result == {"summary": {"total_documents": 5}}
        mock_cache.get.assert_awaited_once()
        # DB should NOT have been queried
        mock_db.execute.assert_not_awaited()
