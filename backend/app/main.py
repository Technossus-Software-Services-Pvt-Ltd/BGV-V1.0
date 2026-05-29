from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.db.base import Base
from app.api.routes import upload, documents, candidates, processing, health, batch
from app.api.routes import settings as settings_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


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
app.include_router(upload.router, prefix="/api/v1", tags=["Upload"])
app.include_router(documents.router, prefix="/api/v1", tags=["Documents"])
app.include_router(candidates.router, prefix="/api/v1", tags=["Candidates"])
app.include_router(processing.router, prefix="/api/v1", tags=["Processing"])
app.include_router(batch.router, prefix="/api/v1", tags=["Batch"])
app.include_router(settings_routes.router, prefix="/api/v1", tags=["Settings"])
