import asyncio
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.api.deps import get_db, get_current_user
from app.models.auth_user import AuthUser
from app.models.batch_import_candidate import BatchImportCandidate
from app.models.batch_import import BatchImport
from app.models.notification_log import NotificationLog
from app.models.enums import BatchCandidateStatus
from app.schemas.review_queue import ReviewQueueResponse, ReviewQueueItem
from app.schemas.notification import NotifyRequest, NotifyResponse, NotificationLogItem
from app.services.notifications.email_service import NotificationService
from app.core.logging import get_logger

logger = get_logger("api.review_queue")

router = APIRouter()

from app.services.task_manager import task_manager, TaskType


REVIEW_STATUSES = [
    BatchCandidateStatus.PARTIAL.value,
    BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value,
    BatchCandidateStatus.FAILED.value,
    BatchCandidateStatus.NO_DOCUMENTS.value,
]


@router.get("/review-queue", response_model=ReviewQueueResponse)
async def list_review_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """List candidates that need review: partial, awaiting_required_documents, or failed."""

    # Subquery: get the latest record per source_candidate_id
    latest_subq = (
        select(
            BatchImportCandidate.source_candidate_id,
            func.max(BatchImportCandidate.updated_at).label("max_updated"),
        )
        .where(BatchImportCandidate.status.in_(REVIEW_STATUSES))
        .group_by(BatchImportCandidate.source_candidate_id)
        .subquery()
    )

    # Base query: join batch_import_candidates with batch_imports, filtered to latest per candidate
    base_query = (
        select(BatchImportCandidate, BatchImport.batch_code)
        .join(BatchImport, BatchImportCandidate.batch_import_id == BatchImport.id)
        .join(
            latest_subq,
            (BatchImportCandidate.source_candidate_id == latest_subq.c.source_candidate_id)
            & (BatchImportCandidate.updated_at == latest_subq.c.max_updated),
        )
        .where(BatchImportCandidate.status.in_(REVIEW_STATUSES))
    )

    # Status filter
    if status and status in REVIEW_STATUSES:
        base_query = base_query.where(BatchImportCandidate.status == status)

    # Search filter: match on name, email, candidate_id, or batch_code
    if search:
        search_term = f"%{search}%"
        base_query = base_query.where(
            or_(
                BatchImportCandidate.source_name.ilike(search_term),
                BatchImportCandidate.source_email.ilike(search_term),
                BatchImportCandidate.source_candidate_id.ilike(search_term),
                BatchImport.batch_code.ilike(search_term),
            )
        )

    # Count total matching records
    count_query = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch paginated results
    results = await db.execute(
        base_query
        .order_by(BatchImportCandidate.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    rows = results.all()

    # Get latest notification status per candidate
    candidate_ids = [row[0].id for row in rows]
    notification_map = {}
    if candidate_ids:
        notif_result = await db.execute(
            select(NotificationLog)
            .where(NotificationLog.candidate_id.in_(candidate_ids))
            .order_by(NotificationLog.created_at.desc())
        )
        for notif in notif_result.scalars().all():
            if notif.candidate_id not in notification_map:
                notification_map[notif.candidate_id] = notif

    items = [
        ReviewQueueItem(
            id=bc.id,
            batch_import_id=bc.batch_import_id,
            batch_code=batch_code,
            candidate_id=bc.candidate_id,
            source_candidate_id=bc.source_candidate_id,
            source_name=bc.source_name,
            source_email=bc.source_email,
            status=bc.status,
            documents_found=bc.documents_found,
            documents_processed=bc.documents_processed,
            error_message=bc.error_message,
            notification_status=notification_map[bc.id].status if bc.id in notification_map else None,
            notification_sent_at=notification_map[bc.id].sent_at if bc.id in notification_map else None,
            created_at=bc.created_at,
            updated_at=bc.updated_at,
        )
        for bc, batch_code in rows
    ]

    return ReviewQueueResponse(items=items, total=total)


@router.post("/review-queue/notify", response_model=NotifyResponse, status_code=202)
async def notify_candidates(
    request: NotifyRequest,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Queue email notifications for selected review queue candidates."""
    logger.info("notify_request_received", candidate_count=len(request.candidate_ids))

    if not request.candidate_ids:
        logger.warning("notify_request_empty", detail="No candidate IDs provided")
        raise HTTPException(status_code=400, detail="No candidate IDs provided")

    if len(request.candidate_ids) > 100:
        logger.warning("notify_request_too_large", count=len(request.candidate_ids))
        raise HTTPException(status_code=400, detail="Maximum 100 candidates per request")

    # Validate candidates exist and have reviewable status
    result = await db.execute(
        select(BatchImportCandidate).where(
            BatchImportCandidate.id.in_(request.candidate_ids),
            BatchImportCandidate.status.in_(REVIEW_STATUSES),
        )
    )
    valid_candidates = list(result.scalars().all())
    valid_with_email = [c for c in valid_candidates if c.source_email]

    skipped = len(request.candidate_ids) - len(valid_with_email)

    logger.info("notify_validation", valid=len(valid_candidates), with_email=len(valid_with_email), skipped=skipped)

    if not valid_with_email:
        logger.warning("notify_no_valid_candidates", total_requested=len(request.candidate_ids))
        return NotifyResponse(
            queued=0,
            skipped=skipped,
            message="No valid candidates with email addresses found",
        )

    # Queue notifications
    log_ids = await NotificationService.queue_notifications(
        db, [c.id for c in valid_with_email]
    )

    # Fire background task - does NOT block the response
    logger.info("notify_queued", log_ids=log_ids, count=len(log_ids))
    task_manager.submit(
        NotificationService.send_notifications_background(log_ids),
        task_type=TaskType.NOTIFICATION,
        name=f"notify-batch-{len(log_ids)}",
    )

    return NotifyResponse(
        queued=len(log_ids),
        skipped=skipped,
        message=f"Emails queued for {len(log_ids)} candidate(s)",
    )


@router.get("/review-queue/notifications/{candidate_id}", response_model=List[NotificationLogItem])
async def get_candidate_notifications(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Get notification history for a specific candidate."""
    result = await db.execute(
        select(NotificationLog)
        .where(NotificationLog.candidate_id == candidate_id)
        .order_by(NotificationLog.created_at.desc())
    )
    logs = result.scalars().all()
    return [NotificationLogItem.model_validate(log) for log in logs]


@router.post("/review-queue/notify/retry/{notification_id}", status_code=202)
async def retry_notification(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Retry a failed notification."""
    logger.info("notify_retry_requested", notification_id=notification_id)
    result = await db.execute(
        select(NotificationLog).where(NotificationLog.id == notification_id)
    )
    log_entry = result.scalar_one_or_none()
    if not log_entry:
        logger.warning("notify_retry_not_found", notification_id=notification_id)
        raise HTTPException(status_code=404, detail="Notification not found")

    if log_entry.status != "failed":
        raise HTTPException(status_code=400, detail="Only failed notifications can be retried")

    log_entry.status = "queued"
    log_entry.error_message = None
    await db.commit()

    task_manager.submit(
        NotificationService.send_notifications_background([log_entry.id]),
        task_type=TaskType.NOTIFICATION,
        name=f"notify-retry-{log_entry.id[:8]}",
    )

    return {"message": "Notification retry queued"}
