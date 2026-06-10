"""Celery tasks for batch processing."""

import asyncio

from app.celery_app import celery
from app.core.logging import get_logger

logger = get_logger("tasks.batch")


@celery.task(name="app.tasks.batch.process_batch", bind=True, max_retries=1)
def process_batch(self, batch_import_id: str):
    """Process a batch import through the pipeline.

    This runs in a Celery worker process with its own event loop and DB session.
    """
    logger.info("celery_batch_start", batch_id=batch_import_id, task_id=self.request.id)

    try:
        asyncio.run(_process_batch_async(batch_import_id))
        logger.info("celery_batch_complete", batch_id=batch_import_id)
    except Exception as exc:
        logger.error("celery_batch_failed", batch_id=batch_import_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)


@celery.task(name="app.tasks.batch.retry_candidate", bind=True, max_retries=2)
def retry_candidate(self, batch_import_id: str, batch_candidate_id: str):
    """Retry processing for a single candidate in a batch."""
    logger.info("celery_retry_candidate_start", candidate_id=batch_candidate_id, task_id=self.request.id)

    try:
        asyncio.run(_retry_candidate_async(batch_import_id, batch_candidate_id))
        logger.info("celery_retry_candidate_complete", candidate_id=batch_candidate_id)
    except Exception as exc:
        logger.error("celery_retry_candidate_failed", candidate_id=batch_candidate_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)


async def _process_batch_async(batch_import_id: str):
    """Async wrapper for batch processing in Celery worker."""
    from app.db.session import AsyncSessionLocal
    from app.services.dependencies import get_batch_orchestrator

    async with AsyncSessionLocal() as db:
        try:
            orchestrator = get_batch_orchestrator(db)
            await orchestrator.process_batch(batch_import_id)
        except Exception as e:
            await db.rollback()
            raise


async def _retry_candidate_async(batch_import_id: str, batch_candidate_id: str):
    """Async wrapper for candidate retry in Celery worker."""
    from app.db.session import AsyncSessionLocal
    from app.services.dependencies import get_batch_orchestrator

    async with AsyncSessionLocal() as db:
        try:
            orchestrator = get_batch_orchestrator(db)
            await orchestrator.retry_candidate(batch_import_id, batch_candidate_id)
        except Exception as e:
            await db.rollback()
            raise
