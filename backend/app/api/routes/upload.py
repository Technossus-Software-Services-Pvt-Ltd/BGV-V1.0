import uuid
import asyncio
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.auth_user import AuthUser
from app.models.candidate import Candidate
from app.models.upload_batch import UploadBatch
from app.models.document import Document
from app.models.enums import ProcessingStatus, AuditAction
from app.core.security import validate_upload_file, validate_file_content, sanitize_filename
from app.core.config import settings
from app.services.audit.logger import AuditService
from app.services.processing.pipeline import ProcessingPipeline
from app.schemas.processing import UploadResponse
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger("api.upload")


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    background_tasks: BackgroundTasks,
    request: Request,
    candidate_id: str = Form(...),
    candidate_name: str = Form(...),
    candidate_dob: Optional[str] = Form(None),
    candidate_gender: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    if len(files) > 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 20 files per upload")

    correlation_id = str(uuid.uuid4())
    logger.info("upload_start", candidate_id=candidate_id, candidate_name=candidate_name, file_count=len(files), correlation_id=correlation_id)
    audit = AuditService(db)

    # Get or create candidate
    result = await db.execute(
        select(Candidate).where(Candidate.candidate_id == candidate_id)
    )
    candidate = result.scalar_one_or_none()

    if not candidate:
        candidate = Candidate(
            candidate_id=candidate_id,
            name=candidate_name,
            dob=candidate_dob,
            gender=candidate_gender,
            correlation_id=correlation_id,
        )
        db.add(candidate)
        await db.flush()
    else:
        # Update dob/gender if provided and not already set
        if candidate_dob and not candidate.dob:
            candidate.dob = candidate_dob
        if candidate_gender and not candidate.gender:
            candidate.gender = candidate_gender
        await db.flush()

    # Create upload batch
    batch_reference = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
    batch = UploadBatch(
        candidate_id=candidate.id,
        batch_reference=batch_reference,
        total_files=len(files),
        processing_status=ProcessingStatus.UPLOADED.value,
        correlation_id=correlation_id,
    )
    db.add(batch)
    await db.flush()

    # Process each file
    document_records = []
    for file in files:
        # Validate file metadata
        validate_upload_file(file)

        # Read file content in chunks to limit memory usage
        chunks = []
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            chunks.append(chunk)
        file_bytes = b"".join(chunks)

        # Validate file content (MIME type check via magic bytes)
        detected_mime = validate_file_content(file_bytes, file.filename)

        # Generate safe storage path
        file_ext = Path(file.filename).suffix.lower()
        stored_name = f"{uuid.uuid4().hex}{file_ext}"
        file_dir = settings.upload_path / correlation_id
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / stored_name

        # Write file asynchronously
        import aiofiles
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)

        # Create document record
        document = Document(
            candidate_id=candidate.id,
            upload_batch_id=batch.id,
            original_filename=file.filename,
            stored_filename=stored_name,
            file_path=str(file_path),
            file_size_bytes=len(file_bytes),
            mime_type=detected_mime,
            processing_status=ProcessingStatus.UPLOADED.value,
            correlation_id=correlation_id,
        )
        db.add(document)
        await db.flush()

        document_records.append({
            "id": document.id,
            "filename": file.filename,
            "size_bytes": len(file_bytes),
            "mime_type": detected_mime,
            "status": ProcessingStatus.UPLOADED.value,
        })

        # Audit log
        await audit.log(
            correlation_id=correlation_id,
            action=AuditAction.UPLOAD.value,
            message=f"File uploaded: {sanitize_filename(file.filename)} ({len(file_bytes)} bytes)",
            candidate_id=candidate.id,
            document_id=document.id,
            processing_stage="upload",
            details={"mime_type": detected_mime, "size_bytes": len(file_bytes)},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:200],
        )

    await db.commit()

    # Queue background processing for each document
    logger.info("upload_complete", batch_reference=batch_reference, file_count=len(files), correlation_id=correlation_id)
    for doc_info in document_records:
        background_tasks.add_task(_process_document_background, doc_info["id"])

    return UploadResponse(
        batch_id=batch.id,
        batch_reference=batch_reference,
        candidate_id=candidate.id,
        documents=document_records,
        total_files=len(files),
        correlation_id=correlation_id,
        message=f"Upload successful. {len(files)} documents queued for processing.",
    )


async def _process_document_background(document_id: str):
    """Background task to process a single document through the pipeline."""
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            logger.info("background_processing_start", document_id=document_id)
            pipeline = ProcessingPipeline(db)
            await pipeline.process_document(document_id)
            await db.commit()
            logger.info("background_processing_complete", document_id=document_id)
        except Exception as e:
            await db.rollback()
            logger.error("background_processing_failed", document_id=document_id, error=str(e))
