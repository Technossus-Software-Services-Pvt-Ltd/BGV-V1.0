"""Centralized async task management for background processing.

Provides:
- Unified task registry with tracking
- Configurable concurrency limiting via semaphores
- Graceful shutdown with task draining
- Exception callback (DRY, not duplicated per module)
- Task cancellation support
- Observable task counts for health checks
"""

import asyncio
from enum import Enum
from typing import Callable, Coroutine, Any, Optional

from app.core.logging import get_logger

logger = get_logger("task_manager")


class TaskType(str, Enum):
    """Categories of background tasks for tracking and concurrency control."""
    DOCUMENT_PROCESSING = "document_processing"
    BATCH_PROCESSING = "batch_processing"
    NOTIFICATION = "notification"


class TaskManager:
    """Manages background async tasks with concurrency control and graceful shutdown.

    Usage:
        task_manager = TaskManager()
        task_manager.submit(my_coroutine(), task_type=TaskType.DOCUMENT_PROCESSING)

        # During shutdown:
        await task_manager.shutdown(timeout=30)
    """

    def __init__(
        self,
        max_document_concurrency: int = 4,
        max_batch_concurrency: int = 2,
        max_notification_concurrency: int = 4,
    ):
        self._tasks: set[asyncio.Task] = set()
        self._semaphores: dict[TaskType, asyncio.Semaphore] = {
            TaskType.DOCUMENT_PROCESSING: asyncio.Semaphore(max_document_concurrency),
            TaskType.BATCH_PROCESSING: asyncio.Semaphore(max_batch_concurrency),
            TaskType.NOTIFICATION: asyncio.Semaphore(max_notification_concurrency),
        }
        self._shutting_down = False

    @property
    def active_count(self) -> int:
        """Total number of active (not-done) tasks."""
        return len(self._tasks)

    def active_count_by_type(self, task_type: TaskType) -> int:
        """Count active tasks of a given type."""
        return sum(
            1 for t in self._tasks
            if not t.done() and getattr(t, "_task_type", None) == task_type
        )

    def submit(
        self,
        coro: Coroutine[Any, Any, Any],
        *,
        task_type: TaskType,
        name: Optional[str] = None,
    ) -> Optional[asyncio.Task]:
        """Submit a coroutine as a managed background task.

        The coroutine will be wrapped with semaphore-based concurrency control.
        Returns the created Task, or None if shutting down.
        """
        if self._shutting_down:
            logger.warning("task_rejected_shutdown", task_type=task_type, name=name)
            return None

        semaphore = self._semaphores.get(task_type)

        async def _wrapped():
            async with semaphore:
                await coro

        task = asyncio.create_task(_wrapped(), name=name)
        task._task_type = task_type  # Tag for tracking
        self._tasks.add(task)
        task.add_done_callback(self._on_task_done)

        logger.debug(
            "task_submitted",
            task_type=task_type,
            name=name,
            active_count=self.active_count,
        )
        return task

    def cancel_by_type(self, task_type: TaskType) -> int:
        """Cancel all active tasks of a given type. Returns count cancelled."""
        cancelled = 0
        for task in list(self._tasks):
            if not task.done() and getattr(task, "_task_type", None) == task_type:
                task.cancel()
                cancelled += 1
        if cancelled:
            logger.info("tasks_cancelled", task_type=task_type, count=cancelled)
        return cancelled

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully drain all tasks, then cancel stragglers after timeout.

        Should be called during application shutdown (lifespan cleanup).
        """
        self._shutting_down = True
        active = [t for t in self._tasks if not t.done()]
        if not active:
            logger.info("shutdown_no_active_tasks")
            return

        logger.info("shutdown_draining", active_count=len(active), timeout=timeout)

        # Wait for tasks to complete up to timeout
        done, pending = await asyncio.wait(active, timeout=timeout)

        if pending:
            logger.warning("shutdown_cancelling_stragglers", count=len(pending))
            for task in pending:
                task.cancel()
            # Give cancelled tasks a moment to clean up
            await asyncio.wait(pending, timeout=5.0)

        logger.info("shutdown_complete", completed=len(done), cancelled=len(pending))

    def get_status(self) -> dict:
        """Return a summary dict suitable for health checks."""
        return {
            "active_tasks": self.active_count,
            "by_type": {
                tt.value: self.active_count_by_type(tt)
                for tt in TaskType
            },
            "shutting_down": self._shutting_down,
        }

    def _on_task_done(self, task: asyncio.Task) -> None:
        """Callback when a task completes — remove from registry, log exceptions."""
        self._tasks.discard(task)

        if task.cancelled():
            logger.debug("task_cancelled", name=task.get_name())
            return

        exc = task.exception()
        if exc:
            logger.error(
                "background_task_failed",
                name=task.get_name(),
                task_type=getattr(task, "_task_type", "unknown"),
                error=str(exc),
                exc_info=exc,
            )


# Module-level singleton instance — reads concurrency from settings
from app.core.config import settings as _settings

task_manager = TaskManager(
    max_document_concurrency=_settings.max_document_concurrency,
    max_batch_concurrency=_settings.max_batch_concurrency,
    max_notification_concurrency=_settings.max_notification_concurrency,
)
