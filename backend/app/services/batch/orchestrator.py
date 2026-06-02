import asyncio
import shutil
import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

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
    AuditAction,
)
from app.models.validation_result import ValidationResult
from app.services.integrations.gmail_scanner import GmailScanner, DiscoveredAttachment
from app.services.integrations.drive_service import GoogleDriveService, DiscoveredDriveFile
from app.services.processing.pipeline import ProcessingPipeline
from app.services.audit.logger import AuditService
from app.services.settings.file_naming_service import FileNamingRuleService
from app.models.classification import AIClassification
from app.models.required_document_rule import RequiredDocumentRule
from app.services.websocket.hub import ws_hub
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

            if not gmail_scanner:
                await self._log(batch.id, None, "warning", "orchestrator",
                                "No integrations configured. Enable Gmail in Settings.")
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

            # Clean up local files now that batch is concluded
            await self._cleanup_batch_local_files(batch)

            await self.db.commit()
            await self._emit_summary(batch)

        except Exception as e:
            logger.error("batch_processing_error", batch_id=batch_import_id, error=str(e))
            batch.status = BatchImportStatus.FAILED.value
            batch.error_message = str(e)[:1000]
            await self._log(batch.id, None, "error", "orchestrator", f"Batch failed: {e}")
            # Clean up local files even on failure
            await self._cleanup_batch_local_files(batch)
            await self.db.commit()
            await self._emit_summary(batch)

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
            await self._emit_candidate_status(batch.id, bc)

            # Get or create the Candidate record
            candidate = await self._ensure_candidate(bc, batch.correlation_id)
            bc.candidate_id = candidate.id
            await self.db.flush()

            # === DISCOVERY PHASE ===
            gmail_attachments: list[DiscoveredAttachment] = []
            drive_files: list[DiscoveredDriveFile] = []

            if gmail_scanner:
                try:
                    loop = asyncio.get_running_loop()
                    gmail_attachments = await loop.run_in_executor(
                        None, gmail_scanner.search_for_candidate,
                        bc.source_name, bc.source_email,
                    )
                    bc.gmail_emails_found = len(gmail_attachments)
                    await self._log(batch.id, bc.id, "info", "gmail",
                                    f"{prefix}: Found {len(gmail_attachments)} attachments in Gmail")
                except Exception as e:
                    await self._log(batch.id, bc.id, "warning", "gmail",
                                    f"{prefix}: Gmail scan failed: {e}")

            # Drive discovery (search) is disabled — Drive service is only used for uploads.
            # if drive_service:
            #     try:
            #         drive_files = drive_service.search_for_candidate(
            #             candidate_name=bc.source_name,
            #             candidate_id=bc.source_candidate_id,
            #         )
            #         bc.drive_files_found = len(drive_files)
            #         await self._log(batch.id, bc.id, "info", "drive",
            #                         f"{prefix}: Found {len(drive_files)} files in Google Drive")
            #     except Exception as e:
            #         await self._log(batch.id, bc.id, "warning", "drive",
            #                         f"{prefix}: Drive scan failed: {e}")

            total_docs = len(gmail_attachments) + len(drive_files)
            bc.documents_found = total_docs

            if total_docs == 0:
                bc.status = BatchCandidateStatus.NO_DOCUMENTS.value
                await self._log(batch.id, bc.id, "warning", "discovery",
                                f"{prefix}: No documents found. Skipping.")
                await self.db.flush()
                await self._emit_candidate_status(batch.id, bc)
                await self._emit_summary(batch)
                return

            bc.status = BatchCandidateStatus.DOCUMENTS_FOUND.value
            await self.db.flush()
            await self._emit_candidate_status(batch.id, bc)

            # === DOWNLOAD & INGEST PHASE ===
            bc.status = BatchCandidateStatus.DOWNLOADING.value
            await self._log(batch.id, bc.id, "info", "download",
                            f"{prefix}: Downloading {total_docs} documents")
            await self.db.flush()
            await self._emit_candidate_status(batch.id, bc)

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

            # Drive folder creation is deferred until first document passes ownership
            storage_folder_id = None

            document_ids = []

            # Download Gmail attachments
            for att in gmail_attachments:
                try:
                    loop = asyncio.get_running_loop()
                    file_bytes = await loop.run_in_executor(
                        None, gmail_scanner.download_attachment, att.message_id, att.attachment_id
                    )
                    doc_id = await self._save_document(
                        candidate, upload_batch, att.filename, att.mime_type, file_bytes,
                        batch.correlation_id,
                    )
                    document_ids.append(doc_id)
                except Exception as e:
                    bc.documents_failed += 1
                    await self._log(batch.id, bc.id, "error", "download",
                                    f"{prefix}: Failed to download Gmail attachment '{att.filename}': {e}")

            # Download Drive files
            for df in drive_files:
                try:
                    loop = asyncio.get_running_loop()
                    file_bytes = await loop.run_in_executor(
                        None, drive_service.download_file, df.file_id, df.mime_type
                    )
                    filename = df.filename
                    mime = df.mime_type
                    if mime in GoogleDriveService.EXPORTABLE_MIMES:
                        filename = Path(filename).stem + ".pdf"
                        mime = "application/pdf"
                    doc_id = await self._save_document(
                        candidate, upload_batch, filename, mime, file_bytes,
                        batch.correlation_id,
                    )
                    document_ids.append(doc_id)
                except Exception as e:
                    bc.documents_failed += 1
                    await self._log(batch.id, bc.id, "error", "download",
                                    f"{prefix}: Failed to download Drive file '{df.filename}': {e}")

            # === PROCESSING PHASE (with immediate upload after ownership validation) ===
            bc.status = BatchCandidateStatus.PROCESSING.value
            await self._log(batch.id, bc.id, "info", "pipeline",
                            f"{prefix}: Processing {len(document_ids)} documents through pipeline")
            await self.db.flush()
            await self._emit_candidate_status(batch.id, bc)

            # Load required document checklist for filtering
            required_rules = await self._get_required_document_rules()
            mandatory_doc_names = {
                self._normalize_doc_type(r.document_name)
                for r in required_rules if r.is_mandatory
            }

            pipeline = ProcessingPipeline(self.db)
            confirmed_doc_ids = []
            uploaded_doc_types = set()  # Track which required doc types have been uploaded

            for doc_id in document_ids:
                try:
                    await pipeline.process_document(doc_id)
                    bc.documents_processed += 1
                    await self.db.flush()

                    # Immediately check ownership validation result for this document
                    vr_result = await self.db.execute(
                        select(ValidationResult).where(
                            ValidationResult.document_id == doc_id,
                            ValidationResult.ownership_confirmed == True,
                        )
                    )
                    if vr_result.scalar_one_or_none():
                        confirmed_doc_ids.append(doc_id)

                        # Check if document type matches required checklist
                        doc_type = await self._get_document_type(doc_id)
                        normalized_type = self._normalize_doc_type(doc_type)

                        if not mandatory_doc_names or self._doc_type_matches_checklist(normalized_type, mandatory_doc_names):
                            # Upload to Drive: either matches required list, or no checklist configured
                            if drive_service:
                                drive_service, storage_folder_id = await self._upload_to_drive(
                                    drive_service, storage_folder_id, batch, bc, doc_id, prefix
                                )
                            uploaded_doc_types.add(normalized_type)
                        else:
                            await self._log(batch.id, bc.id, "info", "checklist",
                                            f"{prefix}: '{doc_type}' not in required document checklist - skipping upload")
                    else:
                        await self._log(batch.id, bc.id, "warning", "ownership",
                                        f"{prefix}: Document {doc_id} failed ownership verification - not uploaded")

                except Exception as e:
                    bc.documents_failed += 1
                    await self._log(batch.id, bc.id, "error", "pipeline",
                                    f"{prefix}: Pipeline failed for document {doc_id}: {e}")

            # === POST-PROCESSING STATUS UPDATE ===
            unconfirmed_count = bc.documents_processed - len(confirmed_doc_ids)

            if not confirmed_doc_ids:
                bc.documents_found = 0
                bc.documents_processed = 0
                bc.status = BatchCandidateStatus.NO_DOCUMENTS.value
                await self._log(batch.id, bc.id, "warning", "ownership",
                                f"{prefix}: Ownership not confirmed for any document. Marking as no documents found.")
                await self.db.flush()
                await self._emit_candidate_status(batch.id, bc)
                await self._emit_summary(batch)
            else:
                # Determine status based on required document checklist coverage
                matched_mandatory, missing_mandatory = self._get_matched_mandatory(uploaded_doc_types, mandatory_doc_names)

                bc.documents_found = len(mandatory_doc_names) if mandatory_doc_names else len(confirmed_doc_ids)
                bc.documents_processed = len(uploaded_doc_types) if mandatory_doc_names else len(confirmed_doc_ids)

                upload_batch.processed_files = len(uploaded_doc_types) if mandatory_doc_names else len(confirmed_doc_ids)
                upload_batch.failed_files = bc.documents_failed + unconfirmed_count
                upload_batch.processing_status = ProcessingStatus.COMPLETED.value

                if not mandatory_doc_names:
                    # No checklist configured — all ownership-confirmed docs uploaded
                    bc.status = BatchCandidateStatus.COMPLETED.value
                    await self._log(batch.id, bc.id, "info", "complete",
                                    f"{prefix}: Completed. {len(confirmed_doc_ids)} verified & uploaded, "
                                    f"{unconfirmed_count} rejected (ownership), {bc.documents_failed} failed")
                elif missing_mandatory and not matched_mandatory:
                    # No required documents matched at all
                    bc.status = BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value
                    missing_names = [r.document_name for r in required_rules
                                     if r.is_mandatory and self._normalize_doc_type(r.document_name) in missing_mandatory]
                    await self._log(batch.id, bc.id, "warning", "checklist",
                                    f"{prefix}: No required documents found. Missing: {', '.join(missing_names)}")
                elif missing_mandatory:
                    # Some required documents found but not all
                    bc.status = BatchCandidateStatus.PARTIAL.value
                    missing_names = [r.document_name for r in required_rules
                                     if r.is_mandatory and self._normalize_doc_type(r.document_name) in missing_mandatory]
                    await self._log(batch.id, bc.id, "warning", "checklist",
                                    f"{prefix}: Partial. {len(matched_mandatory)}/{len(mandatory_doc_names)} mandatory docs. "
                                    f"Missing: {', '.join(missing_names)}")
                else:
                    # All mandatory documents satisfied
                    bc.status = BatchCandidateStatus.COMPLETED.value
                    await self._log(batch.id, bc.id, "info", "complete",
                                    f"{prefix}: Completed. All {len(mandatory_doc_names)} mandatory documents verified & uploaded.")

                await self.db.flush()
                await self._emit_candidate_status(batch.id, bc)
                await self._emit_summary(batch)

        except Exception as e:
            bc.status = BatchCandidateStatus.FAILED.value
            bc.error_message = str(e)[:1000]
            await self._log(batch.id, bc.id, "error", "candidate",
                            f"{prefix}: Failed: {e}")
            await self.db.flush()
            await self._emit_candidate_status(batch.id, bc)
            await self._emit_summary(batch)

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
        """Write a batch log entry and emit via WebSocket."""
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

        # Emit real-time WebSocket event
        await ws_hub.emit_processing_log(
            batch_id=batch_import_id,
            log_id=log_entry.id,
            batch_candidate_id=batch_candidate_id,
            level=level,
            stage=stage,
            message=message,
            details=details,
        )

    async def _emit_candidate_status(self, batch_id: str, bc: BatchImportCandidate) -> None:
        """Emit candidate status change via WebSocket."""
        await ws_hub.emit_candidate_status(
            batch_id=batch_id,
            candidate_id=bc.id,
            status=bc.status,
            documents_found=bc.documents_found or 0,
            documents_processed=bc.documents_processed or 0,
            documents_failed=bc.documents_failed or 0,
            error_message=bc.error_message,
        )

    async def _emit_summary(self, batch: BatchImport) -> None:
        """Emit processing summary counts via WebSocket."""
        candidates = await self._get_batch_candidates(batch.id)
        in_progress = sum(
            1 for c in candidates
            if c.status in (
                BatchCandidateStatus.PROCESSING.value,
                BatchCandidateStatus.DISCOVERING.value,
                BatchCandidateStatus.DOWNLOADING.value,
                BatchCandidateStatus.DOCUMENTS_FOUND.value,
            )
        )
        completed = sum(1 for c in candidates if c.status == BatchCandidateStatus.COMPLETED.value)
        failed = sum(1 for c in candidates if c.status == BatchCandidateStatus.FAILED.value)
        partial = sum(
            1 for c in candidates
            if c.status in (
                BatchCandidateStatus.PARTIAL.value,
                BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value,
            )
        )
        pending = sum(1 for c in candidates if c.status == BatchCandidateStatus.PENDING.value)
        no_documents = sum(1 for c in candidates if c.status == BatchCandidateStatus.NO_DOCUMENTS.value)

        await ws_hub.emit_processing_summary(
            batch_id=batch.id,
            total=batch.total_candidates or len(candidates),
            completed=completed,
            failed=failed,
            in_progress=in_progress,
            partial=partial,
            pending=pending,
            no_documents=no_documents,
            batch_status=batch.status,
        )

    async def _upload_to_drive(
        self,
        drive_service: GoogleDriveService,
        storage_folder_id: Optional[str],
        batch: BatchImport,
        bc: BatchImportCandidate,
        doc_id: str,
        prefix: str,
    ) -> tuple[GoogleDriveService, Optional[str]]:
        """Upload a confirmed document to Drive with lazy folder creation and retry on connection error.
        Returns the (possibly refreshed) drive_service and storage_folder_id.
        """
        # Load configurable file naming rule
        naming_rule = await FileNamingRuleService.get_active_rule(self.db)

        for attempt in range(2):
            try:
                if not storage_folder_id:
                    folder_name = FileNamingRuleService.resolve_folder_name(
                        naming_rule.folder_structure_pattern,
                        bc.source_candidate_id,
                        bc.source_name,
                        batch.created_at,
                    )
                    storage_folder_id = drive_service.create_storage_folder_with_name(
                        folder_name
                    )
                    await self._log(batch.id, bc.id, "info", "drive_storage",
                                    f"{prefix}: Created Drive folder '{folder_name}' for verified documents")

                doc_result = await self.db.execute(
                    select(Document).where(Document.id == doc_id)
                )
                doc = doc_result.scalar_one()

                # Resolve file name from the configured pattern
                doc_type = await self._get_document_type(doc_id)
                resolved_filename = FileNamingRuleService.resolve_file_name(
                    naming_rule.file_rename_pattern,
                    bc.source_candidate_id,
                    bc.source_name,
                    doc_type,
                    doc.original_filename,
                )

                file_bytes = Path(doc.file_path).read_bytes()
                drive_service.upload_file(
                    storage_folder_id, resolved_filename, file_bytes, doc.mime_type
                )
                await self._log(batch.id, bc.id, "info", "drive_upload",
                                f"{prefix}: Uploaded '{resolved_filename}' to Drive (ownership confirmed)")
                return drive_service, storage_folder_id

            except (OSError, ConnectionError) as e:
                if attempt == 0:
                    logger.warning("drive_connection_stale", doc_id=doc_id, error=str(e))
                    drive_service = await self._get_drive_service() or drive_service
                else:
                    logger.warning("drive_upload_failed", doc_id=doc_id, error=str(e))
                    await self._log(batch.id, bc.id, "warning", "drive_upload",
                                    f"{prefix}: Drive upload failed for document {doc_id}: {e}")

            except Exception as e:
                logger.warning("drive_upload_failed", doc_id=doc_id, error=str(e))
                await self._log(batch.id, bc.id, "warning", "drive_upload",
                                f"{prefix}: Drive upload failed for document {doc_id}: {e}")
                break

        return drive_service, storage_folder_id

    async def _get_document_type(self, doc_id: str) -> str:
        """Get the AI-classified document type for a document."""
        result = await self.db.execute(
            select(AIClassification.document_type)
            .where(
                AIClassification.document_id == doc_id,
                AIClassification.page_id.is_(None),  # Full-document classification
            )
            .order_by(AIClassification.confidence_score.desc())
        )
        doc_type = result.scalar_one_or_none()
        return doc_type or "Document"

    async def _get_required_document_rules(self) -> list[RequiredDocumentRule]:
        """Load all active required document rules from the checklist."""
        result = await self.db.execute(
            select(RequiredDocumentRule).where(RequiredDocumentRule.is_active.is_(True))
        )
        return list(result.scalars().all())

    @staticmethod
    def _normalize_doc_type(doc_type: str) -> str:
        """Normalize a document type string for comparison.
        Strips spaces, underscores, hyphens and lowercases for matching
        AI classification output (e.g. 'pan_card') against checklist names (e.g. 'PAN Card').
        """
        import re
        return re.sub(r'[\s_\-]+', '', doc_type.lower().strip())

    @staticmethod
    def _doc_type_matches_checklist(normalized_type: str, mandatory_doc_names: set[str]) -> bool:
        """Check if a normalized doc type matches any entry in the mandatory checklist.
        Uses substring matching: 'aadhaar' matches 'aadhaarcard' and vice versa.
        """
        for rule_name in mandatory_doc_names:
            if normalized_type in rule_name or rule_name in normalized_type:
                return True
        return False

    @staticmethod
    def _get_matched_mandatory(uploaded_doc_types: set[str], mandatory_doc_names: set[str]) -> tuple[set[str], set[str]]:
        """Return (matched, missing) mandatory doc names based on substring matching."""
        matched = set()
        for rule_name in mandatory_doc_names:
            for uploaded in uploaded_doc_types:
                if uploaded in rule_name or rule_name in uploaded:
                    matched.add(rule_name)
                    break
        missing = mandatory_doc_names - matched
        return matched, missing

    async def _cleanup_batch_local_files(self, batch: BatchImport) -> None:
        """Remove local files for a concluded batch. Called after batch completes/fails."""
        batch_dir = settings.upload_path / batch.correlation_id
        if batch_dir.exists():
            try:
                shutil.rmtree(batch_dir)
                logger.info("batch_local_cleanup", batch_id=batch.id, path=str(batch_dir))
                await self._log(batch.id, None, "info", "cleanup",
                                f"Local files cleaned up: {batch_dir}")
            except Exception as e:
                logger.warning("batch_local_cleanup_failed", batch_id=batch.id, error=str(e))
                await self._log(batch.id, None, "warning", "cleanup",
                                f"Failed to clean up local files: {e}")
