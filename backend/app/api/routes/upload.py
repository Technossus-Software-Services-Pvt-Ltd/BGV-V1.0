import re
import uuid
from pathlib import Path
from typing import List, Optional

import aiofiles
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Request
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

# Only allow alphanumeric, hyphens, and underscores for candidate IDs
CANDIDATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,100}$")

# Centralized task manager
from app.services.task_manager import task_manager, TaskType


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    request: Request,
    candidate_id: str = Form(..., min_length=1, max_length=100),
    candidate_name: str = Form(..., min_length=1, max_length=255),
    candidate_dob: Optional[str] = Form(None),
    candidate_gender: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    _current_user: AuthUser = Depends(get_current_user),
):
    if not CANDIDATE_ID_PATTERN.match(candidate_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid candidate_id format")

    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files provided")

    if len(files) > settings.max_files_per_upload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Maximum {settings.max_files_per_upload} files per upload")

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

    # Process each file — track written files for cleanup on failure
    document_records = []
    written_files: List[Path] = []
    try:
        for file in files:
            # Validate file metadata
            validate_upload_file(file)

            # Stream file to disk to avoid buffering entire file in memory
            file_ext = Path(file.filename).suffix.lower()
            stored_name = f"{uuid.uuid4().hex}{file_ext}"
            file_dir = settings.upload_path / correlation_id
            file_dir.mkdir(parents=True, exist_ok=True)
            file_path = file_dir / stored_name

            file_size = 0
            header_bytes = b""
            async with aiofiles.open(file_path, "wb") as f:
                while chunk := await file.read(1024 * 1024):  # 1MB chunks
                    if file_size == 0:
                        header_bytes = chunk[:2048]
                    file_size += len(chunk)
                    if file_size > settings.max_upload_size_bytes:
                        break
                    await f.write(chunk)

            written_files.append(file_path)

            # Remove file if size exceeded
            if file_size > settings.max_upload_size_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File size exceeds {settings.max_upload_size_mb}MB limit",
                )

            # Validate using streamed header bytes and total size
            detected_mime = validate_file_content(header_bytes, file.filename, file_size=file_size)

            # Create document record
            document = Document(
                candidate_id=candidate.id,
                upload_batch_id=batch.id,
                original_filename=file.filename,
                stored_filename=stored_name,
                file_path=str(file_path),
                file_size_bytes=file_size,
                mime_type=detected_mime,
                processing_status=ProcessingStatus.UPLOADED.value,
                correlation_id=correlation_id,
            )
            db.add(document)
            await db.flush()

            document_records.append({
                "id": document.id,
                "filename": file.filename,
                "size_bytes": file_size,
                "mime_type": detected_mime,
                "status": ProcessingStatus.UPLOADED.value,
            })

            # Audit log
            await audit.log(
                correlation_id=correlation_id,
                action=AuditAction.UPLOAD.value,
                message=f"File uploaded: {sanitize_filename(file.filename)} ({file_size} bytes)",
                candidate_id=candidate.id,
                document_id=document.id,
                processing_stage="upload",
                details={"mime_type": detected_mime, "size_bytes": file_size},
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:200],
            )
    except HTTPException:
        # Clean up all files written during this upload attempt
        for fp in written_files:
            fp.unlink(missing_ok=True)
        raise

    await db.commit()

    # Queue background processing for each document (non-blocking asyncio tasks)
    logger.info("upload_complete", batch_reference=batch_reference, file_count=len(files), correlation_id=correlation_id)
    for doc_info in document_records:
        task_manager.submit(
            _process_document_background(doc_info["id"]),
            task_type=TaskType.DOCUMENT_PROCESSING,
            name=f"doc-{doc_info['id'][:8]}",
        )

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
    from app.services.dependencies import get_processing_pipeline

    async with AsyncSessionLocal() as db:
        try:
            logger.info("background_processing_start", document_id=document_id)
            pipeline = get_processing_pipeline(db)
            await pipeline.process_document(document_id)
            await db.commit()
            logger.info("background_processing_complete", document_id=document_id)
        except Exception as e:
            await db.rollback()
            logger.error("background_processing_failed", document_id=document_id, error=str(e))
