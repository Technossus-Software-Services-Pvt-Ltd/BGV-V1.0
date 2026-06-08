"""Service responsible for downloading and saving documents to disk/DB."""

import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import aiofiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.upload_batch import UploadBatch
from app.models.document import Document
from app.models.enums import ProcessingStatus, AuditAction
from app.services.integrations.gmail_scanner import GmailScanner, DiscoveredAttachment
from app.services.integrations.drive_service import GoogleDriveService, DiscoveredDriveFile
from app.services.audit.logger import AuditService
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("batch.ingest")

# Dedicated thread pool for blocking Google API I/O calls
_io_executor = ThreadPoolExecutor(max_workers=settings.google_io_pool_size, thread_name_prefix="google-io")


class DocumentIngestService:
    """Handles downloading discovered documents and saving them to local storage + DB."""

    def __init__(self, db: AsyncSession, audit: AuditService):
        self.db = db
        self.audit = audit

    async def download_and_save(
        self,
        candidate: Candidate,
        upload_batch: UploadBatch,
        gmail_scanner: Optional[GmailScanner],
        drive_service: Optional[GoogleDriveService],
        gmail_attachments: list[DiscoveredAttachment],
        drive_files: list[DiscoveredDriveFile],
        correlation_id: str,
    ) -> tuple[list[str], int]:
        """Download all discovered documents and save to disk.

        Returns (document_ids, failed_count).
        """
        document_ids = []
        failed_count = 0

        # Download Gmail attachments
        for att in gmail_attachments:
            try:
                loop = asyncio.get_running_loop()
                file_bytes = await loop.run_in_executor(
                    _io_executor, gmail_scanner.download_attachment, att.message_id, att.attachment_id
                )
                doc_id = await self._save_document(
                    candidate, upload_batch, att.filename, att.mime_type, file_bytes,
                    correlation_id,
                )
                document_ids.append(doc_id)
            except Exception as e:
                failed_count += 1
                logger.error("gmail_download_failed", filename=att.filename, error=str(e))
                raise

        # Download Drive files
        for df in drive_files:
            try:
                loop = asyncio.get_running_loop()
                file_bytes = await loop.run_in_executor(
                    _io_executor, drive_service.download_file, df.file_id, df.mime_type
                )
                filename = df.filename
                mime = df.mime_type
                if mime in GoogleDriveService.EXPORTABLE_MIMES:
                    filename = Path(filename).stem + ".pdf"
                    mime = "application/pdf"
                doc_id = await self._save_document(
                    candidate, upload_batch, filename, mime, file_bytes,
                    correlation_id,
                )
                document_ids.append(doc_id)
            except Exception as e:
                failed_count += 1
                logger.error("drive_download_failed", filename=df.filename, error=str(e))
                raise

        return document_ids, failed_count

    async def _save_document(
        self,
        candidate: Candidate,
        upload_batch: UploadBatch,
        filename: str,
        mime_type: str,
        file_bytes: bytes,
        correlation_id: str,
    ) -> str:
        """Save a downloaded document to disk and DB."""
        file_ext = Path(filename).suffix.lower() or ".pdf"
        stored_name = f"{uuid.uuid4().hex}{file_ext}"
        file_dir = settings.upload_path / correlation_id / candidate.id
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / stored_name
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_bytes)

        document = Document(
            candidate_id=candidate.id,
            upload_batch_id=upload_batch.id,
            original_filename=filename,
            stored_filename=stored_name,
            file_path=str(file_path),
            file_size_bytes=len(file_bytes),
            mime_type=mime_type,
            processing_status=ProcessingStatus.UPLOADED.value,
            correlation_id=correlation_id,
        )
        self.db.add(document)
        await self.db.flush()

        # Audit log
        await self.audit.log(
            correlation_id=correlation_id,
            action=AuditAction.UPLOAD.value,
            message=f"Batch-imported document: {filename} ({len(file_bytes)} bytes)",
            candidate_id=candidate.id,
            document_id=document.id,
            processing_stage="batch_upload",
        )

        return document.id
