"""Celery tasks for document processing."""

import asyncio

from app.celery_app import celery
from app.core.logging import get_logger

logger = get_logger("tasks.document")


@celery.task(name="app.tasks.document.process_document", bind=True, max_retries=2)
def process_document(self, document_id: str):
    """Process a single document through the OCR/AI pipeline.

    This runs in a Celery worker process. It creates its own async event loop
    and DB session since it runs outside the FastAPI context.
    """
    logger.info("celery_document_start", document_id=document_id, task_id=self.request.id)

    try:
        asyncio.run(_process_document_async(document_id))
        logger.info("celery_document_complete", document_id=document_id)
    except Exception as exc:
        logger.error("celery_document_failed", document_id=document_id, error=str(exc))
        raise self.retry(exc=exc, countdown=30)


async def _process_document_async(document_id: str):
    """Async wrapper for document processing in Celery worker."""
    from app.db.session import AsyncSessionLocal
    from app.services.dependencies import get_processing_pipeline

    async with AsyncSessionLocal() as db:
        try:
            pipeline = get_processing_pipeline(db)
            await pipeline.process_document(document_id)
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise
