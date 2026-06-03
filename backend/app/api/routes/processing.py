from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta

from app.api.utils import parse_date_param
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.auth_user import AuthUser
from app.models.processing_event import ProcessingEvent
from app.models.audit_log import AuditLog
from app.models.upload_batch import UploadBatch
from app.models.candidate import Candidate
from app.schemas.processing import ProcessingEventResponse, ProcessingTimelineResponse, UploadBatchResponse
from app.schemas.response import AuditLogResponse

router = APIRouter()


@router.get("/processing/timeline/{document_id}", response_model=ProcessingTimelineResponse)
async def get_processing_timeline(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ProcessingEvent)
        .where(ProcessingEvent.document_id == document_id)
        .order_by(ProcessingEvent.created_at.asc())
    )
    events = result.scalars().all()

    # Return empty timeline if processing hasn't recorded events yet
    total_duration = sum(e.duration_ms for e in events if e.duration_ms) if events else None
    current_status = events[-1].status if events else "pending"

    return ProcessingTimelineResponse(
        document_id=document_id,
        events=events,
        current_status=current_status,
        total_duration_ms=total_duration,
    )


@router.get("/processing/batches", response_model=List[UploadBatchResponse])
async def list_batches(
    candidate_id: str = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    query = select(UploadBatch).options(selectinload(UploadBatch.candidate)).order_by(UploadBatch.created_at.desc())
    if candidate_id:
        query = query.where(UploadBatch.candidate_id == candidate_id)
    if date_from:
        query = query.where(UploadBatch.created_at >= parse_date_param(date_from, "date_from"))
    if date_to:
        query = query.where(UploadBatch.created_at < parse_date_param(date_to, "date_to") + timedelta(days=1))
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    batches = result.scalars().all()
    return [
        UploadBatchResponse(
            id=b.id,
            candidate_id=b.candidate_id,
            candidate_name=b.candidate.name if b.candidate else None,
            batch_reference=b.batch_reference,
            total_files=b.total_files,
            processed_files=b.processed_files,
            failed_files=b.failed_files,
            processing_status=b.processing_status,
            correlation_id=b.correlation_id,
            created_at=b.created_at,
            updated_at=b.updated_at,
        )
        for b in batches
    ]


@router.get("/processing/batches/{batch_id}", response_model=UploadBatchResponse)
async def get_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    result = await db.execute(
        select(UploadBatch).options(selectinload(UploadBatch.candidate)).where(UploadBatch.id == batch_id)
    )
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return UploadBatchResponse(
        id=batch.id,
        candidate_id=batch.candidate_id,
        candidate_name=batch.candidate.name if batch.candidate else None,
        batch_reference=batch.batch_reference,
        total_files=batch.total_files,
        processed_files=batch.processed_files,
        failed_files=batch.failed_files,
        processing_status=batch.processing_status,
        correlation_id=batch.correlation_id,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


@router.get("/audit/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    correlation_id: str = None,
    document_id: str = None,
    candidate_id: str = None,
    action: str = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())

    if correlation_id:
        query = query.where(AuditLog.correlation_id == correlation_id)
    if document_id:
        query = query.where(AuditLog.document_id == document_id)
    if candidate_id:
        query = query.where(AuditLog.candidate_id == candidate_id)
    if action:
        query = query.where(AuditLog.action == action)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()
