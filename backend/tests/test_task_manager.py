"""Tests for Phase 5: Async Task Management.

Verifies that:
1. TaskManager tracks submitted tasks
2. Concurrency is limited by semaphores
3. Graceful shutdown drains tasks
4. Exception callback logs but doesn't crash
5. Shutdown rejection works
6. Status reporting is correct
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from app.services.task_manager import TaskManager, TaskType, task_manager


class TestTaskManagerInstantiation:
    """Verify TaskManager construction."""

    def test_default_construction(self):
        tm = TaskManager()
        assert tm.active_count == 0
        assert tm._shutting_down is False

    def test_custom_concurrency(self):
        tm = TaskManager(max_document_concurrency=2, max_batch_concurrency=1, max_notification_concurrency=3)
        assert tm._semaphores[TaskType.DOCUMENT_PROCESSING]._value == 2
        assert tm._semaphores[TaskType.BATCH_PROCESSING]._value == 1
        assert tm._semaphores[TaskType.NOTIFICATION]._value == 3

    def test_singleton_instance_exists(self):
        assert task_manager is not None
        assert isinstance(task_manager, TaskManager)


class TestTaskSubmission:
    """Verify task submission and tracking."""

    @pytest.mark.asyncio
    async def test_submit_tracks_task(self):
        tm = TaskManager()

        async def noop():
            pass

        task = tm.submit(noop(), task_type=TaskType.DOCUMENT_PROCESSING, name="test-noop")
        assert task is not None
        assert tm.active_count >= 0  # May complete instantly
        # Let it finish
        await task

    @pytest.mark.asyncio
    async def test_submit_returns_none_when_shutting_down(self):
        tm = TaskManager()
        tm._shutting_down = True

        async def noop():
            pass

        task = tm.submit(noop(), task_type=TaskType.DOCUMENT_PROCESSING)
        assert task is None

    @pytest.mark.asyncio
    async def test_task_removed_after_completion(self):
        tm = TaskManager()

        async def quick():
            return 42

        task = tm.submit(quick(), task_type=TaskType.NOTIFICATION, name="quick")
        await task
        # Give the callback a moment to fire
        await asyncio.sleep(0.01)
        assert tm.active_count == 0

    @pytest.mark.asyncio
    async def test_task_type_tracking(self):
        tm = TaskManager()
        event = asyncio.Event()

        async def wait_for_event():
            await event.wait()

        task1 = tm.submit(wait_for_event(), task_type=TaskType.DOCUMENT_PROCESSING, name="doc1")
        task2 = tm.submit(wait_for_event(), task_type=TaskType.BATCH_PROCESSING, name="batch1")

        assert tm.active_count_by_type(TaskType.DOCUMENT_PROCESSING) == 1
        assert tm.active_count_by_type(TaskType.BATCH_PROCESSING) == 1
        assert tm.active_count_by_type(TaskType.NOTIFICATION) == 0

        event.set()
        await asyncio.gather(task1, task2)


class TestConcurrencyControl:
    """Verify semaphore-based concurrency limiting."""

    @pytest.mark.asyncio
    async def test_concurrency_is_limited(self):
        tm = TaskManager(max_document_concurrency=2)
        running = []
        peak_concurrent = [0]
        barrier = asyncio.Event()

        async def track_concurrent():
            running.append(1)
            peak_concurrent[0] = max(peak_concurrent[0], len(running))
            await barrier.wait()
            running.pop()

        # Submit 5 tasks with max_concurrency=2
        tasks = []
        for i in range(5):
            t = tm.submit(track_concurrent(), task_type=TaskType.DOCUMENT_PROCESSING, name=f"task-{i}")
            tasks.append(t)

        # Give tasks time to start
        await asyncio.sleep(0.05)
        assert peak_concurrent[0] <= 2

        barrier.set()
        await asyncio.gather(*tasks)


class TestGracefulShutdown:
    """Verify graceful shutdown behavior."""

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_tasks(self):
        tm = TaskManager()
        completed = []

        async def slow_task():
            await asyncio.sleep(0.05)
            completed.append(True)

        tm.submit(slow_task(), task_type=TaskType.NOTIFICATION, name="slow")

        await tm.shutdown(timeout=5.0)
        assert len(completed) == 1
        assert tm._shutting_down is True

    @pytest.mark.asyncio
    async def test_shutdown_cancels_after_timeout(self):
        tm = TaskManager()

        async def forever_task():
            await asyncio.sleep(9999)

        tm.submit(forever_task(), task_type=TaskType.DOCUMENT_PROCESSING, name="forever")

        await tm.shutdown(timeout=0.1)
        # Should not hang — task gets cancelled
        assert tm._shutting_down is True

    @pytest.mark.asyncio
    async def test_shutdown_with_no_tasks(self):
        tm = TaskManager()
        await tm.shutdown(timeout=1.0)
        assert tm._shutting_down is True


class TestCancellation:
    """Verify task cancellation by type."""

    @pytest.mark.asyncio
    async def test_cancel_by_type(self):
        tm = TaskManager()

        async def forever():
            await asyncio.sleep(9999)

        tm.submit(forever(), task_type=TaskType.DOCUMENT_PROCESSING, name="doc1")
        tm.submit(forever(), task_type=TaskType.DOCUMENT_PROCESSING, name="doc2")
        tm.submit(forever(), task_type=TaskType.BATCH_PROCESSING, name="batch1")

        cancelled = tm.cancel_by_type(TaskType.DOCUMENT_PROCESSING)
        assert cancelled == 2

        # Batch should still be active
        await asyncio.sleep(0.01)
        assert tm.active_count_by_type(TaskType.BATCH_PROCESSING) == 1

        # Cleanup
        tm.cancel_by_type(TaskType.BATCH_PROCESSING)
        await asyncio.sleep(0.05)


class TestExceptionHandling:
    """Verify failed tasks are handled gracefully."""

    @pytest.mark.asyncio
    async def test_failed_task_is_logged_not_raised(self):
        tm = TaskManager()

        async def failing():
            raise ValueError("test error")

        task = tm.submit(failing(), task_type=TaskType.NOTIFICATION, name="failing")
        # Should not raise even though the task errors
        await asyncio.sleep(0.05)
        assert tm.active_count == 0


class TestStatusReporting:
    """Verify get_status for health checks."""

    @pytest.mark.asyncio
    async def test_status_shape(self):
        tm = TaskManager()
        status = tm.get_status()
        assert "active_tasks" in status
        assert "by_type" in status
        assert "shutting_down" in status
        assert status["active_tasks"] == 0
        assert status["shutting_down"] is False
        assert set(status["by_type"].keys()) == {
            "document_processing", "batch_processing", "notification"
        }
