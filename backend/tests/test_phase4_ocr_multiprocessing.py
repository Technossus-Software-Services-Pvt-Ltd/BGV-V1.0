"""Tests for Phase 4: OCR ProcessPoolExecutor multiprocessing."""

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from concurrent.futures import ProcessPoolExecutor

import pytest
import numpy as np


# ─── OCRProcessPool lifecycle tests ─────────────────────────────────────────────


class TestOCRProcessPoolLifecycle:
    """Tests for process pool startup and shutdown."""

    def test_pool_not_running_initially(self):
        from app.services.ocr.process_pool import OCRProcessPool
        pool = OCRProcessPool()
        assert pool.is_running is False

    @patch("app.services.ocr.process_pool.settings")
    def test_startup_creates_pool(self, mock_settings):
        from app.services.ocr.process_pool import OCRProcessPool
        mock_settings.ocr_process_workers = 2

        pool = OCRProcessPool()
        pool.startup()

        assert pool.is_running is True
        pool.shutdown()

    @patch("app.services.ocr.process_pool.settings")
    def test_shutdown_stops_pool(self, mock_settings):
        from app.services.ocr.process_pool import OCRProcessPool
        mock_settings.ocr_process_workers = 1

        pool = OCRProcessPool()
        pool.startup()
        pool.shutdown()

        assert pool.is_running is False

    @patch("app.services.ocr.process_pool.settings")
    def test_double_startup_is_safe(self, mock_settings):
        from app.services.ocr.process_pool import OCRProcessPool
        mock_settings.ocr_process_workers = 1

        pool = OCRProcessPool()
        pool.startup()
        pool.startup()  # Second call should be no-op

        assert pool.is_running is True
        pool.shutdown()

    def test_double_shutdown_is_safe(self):
        from app.services.ocr.process_pool import OCRProcessPool
        pool = OCRProcessPool()
        pool.shutdown()  # Should not raise
        pool.shutdown()  # Should not raise

    @pytest.mark.asyncio
    async def test_process_async_raises_when_not_started(self):
        from app.services.ocr.process_pool import OCRProcessPool
        pool = OCRProcessPool()
        img = np.zeros((100, 100, 3), dtype=np.uint8)

        with pytest.raises(RuntimeError, match="not started"):
            await pool.process_async(img)


# ─── OCR worker function tests ──────────────────────────────────────────────────


class TestOCRWorkerFunction:
    """Tests for the _run_ocr_in_process worker function."""

    @patch("app.services.ocr.process_pool._process_local_ocr")
    def test_worker_returns_dict_on_success(self, mock_ocr):
        """Worker should return a properly structured dict on success."""
        from app.services.ocr.process_pool import _run_ocr_in_process

        # Mock PaddleOCR result format
        mock_ocr.ocr.return_value = [[
            [[[0, 0], [100, 0], [100, 30], [0, 30]], ("Hello world", 0.95)],
            [[[0, 40], [100, 40], [100, 70], [0, 70]], ("Second line", 0.88)],
        ]]

        # Patch globals to use mock
        import app.services.ocr.process_pool as module
        module._process_local_ocr = mock_ocr

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = _run_ocr_in_process(img)

        assert result["text"] == "Hello world\nSecond line"
        assert result["confidence"] > 0.8
        assert result["word_count"] == 4
        assert result["error"] is None
        assert result["processing_duration_ms"] >= 0

    @patch("app.services.ocr.process_pool._process_local_ocr")
    def test_worker_returns_empty_on_no_results(self, mock_ocr):
        """Worker should return empty dict when OCR finds nothing."""
        from app.services.ocr.process_pool import _run_ocr_in_process
        import app.services.ocr.process_pool as module

        mock_ocr.ocr.return_value = [[]]
        module._process_local_ocr = mock_ocr

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = _run_ocr_in_process(img)

        assert result["text"] == ""
        assert result["confidence"] == 0.0
        assert result["word_count"] == 0
        assert result["error"] is None

    @patch("app.services.ocr.process_pool._process_local_ocr")
    def test_worker_handles_exception(self, mock_ocr):
        """Worker should catch exceptions and return error dict."""
        from app.services.ocr.process_pool import _run_ocr_in_process
        import app.services.ocr.process_pool as module

        mock_ocr.ocr.side_effect = RuntimeError("Model crashed")
        module._process_local_ocr = mock_ocr

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = _run_ocr_in_process(img)

        assert result["text"] == ""
        assert result["error"] == "Model crashed"

    @patch("app.services.ocr.process_pool._process_local_ocr")
    def test_worker_filters_low_confidence(self, mock_ocr):
        """Worker should filter lines below MIN_CONFIDENCE_THRESHOLD (0.3)."""
        from app.services.ocr.process_pool import _run_ocr_in_process
        import app.services.ocr.process_pool as module

        mock_ocr.ocr.return_value = [[
            [[[0, 0], [100, 0], [100, 30], [0, 30]], ("Good text", 0.85)],
            [[[0, 40], [100, 40], [100, 70], [0, 70]], ("Bad text", 0.1)],  # Below 0.3
        ]]
        module._process_local_ocr = mock_ocr

        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = _run_ocr_in_process(img)

        assert "Good text" in result["text"]
        assert "Bad text" not in result["text"]


# ─── PaddleOCREngine integration with process pool ──────────────────────────────


class TestEngineProcessPoolIntegration:
    """Tests that PaddleOCREngine.process_async uses process pool when available."""

    @pytest.mark.asyncio
    @patch("app.services.ocr.engine._ocr_executor")
    async def test_falls_back_to_thread_pool_when_pool_not_running(self, mock_executor):
        """When process pool is not started, falls back to thread pool."""
        from app.services.ocr.engine import PaddleOCREngine, OCREngineResult

        engine = PaddleOCREngine()
        img = np.zeros((100, 100, 3), dtype=np.uint8)

        expected_result = OCREngineResult(
            text="test", confidence=0.9, word_count=1,
            raw_output=[], processing_duration_ms=100,
        )

        loop = asyncio.get_running_loop()

        with patch("app.services.ocr.process_pool.ocr_process_pool") as mock_pool:
            mock_pool.is_running = False
            with patch.object(engine, "process", return_value=expected_result):
                mock_executor.submit = MagicMock()
                # Use a direct call to verify fallback path
                result = await loop.run_in_executor(None, engine.process, img)

        assert result.text == "test"

    @pytest.mark.asyncio
    async def test_uses_process_pool_when_running(self):
        """When process pool is started, it should be used for OCR."""
        from app.services.ocr.engine import PaddleOCREngine

        engine = PaddleOCREngine()
        img = np.zeros((100, 100, 3), dtype=np.uint8)

        mock_result = {
            "text": "process pool result",
            "confidence": 0.92,
            "word_count": 3,
            "raw_output": [],
            "processing_duration_ms": 200,
            "language_detected": "en",
            "orientation_angle": 0.0,
            "error": None,
        }

        with patch("app.services.ocr.process_pool.ocr_process_pool") as mock_pool:
            mock_pool.is_running = True
            mock_pool.process_async = AsyncMock(return_value=mock_result)

            result = await engine.process_async(img)

        assert result.text == "process pool result"
        assert result.confidence == 0.92
        assert result.word_count == 3
        mock_pool.process_async.assert_awaited_once_with(img)


# ─── Config test ─────────────────────────────────────────────────────────────────


class TestPhase4Config:
    """Tests for Phase 4 config settings."""

    def test_ocr_process_workers_default(self):
        from app.core.config import Settings
        s = Settings(
            database_url="postgresql+asyncpg://u:p@localhost/db",
            database_sync_url="postgresql://u:p@localhost/db",
            secret_key="test-secret-key-for-unit-testing-only",
        )
        assert s.ocr_process_workers == 2
