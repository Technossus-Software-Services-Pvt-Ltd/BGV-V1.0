import os
# Must be set before any protobuf import — enables compatibility between paddlepaddle 2.x pb2 files and protobuf 4+
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.db.base import Base
from app.api.routes import upload, documents, candidates, processing, health, batch, auth
from app.api.routes import settings as settings_routes
from app.api.routes import dashboard
from app.api.routes import review_queue
from app.api.routes import ws

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    if settings.environment == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    # Recover documents stuck in intermediate processing states from prior crashes
    await _recover_stuck_documents()
    # Recover notifications stuck in queued state from prior crashes
    from app.services.notifications.email_service import NotificationService
    await NotificationService.recover_stuck_notifications()
    yield
    # Graceful shutdown: drain background tasks
    from app.services.task_manager import task_manager
    await task_manager.shutdown(timeout=settings.shutdown_timeout_seconds)
    # Cleanup OllamaClient HTTP connections
    from app.api.routes.health import _ollama_client
    await _ollama_client.close()
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
        await db.execute(text("SELECT pg_advisory_lock(42)"))
        try:
            result = await db.execute(
                update(Document)
                .where(Document.processing_status.in_(stuck_states))
                .values(processing_status=ProcessingStatus.UPLOADED.value)
            )
            if result.rowcount:
                logger.warning("recovered_stuck_documents", count=result.rowcount)
            await db.commit()
        finally:
            await db.execute(text("SELECT pg_advisory_unlock(42)"))
            await db.commit()


app = FastAPI(
    title="BGV Platform - AI-Powered Background Verification",
    description="Production-grade OCR + AI Classification platform for background verification",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
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
