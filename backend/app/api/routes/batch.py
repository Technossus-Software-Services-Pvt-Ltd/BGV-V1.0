import uuid
import asyncio
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone

import aiofiles
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.auth_user import AuthUser
from app.models.batch_import import BatchImport
from app.models.batch_import_candidate import BatchImportCandidate
from app.models.batch_log import BatchLog
from app.models.enums import BatchImportStatus, BatchCandidateStatus
from app.services.batch.parser import parse_import_file, ParseError, ParsedCandidate
from app.services.batch.orchestrator import BatchOrchestrator
from app.schemas.batch import (
    BatchUploadResponse,
    BatchImportResponse,
    BatchCandidateResponse,
    BatchDetailResponse,
    BatchLogResponse,
)
from app.core.config import settings
from app.core.logging import get_logger

router = APIRouter(prefix="/batch")
logger = get_logger("api.batch")

from app.services.task_manager import task_manager, TaskType

ALLOWED_IMPORT_EXTENSIONS = {".csv", ".xlsx", ".xls"}


@router.post("/upload", response_model=BatchUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_batch_file(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Upload an Excel/CSV file containing candidate data for batch processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_IMPORT_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Use .csv or .xlsx",
        )

    # Stream file and enforce size limit during read
    max_size = 10 * 1024 * 1024  # 10MB
    chunk_size = 64 * 1024  # 64KB chunks
    chunks = []
    total_size = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > max_size:
            raise HTTPException(status_code=400, detail="Import file must be under 10MB")
        chunks.append(chunk)
    file_bytes = b"".join(chunks)

    correlation_id = str(uuid.uuid4())

    # Generate batch code: BGV_YYYYMMDD001 (incremental per day)
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    prefix = f"BGV_{today_str}"
    count_result = await db.execute(
        select(func.count()).select_from(BatchImport).where(
            BatchImport.batch_code.like(f"{prefix}%")
        )
    )
    seq = (count_result.scalar() or 0) + 1
    batch_code = f"{prefix}{seq:03d}"

    stored_name = f"{uuid.uuid4().hex}{ext}"
    file_dir = settings.upload_path / "batch_imports"
    file_dir.mkdir(parents=True, exist_ok=True)
    file_path = file_dir / stored_name
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_bytes)

    # Create batch import record
    batch = BatchImport(
        batch_code=batch_code,
        original_filename=file.filename,
        stored_filename=stored_name,
        file_path=str(file_path),
        status=BatchImportStatus.UPLOADED.value,
        correlation_id=correlation_id,
    )
    db.add(batch)
    await db.flush()

    # Parse the file
    try:
        batch.status = BatchImportStatus.PARSING.value
        await db.flush()

        parsed_candidates, parse_errors = await asyncio.to_thread(parse_import_file, str(file_path), file.filename)

        if parse_errors:
            logger.warning("batch_parse_warnings", batch_code=batch_code, errors=parse_errors[:10])

        if not parsed_candidates:
            batch.status = BatchImportStatus.PARSE_FAILED.value
            batch.error_message = "No valid candidates found. " + "; ".join(parse_errors[:5])
            await db.commit()
            raise HTTPException(status_code=400, detail=batch.error_message)

        # Create batch candidate records
        for pc in parsed_candidates:
            bc = BatchImportCandidate(
                batch_import_id=batch.id,
                row_number=pc.row_number,
                source_candidate_id=pc.candidate_id,
                source_name=pc.name,
                source_email=pc.email,
                source_phone=pc.phone,
                source_dob=pc.dob,
                source_gender=pc.gender,
                status=BatchCandidateStatus.PENDING.value,
            )
            db.add(bc)

        batch.total_candidates = len(parsed_candidates)
        batch.status = BatchImportStatus.PARSED.value
        await db.commit()

        logger.info("batch_uploaded", batch_code=batch_code, candidates=len(parsed_candidates))

        return BatchUploadResponse(
            batch_id=batch.id,
            batch_code=batch_code,
            total_candidates=len(parsed_candidates),
            correlation_id=correlation_id,
            message=f"File parsed successfully. {len(parsed_candidates)} candidates found."
            + (f" {len(parse_errors)} rows had warnings." if parse_errors else ""),
        )

    except ParseError as e:
        batch.status = BatchImportStatus.PARSE_FAILED.value
        batch.error_message = str(e)
        await db.commit()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{batch_id}/start", response_model=BatchImportResponse)
async def start_batch_processing(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Start processing a parsed batch import."""
    result = await db.execute(select(BatchImport).where(BatchImport.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    if batch.status not in (BatchImportStatus.PARSED.value, BatchImportStatus.FAILED.value,
                            BatchImportStatus.COMPLETED_WITH_ERRORS.value):
        raise HTTPException(
            status_code=400,
            detail=f"Batch is in '{batch.status}' state. Can only start from 'parsed', 'failed', or 'completed_with_errors'.",
        )

    batch.status = BatchImportStatus.PROCESSING.value
    await db.commit()

    # Submit to centralized task manager with concurrency control
    task_manager.submit(
        _process_batch_background(batch_id),
        task_type=TaskType.BATCH_PROCESSING,
        name=f"batch-{batch_id[:8]}",
    )

    return BatchImportResponse.model_validate(batch)


@router.get("", response_model=List[BatchImportResponse])
async def list_batch_imports(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """List all batch imports with optional filters."""
    query = select(BatchImport).order_by(desc(BatchImport.created_at))

    if status_filter:
        query = query.where(BatchImport.status == status_filter)
    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            query = query.where(BatchImport.created_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            query = query.where(BatchImport.created_at <= dt_to)
        except ValueError:
            pass

    result = await db.execute(query.offset(skip).limit(limit))
    batches = result.scalars().all()
    return [BatchImportResponse.model_validate(b) for b in batches]


@router.get("/{batch_id}", response_model=BatchDetailResponse)
async def get_batch_detail(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Get batch import with all candidate details."""
    result = await db.execute(select(BatchImport).where(BatchImport.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    result = await db.execute(
        select(BatchImportCandidate)
        .where(BatchImportCandidate.batch_import_id == batch_id)
        .order_by(BatchImportCandidate.row_number)
    )
    candidates = result.scalars().all()

    return BatchDetailResponse(
        batch=BatchImportResponse.model_validate(batch),
        candidates=[BatchCandidateResponse.model_validate(c) for c in candidates],
    )


@router.get("/{batch_id}/candidates", response_model=List[BatchCandidateResponse])
async def list_batch_candidates(
    batch_id: str,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """List candidates for a batch import with optional status filter."""
    query = select(BatchImportCandidate).where(
        BatchImportCandidate.batch_import_id == batch_id
    )
    if status_filter:
        query = query.where(BatchImportCandidate.status == status_filter)
    query = query.order_by(BatchImportCandidate.row_number)

    result = await db.execute(query)
    candidates = result.scalars().all()
    return [BatchCandidateResponse.model_validate(c) for c in candidates]


@router.post("/{batch_id}/candidates/{candidate_id}/retry", response_model=BatchCandidateResponse)
async def retry_batch_candidate(
    batch_id: str,
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Retry processing a failed candidate."""
    result = await db.execute(
        select(BatchImportCandidate).where(
            BatchImportCandidate.id == candidate_id,
            BatchImportCandidate.batch_import_id == batch_id,
        )
    )
    bc = result.scalar_one_or_none()
    if not bc:
        raise HTTPException(status_code=404, detail="Batch candidate not found")

    if bc.status not in (BatchCandidateStatus.FAILED.value, BatchCandidateStatus.NO_DOCUMENTS.value):
        raise HTTPException(status_code=400, detail=f"Candidate is in '{bc.status}' state. Only 'failed' or 'no_documents' can be retried.")

    task_manager.submit(
        _retry_candidate_background(batch_id, candidate_id),
        task_type=TaskType.BATCH_PROCESSING,
        name=f"retry-{candidate_id[:8]}",
    )
    return BatchCandidateResponse.model_validate(bc)


@router.get("/{batch_id}/logs/all")
async def get_batch_logs(
    batch_id: str,
    candidate_id: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Get all logs for a batch (REST endpoint for audit page)."""
    result = await db.execute(select(BatchImport).where(BatchImport.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    query = (
        select(BatchLog)
        .where(BatchLog.batch_import_id == batch_id)
        .order_by(BatchLog.created_at)
    )
    if candidate_id:
        query = query.where(BatchLog.batch_candidate_id == candidate_id)
    if level:
        query = query.where(BatchLog.level == level)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "batch_import_id": log.batch_import_id,
            "batch_candidate_id": log.batch_candidate_id,
            "level": log.level,
            "stage": log.stage,
            "message": log.message,
            "details": log.details,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]


@router.get("/{batch_id}/logs")
async def stream_batch_logs(
    batch_id: str,
    after: Optional[str] = Query(None, description="Return logs after this log ID"),
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """SSE endpoint for real-time batch processing logs."""
    # Verify batch exists
    result = await db.execute(select(BatchImport).where(BatchImport.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    return StreamingResponse(
        _log_stream_generator(batch_id, after),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _log_stream_generator(batch_id: str, after_id: Optional[str]):
    """Generator for SSE log streaming."""
    from app.db.session import AsyncSessionLocal

    last_id = after_id
    consecutive_empty = 0
    max_empty = 120  # ~2 minutes of no new logs before closing

    # Use a single session for the entire stream to avoid connection pool churn
    async with AsyncSessionLocal() as db:
        while True:
            query = (
                select(BatchLog)
                .where(BatchLog.batch_import_id == batch_id)
                .order_by(BatchLog.created_at)
                .limit(100)
            )
            if last_id:
                # Get the timestamp of the last seen log
                last_result = await db.execute(
                    select(BatchLog.created_at).where(BatchLog.id == last_id)
                )
                last_ts = last_result.scalar_one_or_none()
                if last_ts:
                    query = query.where(BatchLog.created_at > last_ts)

            result = await db.execute(query)
            logs = result.scalars().all()

            if logs:
                consecutive_empty = 0
                for log in logs:
                    data = json.dumps({
                        "id": log.id,
                        "level": log.level,
                        "stage": log.stage,
                        "message": log.message,
                        "details": log.details,
                        "batch_candidate_id": log.batch_candidate_id,
                        "created_at": log.created_at.isoformat(),
                    })
                    yield f"data: {data}\n\n"
                    last_id = log.id
            else:
                consecutive_empty += 1

            # Check if batch is complete
            batch_result = await db.execute(
                select(BatchImport.status).where(BatchImport.id == batch_id)
            )
            batch_status = batch_result.scalar_one_or_none()

            if batch_status in (
                BatchImportStatus.COMPLETED.value,
                BatchImportStatus.COMPLETED_WITH_ERRORS.value,
                BatchImportStatus.FAILED.value,
            ) and consecutive_empty >= 3:
                # Send final event
                yield f"data: {json.dumps({'type': 'complete', 'status': batch_status})}\n\n"
                return

            if consecutive_empty >= max_empty:
                yield f"data: {json.dumps({'type': 'timeout'})}\n\n"
                return

            # Expire cached ORM state so next iteration sees fresh data
            db.expire_all()
            await asyncio.sleep(1)


async def _process_batch_background(batch_import_id: str):
    """Background task for batch processing."""
    from app.db.session import AsyncSessionLocal
    from app.services.dependencies import get_batch_orchestrator

    async with AsyncSessionLocal() as db:
        try:
            logger.info("batch_processing_start", batch_id=batch_import_id)
            orchestrator = get_batch_orchestrator(db)
            await orchestrator.process_batch(batch_import_id)
            logger.info("batch_processing_complete", batch_id=batch_import_id)
        except Exception as e:
            await db.rollback()
            logger.error("batch_processing_failed", batch_id=batch_import_id, error=str(e))


async def _retry_candidate_background(batch_import_id: str, batch_candidate_id: str):
    """Background task for retrying a single candidate."""
    from app.db.session import AsyncSessionLocal
    from app.services.dependencies import get_batch_orchestrator

    async with AsyncSessionLocal() as db:
        try:
            orchestrator = get_batch_orchestrator(db)
            await orchestrator.retry_candidate(batch_import_id, batch_candidate_id)
        except Exception as e:
            await db.rollback()
            logger.error("retry_candidate_failed", batch_candidate_id=batch_candidate_id, error=str(e))



