"""Task dispatcher that routes work to Celery workers or in-process task manager.

When `settings.celery_enabled` is True, tasks are sent to Celery for external workers.
When False, falls back to the existing in-process asyncio TaskManager (no Celery required).
"""

from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.services.task_manager import task_manager, TaskType

logger = get_logger("task_dispatcher")


class TaskDispatcher:
    """Routes background tasks to Celery or in-process task manager."""

    @property
    def using_celery(self) -> bool:
        return settings.celery_enabled

    def dispatch_document_processing(self, document_id: str) -> Optional[str]:
        """Dispatch document processing. Returns task ID (Celery) or None (in-process)."""
        if self.using_celery:
            from app.tasks.document import process_document
            result = process_document.delay(document_id)
            logger.info("celery_dispatched", task="process_document", document_id=document_id, task_id=result.id)
            return result.id

        # Fallback: in-process
        from app.api.routes.upload import _process_document_background
        task_manager.submit(
            _process_document_background(document_id),
            task_type=TaskType.DOCUMENT_PROCESSING,
            name=f"doc-{document_id[:8]}",
        )
        return None

    def dispatch_batch_processing(self, batch_import_id: str) -> Optional[str]:
        """Dispatch batch processing. Returns task ID (Celery) or None (in-process)."""
        if self.using_celery:
            from app.tasks.batch import process_batch
            result = process_batch.delay(batch_import_id)
            logger.info("celery_dispatched", task="process_batch", batch_id=batch_import_id, task_id=result.id)
            return result.id

        # Fallback: in-process
        from app.api.routes.batch import _process_batch_background
        task_manager.submit(
            _process_batch_background(batch_import_id),
            task_type=TaskType.BATCH_PROCESSING,
            name=f"batch-{batch_import_id[:8]}",
        )
        return None

    def dispatch_retry_candidate(self, batch_import_id: str, batch_candidate_id: str) -> Optional[str]:
        """Dispatch candidate retry. Returns task ID (Celery) or None (in-process)."""
        if self.using_celery:
            from app.tasks.batch import retry_candidate
            result = retry_candidate.delay(batch_import_id, batch_candidate_id)
            logger.info("celery_dispatched", task="retry_candidate", candidate_id=batch_candidate_id, task_id=result.id)
            return result.id

        # Fallback: in-process
        from app.api.routes.batch import _retry_candidate_background
        task_manager.submit(
            _retry_candidate_background(batch_import_id, batch_candidate_id),
            task_type=TaskType.BATCH_PROCESSING,
            name=f"retry-{batch_candidate_id[:8]}",
        )
        return None

    def dispatch_notifications(self, notification_log_ids: list[str]) -> Optional[str]:
        """Dispatch notification sending. Returns task ID (Celery) or None (in-process)."""
        if self.using_celery:
            from app.tasks.notification import send_notifications
            result = send_notifications.delay(notification_log_ids)
            logger.info("celery_dispatched", task="send_notifications", count=len(notification_log_ids), task_id=result.id)
            return result.id

        # Fallback: in-process
        from app.services.notifications.email_service import NotificationService
        task_manager.submit(
            NotificationService.send_notifications_background(notification_log_ids),
            task_type=TaskType.NOTIFICATION,
            name=f"notify-batch-{len(notification_log_ids)}",
        )
        return None


# Module-level singleton
task_dispatcher = TaskDispatcher()
