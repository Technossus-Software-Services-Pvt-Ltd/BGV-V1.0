import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.batch_import import BatchImport
from app.models.batch_import_candidate import BatchImportCandidate
from app.models.batch_log import BatchLog
from app.models.candidate import Candidate
from app.models.upload_batch import UploadBatch
from app.models.document import Document
from app.models.integration_config import IntegrationConfig
from app.models.enums import (
    BatchImportStatus,
    BatchCandidateStatus,
    IntegrationProvider,
    ProcessingStatus,
    LogLevel,
    AuditAction,
)
from app.services.integrations.gmail_scanner import GmailScanner, DiscoveredAttachment
from app.services.integrations.drive_service import GoogleDriveService, DiscoveredDriveFile
from app.services.processing.pipeline import ProcessingPipeline
from app.services.audit.logger import AuditService
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("batch.orchestrator")


class BatchOrchestrator:
    """Orchestrates the full batch processing workflow:
    Parse → Discover (Gmail + Drive) → Download → Feed to Pipeline → Store
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def process_batch(self, batch_import_id: str) -> None:
        """Main entry point: process all candidates in a batch import."""
        batch = await self._get_batch(batch_import_id)
        if not batch:
            logger.error("batch_not_found", batch_import_id=batch_import_id)
            return

        correlation_id = batch.correlation_id

        try:
            batch.status = BatchImportStatus.PROCESSING.value
            await self.db.flush()
            await self._log(batch.id, None, "info", "orchestrator", f"Starting batch processing: {batch.batch_code}")

            # Load integration configs
            gmail_scanner = await self._get_gmail_scanner()
            drive_service = await self._get_drive_service()

            if not gmail_scanner and not drive_service:
                await self._log(batch.id, None, "warning", "orchestrator",
                                "No integrations configured. Enable Gmail or Google Drive in Settings.")
                batch.status = BatchImportStatus.FAILED.value
                batch.error_message = "No integrations configured"
                await self.db.commit()
                return

            # Process each candidate
            candidates = await self._get_batch_candidates(batch_import_id)
            total = len(candidates)
            await self._log(batch.id, None, "info", "orchestrator", f"Processing {total} candidates")

            for idx, bc in enumerate(candidates, start=1):
                await self._process_candidate(batch, bc, gmail_scanner, drive_service, idx, total)
                await self.db.commit()

            # Final status
            await self._update_batch_totals(batch)
            if batch.failed_candidates > 0:
                batch.status = BatchImportStatus.COMPLETED_WITH_ERRORS.value
            else:
                batch.status = BatchImportStatus.COMPLETED.value

            await self._log(batch.id, None, "info", "orchestrator",
                            f"Batch complete: {batch.processed_candidates} processed, "
                            f"{batch.failed_candidates} failed, {batch.skipped_candidates} skipped")
            await self.db.commit()

        except Exception as e:
            logger.error("batch_processing_error", batch_id=batch_import_id, error=str(e))
            batch.status = BatchImportStatus.FAILED.value
            batch.error_message = str(e)[:1000]
            await self._log(batch.id, None, "error", "orchestrator", f"Batch failed: {e}")
            await self.db.commit()

    async def retry_candidate(self, batch_import_id: str, batch_candidate_id: str) -> None:
        """Retry processing a single failed candidate."""
        batch = await self._get_batch(batch_import_id)
        if not batch:
            return

        result = await self.db.execute(
            select(BatchImportCandidate).where(
                BatchImportCandidate.id == batch_candidate_id,
                BatchImportCandidate.batch_import_id == batch_import_id,
            )
        )
        bc = result.scalar_one_or_none()
        if not bc:
            return

        gmail_scanner = await self._get_gmail_scanner()
        drive_service = await self._get_drive_service()

        bc.status = BatchCandidateStatus.PENDING.value
        bc.error_message = None
        bc.documents_found = 0
        bc.documents_processed = 0
        bc.documents_failed = 0
        await self.db.flush()

        await self._process_candidate(batch, bc, gmail_scanner, drive_service, 0, 0)
        await self._update_batch_totals(batch)
        await self.db.commit()

    async def _process_candidate(
        self,
        batch: BatchImport,
        bc: BatchImportCandidate,
        gmail_scanner: Optional[GmailScanner],
        drive_service: Optional[GoogleDriveService],
        current: int,
        total: int,
    ) -> None:
        """Process a single candidate: discover docs, download, run pipeline."""
        prefix = f"[{current}/{total}] {bc.source_name}" if total > 0 else bc.source_name
        try:
            await self._log(batch.id, bc.id, "info", "discovery", f"{prefix}: Starting document discovery")
            bc.status = BatchCandidateStatus.DISCOVERING.value
            await self.db.flush()

            # Get or create the Candidate record
            candidate = await self._ensure_candidate(bc, batch.correlation_id)
            bc.candidate_id = candidate.id
            await self.db.flush()

            # === DISCOVERY PHASE ===
            gmail_attachments: list[DiscoveredAttachment] = []
            drive_files: list[DiscoveredDriveFile] = []

            if gmail_scanner:
                try:
                    gmail_attachments = gmail_scanner.search_for_candidate(
                        candidate_name=bc.source_name,
                        candidate_email=bc.source_email,
                    )
                    bc.gmail_emails_found = len(gmail_attachments)
                    await self._log(batch.id, bc.id, "info", "gmail",
                                    f"{prefix}: Found {len(gmail_attachments)} attachments in Gmail")
                except Exception as e:
                    await self._log(batch.id, bc.id, "warning", "gmail",
                                    f"{prefix}: Gmail scan failed: {e}")

            if drive_service:
                try:
                    drive_files = drive_service.search_for_candidate(
                        candidate_name=bc.source_name,
                        candidate_id=bc.source_candidate_id,
                    )
                    bc.drive_files_found = len(drive_files)
                    await self._log(batch.id, bc.id, "info", "drive",
                                    f"{prefix}: Found {len(drive_files)} files in Google Drive")
                except Exception as e:
                    await self._log(batch.id, bc.id, "warning", "drive",
                                    f"{prefix}: Drive scan failed: {e}")

            total_docs = len(gmail_attachments) + len(drive_files)
            bc.documents_found = total_docs

            if total_docs == 0:
                bc.status = BatchCandidateStatus.NO_DOCUMENTS.value
                await self._log(batch.id, bc.id, "warning", "discovery",
                                f"{prefix}: No documents found. Skipping.")
                await self.db.flush()
                return

            bc.status = BatchCandidateStatus.DOCUMENTS_FOUND.value
            await self.db.flush()

            # === DOWNLOAD & INGEST PHASE ===
            bc.status = BatchCandidateStatus.DOWNLOADING.value
            await self._log(batch.id, bc.id, "info", "download",
                            f"{prefix}: Downloading {total_docs} documents")
            await self.db.flush()

            # Create an upload batch for this candidate
            upload_batch = UploadBatch(
                candidate_id=candidate.id,
                batch_reference=f"BATCH-{batch.batch_code}-{bc.source_candidate_id}",
                total_files=total_docs,
                processing_status=ProcessingStatus.UPLOADED.value,
                correlation_id=batch.correlation_id,
            )
            self.db.add(upload_batch)
            await self.db.flush()

            # Create Drive storage folder (if Drive is available)
            storage_folder_id = None
            if drive_service:
                try:
                    storage_folder_id = drive_service.create_storage_folder(
                        batch.batch_code, bc.source_name
                    )
                except Exception as e:
                    await self._log(batch.id, bc.id, "warning", "drive_storage",
                                    f"{prefix}: Could not create Drive folder: {e}")

            document_ids = []

            # Download Gmail attachments
            for att in gmail_attachments:
                try:
                    file_bytes = gmail_scanner.download_attachment(att.message_id, att.attachment_id)
                    doc_id = await self._save_document(
                        candidate, upload_batch, att.filename, att.mime_type, file_bytes,
                        batch.correlation_id, drive_service, storage_folder_id,
                    )
                    document_ids.append(doc_id)
                except Exception as e:
                    bc.documents_failed += 1
                    await self._log(batch.id, bc.id, "error", "download",
                                    f"{prefix}: Failed to download Gmail attachment '{att.filename}': {e}")

            # Download Drive files
            for df in drive_files:
                try:
                    file_bytes = drive_service.download_file(df.file_id, df.mime_type)
                    filename = df.filename
                    mime = df.mime_type
                    if mime in GoogleDriveService.EXPORTABLE_MIMES:
                        filename = Path(filename).stem + ".pdf"
                        mime = "application/pdf"
                    doc_id = await self._save_document(
                        candidate, upload_batch, filename, mime, file_bytes,
                        batch.correlation_id, drive_service, storage_folder_id,
                    )
                    document_ids.append(doc_id)
                except Exception as e:
                    bc.documents_failed += 1
                    await self._log(batch.id, bc.id, "error", "download",
                                    f"{prefix}: Failed to download Drive file '{df.filename}': {e}")

            # === PROCESSING PHASE ===
            bc.status = BatchCandidateStatus.PROCESSING.value
            await self._log(batch.id, bc.id, "info", "pipeline",
                            f"{prefix}: Processing {len(document_ids)} documents through pipeline")
            await self.db.flush()

            pipeline = ProcessingPipeline(self.db)
            for doc_id in document_ids:
                try:
                    await pipeline.process_document(doc_id)
                    bc.documents_processed += 1
                    await self.db.flush()
                except Exception as e:
                    bc.documents_failed += 1
                    await self._log(batch.id, bc.id, "error", "pipeline",
                                    f"{prefix}: Pipeline failed for document {doc_id}: {e}")

            # Update upload batch counts
            upload_batch.processed_files = bc.documents_processed
            upload_batch.failed_files = bc.documents_failed
            upload_batch.processing_status = ProcessingStatus.COMPLETED.value

            bc.status = BatchCandidateStatus.COMPLETED.value
            await self._log(batch.id, bc.id, "info", "complete",
                            f"{prefix}: Completed. {bc.documents_processed} processed, {bc.documents_failed} failed")
            await self.db.flush()

        except Exception as e:
            bc.status = BatchCandidateStatus.FAILED.value
            bc.error_message = str(e)[:1000]
            await self._log(batch.id, bc.id, "error", "candidate",
                            f"{prefix}: Failed: {e}")
            await self.db.flush()

    async def _save_document(
        self,
        candidate: Candidate,
        upload_batch: UploadBatch,
        filename: str,
        mime_type: str,
        file_bytes: bytes,
        correlation_id: str,
        drive_service: Optional[GoogleDriveService],
        storage_folder_id: Optional[str],
    ) -> str:
        """Save a downloaded document to disk and DB. Optionally upload to Drive storage."""
        file_ext = Path(filename).suffix.lower() or ".pdf"
        stored_name = f"{uuid.uuid4().hex}{file_ext}"
        file_dir = settings.upload_path / correlation_id / candidate.id
        file_dir.mkdir(parents=True, exist_ok=True)
        file_path = file_dir / stored_name
        file_path.write_bytes(file_bytes)

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

        # Upload to Drive storage folder
        if drive_service and storage_folder_id:
            try:
                drive_service.upload_file(storage_folder_id, filename, file_bytes, mime_type)
            except Exception as e:
                logger.warning("drive_upload_failed", filename=filename, error=str(e))

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

    async def _ensure_candidate(self, bc: BatchImportCandidate, correlation_id: str) -> Candidate:
        """Get or create a Candidate record from batch candidate data."""
        # Match by candidate_id AND name to avoid merging different candidates
        # that happen to share the same candidate_id in different batches.
        result = await self.db.execute(
            select(Candidate).where(
                Candidate.candidate_id == bc.source_candidate_id,
                Candidate.name == bc.source_name,
            )
        )
        candidate = result.scalar_one_or_none()

        if not candidate:
            candidate = Candidate(
                candidate_id=bc.source_candidate_id,
                name=bc.source_name,
                email=bc.source_email,
                phone=bc.source_phone,
                dob=bc.source_dob,
                gender=bc.source_gender,
                correlation_id=correlation_id,
            )
            self.db.add(candidate)
            await self.db.flush()
        else:
            # Update missing fields
            if bc.source_email and not candidate.email:
                candidate.email = bc.source_email
            if bc.source_phone and not candidate.phone:
                candidate.phone = bc.source_phone
            if bc.source_dob and not candidate.dob:
                candidate.dob = bc.source_dob
            if bc.source_gender and not candidate.gender:
                candidate.gender = bc.source_gender
            await self.db.flush()

        return candidate

    async def _get_batch(self, batch_import_id: str) -> Optional[BatchImport]:
        result = await self.db.execute(
            select(BatchImport).where(BatchImport.id == batch_import_id)
        )
        return result.scalar_one_or_none()

    async def _get_batch_candidates(self, batch_import_id: str) -> list[BatchImportCandidate]:
        result = await self.db.execute(
            select(BatchImportCandidate)
            .where(BatchImportCandidate.batch_import_id == batch_import_id)
            .order_by(BatchImportCandidate.row_number)
        )
        return list(result.scalars().all())

    async def _get_gmail_scanner(self) -> Optional[GmailScanner]:
        result = await self.db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.provider == IntegrationProvider.GMAIL.value,
                IntegrationConfig.is_enabled == True,
            )
        )
        config = result.scalar_one_or_none()
        if config and config.credentials_json:
            try:
                return GmailScanner(config.credentials_json)
            except Exception as e:
                logger.error("gmail_init_failed", error=str(e))
        return None

    async def _get_drive_service(self) -> Optional[GoogleDriveService]:
        result = await self.db.execute(
            select(IntegrationConfig).where(
                IntegrationConfig.provider == IntegrationProvider.GOOGLE_DRIVE.value,
                IntegrationConfig.is_enabled == True,
            )
        )
        config = result.scalar_one_or_none()
        if config and config.credentials_json:
            try:
                return GoogleDriveService(config.credentials_json, config.config_json)
            except Exception as e:
                logger.error("drive_init_failed", error=str(e))
        return None

    async def _update_batch_totals(self, batch: BatchImport) -> None:
        """Recompute batch-level totals from candidate statuses."""
        candidates = await self._get_batch_candidates(batch.id)
        batch.processed_candidates = sum(1 for c in candidates if c.status == BatchCandidateStatus.COMPLETED.value)
        batch.failed_candidates = sum(1 for c in candidates if c.status == BatchCandidateStatus.FAILED.value)
        batch.skipped_candidates = sum(
            1 for c in candidates
            if c.status in (BatchCandidateStatus.NO_DOCUMENTS.value, BatchCandidateStatus.SKIPPED.value)
        )
        batch.total_documents_found = sum(c.documents_found for c in candidates)
        batch.total_documents_processed = sum(c.documents_processed for c in candidates)
        await self.db.flush()

    async def _log(
        self,
        batch_import_id: str,
        batch_candidate_id: Optional[str],
        level: str,
        stage: str,
        message: str,
        details: Optional[str] = None,
    ) -> None:
        """Write a batch log entry (used for SSE streaming)."""
        log_entry = BatchLog(
            batch_import_id=batch_import_id,
            batch_candidate_id=batch_candidate_id,
            level=level,
            stage=stage,
            message=message,
            details=details,
        )
        self.db.add(log_entry)
        await self.db.flush()
        logger.info("batch_log", batch_id=batch_import_id, level=level, stage=stage, message=message)
