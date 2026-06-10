"""Celery application factory and configuration.

Usage:
    # Start worker:
    celery -A app.celery_app.celery worker --loglevel=info --pool=prefork --concurrency=4

    # Start beat (optional, for scheduled tasks):
    celery -A app.celery_app.celery beat --loglevel=info
"""

from celery import Celery

from app.core.config import settings

celery = Celery(
    "bgv_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=600,
    task_default_queue="bgv_default",
    task_routes={
        "app.tasks.document.*": {"queue": "bgv_documents"},
        "app.tasks.batch.*": {"queue": "bgv_batches"},
        "app.tasks.notification.*": {"queue": "bgv_notifications"},
    },
)

# Auto-discover task modules
celery.autodiscover_tasks(["app.tasks"])
