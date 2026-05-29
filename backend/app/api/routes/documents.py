from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.db.session import get_db
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
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(Document).order_by(Document.created_at.desc())

    if candidate_id:
        query = query.where(Document.candidate_id == candidate_id)
    if status_filter:
        query = query.where(Document.processing_status == status_filter)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    documents = result.scalars().all()
    return documents


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    # Get document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # Get candidate name
    candidate_name = None
    if document.candidate_id:
        cand_result = await db.execute(select(Candidate).where(Candidate.id == document.candidate_id))
        candidate = cand_result.scalar_one_or_none()
        if candidate:
            candidate_name = candidate.name

    # Get pages
    pages_result = await db.execute(
        select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number)
    )
    pages = pages_result.scalars().all()

    # Get OCR results
    ocr_result = await db.execute(
        select(OCRResult).where(OCRResult.document_id == document_id)
    )
    ocr_results = ocr_result.scalars().all()

    # Get classifications
    class_result = await db.execute(
        select(AIClassification).where(AIClassification.document_id == document_id)
    )
    classifications = class_result.scalars().all()

    # Get validation results
    val_result = await db.execute(
        select(ValidationResult).where(ValidationResult.document_id == document_id)
    )
    validation_results = val_result.scalars().all()

    return DocumentDetailResponse(
        document=document,
        candidate_name=candidate_name,
        pages=pages,
        ocr_results=ocr_results,
        classifications=classifications,
        validation_results=validation_results,
    )


@router.get("/documents/{document_id}/ocr", response_model=List[OCRResultResponse])
async def get_document_ocr(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OCRResult).where(OCRResult.document_id == document_id)
    )
    return result.scalars().all()


@router.get("/documents/{document_id}/classification", response_model=List[ClassificationResponse])
async def get_document_classification(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AIClassification).where(AIClassification.document_id == document_id)
    )
    return result.scalars().all()


@router.get("/documents/{document_id}/validation", response_model=List[ValidationResultResponse])
async def get_document_validation(
    document_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ValidationResult).where(ValidationResult.document_id == document_id)
    )
    return result.scalars().all()
