from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import date, datetime, timedelta

from app.api.utils import parse_date_param
from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.auth_user import AuthUser
from app.models.document import Document, DocumentPage
from app.models.ocr_result import OCRResult
from app.models.classification import AIClassification
from app.models.validation_result import ValidationResult
from app.models.candidate import Candidate
from app.schemas.document import (
    DocumentResponse,
    DocumentDetailResponse,
    DocumentPageResponse,
    OCRResultResponse,
    ClassificationResponse,
    ValidationResultResponse,
)

router = APIRouter()


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    candidate_id: str = None,
    status_filter: str = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    query = select(Document).order_by(Document.created_at.desc())

    if candidate_id:
        query = query.where(Document.candidate_id == candidate_id)
    if status_filter:
        query = query.where(Document.processing_status == status_filter)
    if date_from:
        query = query.where(Document.created_at >= parse_date_param(date_from, "date_from"))
    if date_to:
        query = query.where(Document.created_at < parse_date_param(date_to, "date_to") + timedelta(days=1))

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().all()

    # Enrich with best validation per document using a single optimized query
    doc_ids = [doc.id for doc in documents]
    val_map = {}
    if doc_ids:
        # Subquery: max ownership_score per document_id
        best_score_subq = (
            select(
                ValidationResult.document_id,
                func.max(ValidationResult.ownership_score).label("max_score"),
            )
            .where(ValidationResult.document_id.in_(doc_ids))
            .group_by(ValidationResult.document_id)
            .subquery()
        )
        # Join to get full validation row for the best score
        val_result = await db.execute(
            select(ValidationResult)
            .join(
                best_score_subq,
                (ValidationResult.document_id == best_score_subq.c.document_id)
                & (ValidationResult.ownership_score == best_score_subq.c.max_score),
            )
        )
        for v in val_result.scalars().all():
            val_map[v.document_id] = v

    responses = []
    for doc in documents:
        resp = DocumentResponse.model_validate(doc)
        val = val_map.get(doc.id)
        if val:
            resp.validation_status = val.validation_status
            resp.ownership_confirmed = val.ownership_confirmed
            resp.validated_at = val.created_at
        responses.append(resp)

    return responses


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    # Get document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Fetch all related data in parallel-safe batched queries (single filter)
    pages_result, ocr_result, class_result, val_result = await _fetch_document_relations(
        db, document_id
    )

    candidate_name = None
    if document.candidate_id:
        cand_result = await db.execute(select(Candidate).where(Candidate.id == document.candidate_id))
        candidate = cand_result.scalar_one_or_none()
        if candidate:
            candidate_name = candidate.name

    return DocumentDetailResponse(
        document=document,
        candidate_name=candidate_name,
        pages=pages_result,
        ocr_results=ocr_result,
        classifications=class_result,
        validation_results=val_result,
    )


async def _fetch_document_relations(db: AsyncSession, document_id: str):
    """Fetch all document-related records in minimal queries."""
    pages_result = await db.execute(
        select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number)
    )
    ocr_result = await db.execute(select(OCRResult).where(OCRResult.document_id == document_id))
    class_result = await db.execute(select(AIClassification).where(AIClassification.document_id == document_id))
    val_result = await db.execute(select(ValidationResult).where(ValidationResult.document_id == document_id))

    return (
        pages_result.scalars().all(),
        ocr_result.scalars().all(),
        class_result.scalars().all(),
        val_result.scalars().all(),
    )


@router.get("/documents/{document_id}/ocr", response_model=List[OCRResultResponse])
async def get_document_ocr(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    result = await db.execute(
        select(OCRResult).where(OCRResult.document_id == document_id)
    )
    return result.scalars().all()


@router.get("/documents/{document_id}/classification", response_model=List[ClassificationResponse])
async def get_document_classification(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    result = await db.execute(
        select(AIClassification).where(AIClassification.document_id == document_id)
    )
    return result.scalars().all()


@router.get("/documents/{document_id}/validation", response_model=List[ValidationResultResponse])
async def get_document_validation(
    document_id: str,
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    result = await db.execute(
        select(ValidationResult).where(ValidationResult.document_id == document_id)
    )
    return result.scalars().all()
