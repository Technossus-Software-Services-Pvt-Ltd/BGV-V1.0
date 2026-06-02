from datetime import datetime, timezone, timedelta
import time
from typing import Any, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case, cast, Date

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.auth_user import AuthUser
from app.models.document import Document
from app.models.batch_import import BatchImport
from app.models.batch_import_candidate import BatchImportCandidate
from app.models.validation_result import ValidationResult
from app.models.enums import ProcessingStatus, BatchImportStatus, ValidationStatus

router = APIRouter(prefix="/dashboard")

# Simple time-based cache for dashboard stats (30 second TTL)
_dashboard_cache: dict[str, Any] = {"data": None, "expires_at": 0.0}


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    """Aggregate stats for the dashboard."""

    # Return cached result if still fresh
    if _dashboard_cache["data"] is not None and time.time() < _dashboard_cache["expires_at"]:
        return _dashboard_cache["data"]

    # --- Document Stats ---
    doc_status_result = await db.execute(
        select(
            Document.processing_status,
            func.count(Document.id),
        ).group_by(Document.processing_status)
    )
    doc_by_status = {row[0]: row[1] for row in doc_status_result.all()}

    total_documents = sum(doc_by_status.values())
    completed_docs = doc_by_status.get(ProcessingStatus.COMPLETED.value, 0)
    failed_docs = doc_by_status.get(ProcessingStatus.FAILED.value, 0) + doc_by_status.get(ProcessingStatus.OCR_FAILED.value, 0)
    skipped_docs = doc_by_status.get(ProcessingStatus.SKIPPED.value, 0)
    in_progress_docs = total_documents - completed_docs - failed_docs - skipped_docs

    # --- Batch Stats ---
    batch_status_result = await db.execute(
        select(
            BatchImport.status,
            func.count(BatchImport.id),
        ).group_by(BatchImport.status)
    )
    batch_by_status = {row[0]: row[1] for row in batch_status_result.all()}
    total_batches = sum(batch_by_status.values())

    # --- Candidate Stats ---
    total_candidates_result = await db.execute(
        select(func.count(BatchImportCandidate.id))
    )
    total_candidates = total_candidates_result.scalar() or 0

    # --- Ownership Verification Stats ---
    validation_result = await db.execute(
        select(
            ValidationResult.validation_status,
            func.count(ValidationResult.id),
        ).group_by(ValidationResult.validation_status)
    )
    validation_by_status = {row[0]: row[1] for row in validation_result.all()}

    ownership_matched = validation_by_status.get(ValidationStatus.MATCHED.value, 0)
    ownership_partial = validation_by_status.get(ValidationStatus.PARTIAL_MATCH.value, 0)
    ownership_unmatched = validation_by_status.get(ValidationStatus.UNMATCHED.value, 0)

    # --- Daily document processing (last 7 days) ---
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    daily_result = await db.execute(
        select(
            cast(Document.created_at, Date).label("date"),
            func.count(Document.id).label("count"),
        )
        .where(Document.created_at >= seven_days_ago)
        .group_by(cast(Document.created_at, Date))
        .order_by(cast(Document.created_at, Date))
    )
    daily_docs = [{"date": row[0].isoformat(), "count": row[1]} for row in daily_result.all()]

    # --- Daily batches (last 7 days) ---
    daily_batch_result = await db.execute(
        select(
            cast(BatchImport.created_at, Date).label("date"),
            func.count(BatchImport.id).label("count"),
        )
        .where(BatchImport.created_at >= seven_days_ago)
        .group_by(cast(BatchImport.created_at, Date))
        .order_by(cast(BatchImport.created_at, Date))
    )
    daily_batches = [{"date": row[0].isoformat(), "count": row[1]} for row in daily_batch_result.all()]

    # --- Document type distribution (from classifications) ---
    from app.models.classification import AIClassification
    doc_type_result = await db.execute(
        select(
            AIClassification.document_type,
            func.count(AIClassification.id),
        ).group_by(AIClassification.document_type)
    )
    doc_types = [{"type": row[0], "count": row[1]} for row in doc_type_result.all()]

    result = {
        "summary": {
            "total_documents": total_documents,
            "completed_documents": completed_docs,
            "failed_documents": failed_docs,
            "skipped_documents": skipped_docs,
            "in_progress_documents": in_progress_docs,
            "total_batches": total_batches,
            "total_candidates": total_candidates,
        },
        "document_status": [
            {"status": "Completed", "count": completed_docs},
            {"status": "Failed", "count": failed_docs},
            {"status": "Skipped", "count": skipped_docs},
            {"status": "In Progress", "count": in_progress_docs},
        ],
        "batch_status": [
            {"status": k, "count": v} for k, v in batch_by_status.items()
        ],
        "ownership_verification": [
            {"status": "Matched", "count": ownership_matched},
            {"status": "Partial", "count": ownership_partial},
            {"status": "Unmatched", "count": ownership_unmatched},
        ],
        "daily_documents": daily_docs,
        "daily_batches": daily_batches,
        "document_types": doc_types,
    }

    _dashboard_cache["data"] = result
    _dashboard_cache["expires_at"] = time.time() + 30

    return result
