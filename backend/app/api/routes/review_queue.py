from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.api.deps import get_db
from app.models.batch_import_candidate import BatchImportCandidate
from app.models.batch_import import BatchImport
from app.models.enums import BatchCandidateStatus
from app.schemas.review_queue import ReviewQueueResponse, ReviewQueueItem

router = APIRouter()

REVIEW_STATUSES = [
    BatchCandidateStatus.PARTIAL.value,
    BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value,
    BatchCandidateStatus.FAILED.value,
]


@router.get("/review-queue", response_model=ReviewQueueResponse)
async def list_review_queue(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=200),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List candidates that need review: partial, awaiting_required_documents, or failed."""

    # Base query: join batch_import_candidates with batch_imports
    base_query = (
        select(BatchImportCandidate, BatchImport.batch_code)
        .join(BatchImport, BatchImportCandidate.batch_import_id == BatchImport.id)
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
            created_at=bc.created_at,
            updated_at=bc.updated_at,
        )
        for bc, batch_code in rows
    ]

    return ReviewQueueResponse(items=items, total=total)
