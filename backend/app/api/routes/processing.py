from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.session import get_db
from app.models.processing_event import ProcessingEvent
from app.models.audit_log import AuditLog
from app.models.upload_batch import UploadBatch
from app.schemas.processing import ProcessingEventResponse, ProcessingTimelineResponse, UploadBatchResponse
from app.schemas.response import AuditLogResponse

router = APIRouter()


@router.get("/processing/timeline/{document_id}", response_model=ProcessingTimelineResponse)
async def get_processing_timeline(
    document_id: str,
    db: AsyncSession = Depends(get_db),
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
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(UploadBatch).order_by(UploadBatch.created_at.desc())
    if candidate_id:
        query = query.where(UploadBatch.candidate_id == candidate_id)
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/processing/batches/{batch_id}", response_model=UploadBatchResponse)
async def get_batch(
    batch_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(UploadBatch).where(UploadBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")
    return batch


@router.get("/audit/logs", response_model=List[AuditLogResponse])
async def get_audit_logs(
    correlation_id: str = None,
    document_id: str = None,
    candidate_id: str = None,
    action: str = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
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
