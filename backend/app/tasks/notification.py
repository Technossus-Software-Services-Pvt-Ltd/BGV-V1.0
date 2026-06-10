"""Celery tasks for email notifications."""

import asyncio

from app.celery_app import celery
from app.core.logging import get_logger

logger = get_logger("tasks.notification")


@celery.task(name="app.tasks.notification.send_notifications", bind=True, max_retries=3)
def send_notifications(self, notification_log_ids: list[str]):
    """Send email notifications for the given log IDs.

    This runs in a Celery worker process with its own event loop.
    """
    logger.info(
        "celery_notifications_start",
        count=len(notification_log_ids),
        task_id=self.request.id,
    )

    try:
        asyncio.run(_send_notifications_async(notification_log_ids))
        logger.info("celery_notifications_complete", count=len(notification_log_ids))
    except Exception as exc:
        logger.error("celery_notifications_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


async def _send_notifications_async(notification_log_ids: list[str]):
    """Async wrapper for notification sending in Celery worker."""
    from app.services.notifications.email_service import NotificationService
    await NotificationService.send_notifications_background(notification_log_ids)
