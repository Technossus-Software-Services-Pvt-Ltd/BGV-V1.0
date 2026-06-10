import os
# Must be set before any protobuf import — enables compatibility between paddlepaddle 2.x pb2 files and protobuf 4+
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.db.base import Base
from app.api.routes import upload, documents, candidates, processing, health, batch, auth
from app.api.routes import settings as settings_routes
from app.api.routes import dashboard
from app.api.routes import review_queue
from app.api.routes import ws

# Named advisory lock IDs to prevent collisions in PostgreSQL's global lock namespace
ADVISORY_LOCK_DOCUMENT_RECOVERY = 1000001  # Startup: reset stuck documents

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # Ensure upload directory exists at startup
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    # Schema management is handled exclusively by Alembic migrations.
    # Do NOT use Base.metadata.create_all — it can cause schema drift.
    # Start the OCR process pool for CPU-parallel OCR
    from app.services.ocr.process_pool import ocr_process_pool
    ocr_process_pool.startup()
    # Recover documents stuck in intermediate processing states from prior crashes
    await _recover_stuck_documents()
    # Recover batches stuck in processing state from prior crashes
    await _recover_stuck_batches()
    # Recover notifications stuck in queued state from prior crashes
    from app.services.notifications.email_service import NotificationService
    await NotificationService.recover_stuck_notifications()
    yield
    # Graceful shutdown: drain background tasks
    from app.services.task_manager import task_manager
    await task_manager.shutdown(timeout=settings.shutdown_timeout_seconds)
    # Shutdown OCR process pool
    ocr_process_pool.shutdown()
    # Close Redis connection
    from app.services.cache import close_redis
    await close_redis()
    # Cleanup OllamaClient HTTP connections
    from app.services.dependencies import get_ai_classifier
    await get_ai_classifier().client.close()
    await engine.dispose()


async def _recover_stuck_documents():
    """Reset documents stuck in intermediate states back to UPLOADED for reprocessing."""
    from sqlalchemy import update, text
    from app.db.session import AsyncSessionLocal
    from app.models.document import Document
    from app.models.enums import ProcessingStatus
    from app.core.logging import get_logger

    logger = get_logger("startup.recovery")
    stuck_states = [
        ProcessingStatus.NORMALIZING.value,
        ProcessingStatus.OCR_RUNNING.value,
        ProcessingStatus.AI_CLASSIFYING.value,
        ProcessingStatus.VALIDATING.value,
    ]

    async with AsyncSessionLocal() as db:
        # Advisory lock prevents multiple workers from running recovery concurrently
        # Only use advisory locks on PostgreSQL (not supported on SQLite/other DBs)
        is_postgres = "postgresql" in settings.database_url
        try:
            if is_postgres:
                await db.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_DOCUMENT_RECOVERY})
            result = await db.execute(
                update(Document)
                .where(Document.processing_status.in_(stuck_states))
                .values(processing_status=ProcessingStatus.UPLOADED.value)
            )
            if result.rowcount:
                logger.warning("recovered_stuck_documents", count=result.rowcount)
            await db.commit()
        finally:
            if is_postgres:
                await db.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": ADVISORY_LOCK_DOCUMENT_RECOVERY})


ADVISORY_LOCK_BATCH_RECOVERY = 1000002  # Startup: reset stuck batches


async def _recover_stuck_batches():
    """Reset batch imports stuck in 'processing' state back to 'failed' for retry."""
    from sqlalchemy import update, text
    from app.db.session import AsyncSessionLocal
    from app.models.batch_import import BatchImport
    from app.models.enums import BatchImportStatus
    from app.core.logging import get_logger

    logger = get_logger("startup.recovery")

    async with AsyncSessionLocal() as db:
        is_postgres = "postgresql" in settings.database_url
        try:
            if is_postgres:
                await db.execute(text("SELECT pg_advisory_lock(:lock_id)"), {"lock_id": ADVISORY_LOCK_BATCH_RECOVERY})
            result = await db.execute(
                update(BatchImport)
                .where(BatchImport.status == BatchImportStatus.PROCESSING.value)
                .values(
                    status=BatchImportStatus.FAILED.value,
                    error_message="Recovered from crash during processing",
                )
            )
            if result.rowcount:
                logger.warning("recovered_stuck_batches", count=result.rowcount)
            await db.commit()
        finally:
            if is_postgres:
                await db.execute(text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": ADVISORY_LOCK_BATCH_RECOVERY})


# Rate limiter — keyed by client IP
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="BGV Platform - AI-Powered Background Verification",
    description="Production-grade OCR + AI Classification platform for background verification",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(candidates.router, prefix="/api/v1", tags=["Candidates"])
app.include_router(processing.router, prefix="/api/v1", tags=["Processing"])
app.include_router(batch.router, prefix="/api/v1", tags=["Batch"])
app.include_router(settings_routes.router, prefix="/api/v1", tags=["Settings"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(review_queue.router, prefix="/api/v1", tags=["Review Queue"])
app.include_router(ws.router, prefix="/api/v1", tags=["WebSocket"])


# Global exception handler for domain exceptions
from app.core.exceptions import BGVBaseException
from app.core.logging import get_logger

_exc_logger = get_logger("exception_handler")


@app.exception_handler(BGVBaseException)
async def bgv_exception_handler(request: Request, exc: BGVBaseException):
    """Maps domain exceptions to structured JSON error responses."""
    status_code = exc.status_code
    _exc_logger.warning(
        "domain_exception",
        status_code=status_code,
        exception_type=type(exc).__name__,
        message=exc.message,
        correlation_id=exc.correlation_id,
        path=str(request.url.path),
    )
    content = {"detail": exc.message, "error_type": type(exc).__name__}
    if exc.correlation_id:
        content["correlation_id"] = exc.correlation_id
    if exc.details:
        content["details"] = exc.details
    return JSONResponse(status_code=status_code, content=content)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'; frame-ancestors 'none'"
    return response


@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    """Safety net middleware for unhandled exceptions — returns 500 without leaking internals."""
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        # Don't catch domain exceptions (handled by bgv_exception_handler)
        if isinstance(exc, BGVBaseException):
            raise
        _exc_logger.error(
            "unhandled_exception",
            exception_type=type(exc).__name__,
            message=str(exc)[:500],
            path=str(request.url.path),
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error_type": "InternalError"},
        )
