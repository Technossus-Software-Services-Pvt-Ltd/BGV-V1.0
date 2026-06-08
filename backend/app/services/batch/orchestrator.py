import shutil
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.protocols import WebSocketHubProtocol

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.batch_import import BatchImport
from app.models.batch_import_candidate import BatchImportCandidate
from app.models.candidate import Candidate
from app.models.document import Document
from app.models.upload_batch import UploadBatch
from app.models.enums import (
    BatchImportStatus,
    BatchCandidateStatus,
    ProcessingStatus,
)
from app.models.validation_result import ValidationResult
from app.models.required_document_rule import RequiredDocumentRule
from app.services.processing.pipeline import ProcessingPipeline
from app.services.audit.logger import AuditService
from app.services.batch.discovery_service import DiscoveryService
from app.services.batch.ingest_service import DocumentIngestService
from app.services.batch.drive_upload_service import DriveUploadService
from app.services.batch.status_service import BatchStatusService
from app.services.batch.checklist_matcher import ChecklistMatcher
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("batch.orchestrator")


class BatchOrchestrator:
    """Orchestrates the full batch processing workflow:
    Parse → Discover (Gmail + Drive) → Download → Feed to Pipeline → Store

    This class is now a thin coordinator that delegates to focused services:
    - DiscoveryService: Gmail/Drive integration + document search
    - DocumentIngestService: File download + save to disk
    - DriveUploadService: Upload confirmed docs to Drive
    - BatchStatusService: Logging + WebSocket emissions + progress tracking
    - ChecklistMatcher: Document type matching logic
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        ws_hub: Optional["WebSocketHubProtocol"] = None,
        pipeline_factory=None,
    ):
        self.db = db
        self.audit = AuditService(db)
        # Accept a pipeline factory or use the default
        self._pipeline_factory = pipeline_factory

        # Initialize sub-services
        self._discovery = DiscoveryService(db)
        self._ingest = DocumentIngestService(db, self.audit)
        self._drive_upload = DriveUploadService(db)
        self._status = BatchStatusService(db, ws_hub=ws_hub)

    async def process_batch(self, batch_import_id: str) -> None:
        """Main entry point: process all candidates in a batch import."""
        batch = await self._get_batch(batch_import_id)
        if not batch:
            logger.error("batch_not_found", batch_import_id=batch_import_id)
            return

        try:
            batch.status = BatchImportStatus.PROCESSING.value
            await self.db.flush()
            await self._status.log(batch.id, None, "info", "orchestrator", f"Starting batch processing: {batch.batch_code}")

            # Load integration configs
            gmail_scanner = await self._discovery.get_gmail_scanner()
            drive_service = await self._discovery.get_drive_service()

            if not gmail_scanner:
                await self._status.log(batch.id, None, "warning", "orchestrator",
                                       "No integrations configured. Enable Gmail in Settings.")
                batch.status = BatchImportStatus.FAILED.value
                batch.error_message = "No integrations configured"
                await self.db.commit()
                return

            # Process each candidate
            candidates = await self._get_batch_candidates(batch_import_id)
            total = len(candidates)
            await self._status.log(batch.id, None, "info", "orchestrator", f"Processing {total} candidates")

            for idx, bc in enumerate(candidates, start=1):
                await self._process_candidate(batch, bc, gmail_scanner, drive_service, idx, total)
                # Update batch counters atomically with each candidate commit
                # so persisted state is always consistent if process crashes mid-batch
                await self._status.update_batch_totals(batch)
                await self.db.commit()

            # Final status
            await self._status.update_batch_totals(batch)
            if batch.failed_candidates > 0:
                batch.status = BatchImportStatus.COMPLETED_WITH_ERRORS.value
            else:
                batch.status = BatchImportStatus.COMPLETED.value

            await self._status.log(batch.id, None, "info", "orchestrator",
                                   f"Batch complete: {batch.processed_candidates} processed, "
                                   f"{batch.failed_candidates} failed, {batch.skipped_candidates} skipped")

            # Clean up local files now that batch is concluded
            await self._cleanup_batch_local_files(batch)

            await self.db.commit()
            await self._status.emit_summary(batch)

        except Exception as e:
            logger.error("batch_processing_error", batch_id=batch_import_id, error=str(e))
            batch.status = BatchImportStatus.FAILED.value
            batch.error_message = str(e)[:1000]
            await self._status.log(batch.id, None, "error", "orchestrator", f"Batch failed: {e}")
            # Clean up local files even on failure
            await self._cleanup_batch_local_files(batch)
            await self.db.commit()
            await self._status.emit_summary(batch)

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

        gmail_scanner = await self._discovery.get_gmail_scanner()
        drive_service = await self._discovery.get_drive_service()

        bc.status = BatchCandidateStatus.PENDING.value
        bc.error_message = None
        bc.documents_found = 0
        bc.documents_processed = 0
        bc.documents_failed = 0
        await self.db.flush()

        await self._process_candidate(batch, bc, gmail_scanner, drive_service, 0, 0)
        await self._status.update_batch_totals(batch)
        await self.db.commit()

    async def _process_candidate(
        self,
        batch: BatchImport,
        bc: BatchImportCandidate,
        gmail_scanner,
        drive_service,
        current: int,
        total: int,
    ) -> None:
        """Process a single candidate: discover docs, download, run pipeline."""
        prefix = f"[{current}/{total}] {bc.source_name}" if total > 0 else bc.source_name
        try:
            await self._status.log(batch.id, bc.id, "info", "discovery", f"{prefix}: Starting document discovery")
            bc.status = BatchCandidateStatus.DISCOVERING.value
            await self.db.flush()
            await self._status.emit_candidate_status(batch.id, bc)

            # Get or create the Candidate record
            candidate = await self._ensure_candidate(bc, batch.correlation_id)
            bc.candidate_id = candidate.id
            await self.db.flush()

            # === DISCOVERY ===
            try:
                gmail_attachments, drive_files = await self._discovery.discover_documents(
                    bc.source_name, bc.source_email, gmail_scanner, drive_service,
                )
                bc.gmail_emails_found = len(gmail_attachments)
                await self._status.log(batch.id, bc.id, "info", "gmail",
                                       f"{prefix}: Found {len(gmail_attachments)} attachments in Gmail")
            except Exception as e:
                gmail_attachments, drive_files = [], []
                await self._status.log(batch.id, bc.id, "warning", "gmail",
                                       f"{prefix}: Gmail scan failed: {e}")

            total_docs = len(gmail_attachments) + len(drive_files)
            bc.documents_found = total_docs

            if total_docs == 0:
                bc.status = BatchCandidateStatus.NO_DOCUMENTS.value
                await self._status.log(batch.id, bc.id, "warning", "discovery",
                                       f"{prefix}: No documents found. Skipping.")
                await self.db.flush()
                await self._status.emit_candidate_status(batch.id, bc)
                await self._status.emit_summary(batch)
                return

            bc.status = BatchCandidateStatus.DOCUMENTS_FOUND.value
            await self.db.flush()
            await self._status.emit_candidate_status(batch.id, bc)

            # === DOWNLOAD & INGEST ===
            bc.status = BatchCandidateStatus.DOWNLOADING.value
            await self._status.log(batch.id, bc.id, "info", "download",
                                   f"{prefix}: Downloading {total_docs} documents")
            await self.db.flush()
            await self._status.emit_candidate_status(batch.id, bc)

            upload_batch = UploadBatch(
                candidate_id=candidate.id,
                batch_reference=f"BATCH-{batch.batch_code}-{bc.source_candidate_id}",
                total_files=total_docs,
                processing_status=ProcessingStatus.UPLOADED.value,
                correlation_id=batch.correlation_id,
            )
            self.db.add(upload_batch)
            await self.db.flush()

            document_ids = []
            for att in gmail_attachments:
                try:
                    from app.services.batch.ingest_service import _io_executor
                    import asyncio
                    loop = asyncio.get_running_loop()
                    file_bytes = await loop.run_in_executor(
                        _io_executor, gmail_scanner.download_attachment, att.message_id, att.attachment_id
                    )
                    doc_id = await self._ingest._save_document(
                        candidate, upload_batch, att.filename, att.mime_type, file_bytes,
                        batch.correlation_id,
                    )
                    document_ids.append(doc_id)
                except Exception as e:
                    bc.documents_failed += 1
                    await self._status.log(batch.id, bc.id, "error", "download",
                                           f"{prefix}: Failed to download Gmail attachment '{att.filename}': {e}")

            for df in drive_files:
                try:
                    from app.services.batch.ingest_service import _io_executor
                    from pathlib import Path
                    import asyncio
                    from app.services.integrations.drive_service import GoogleDriveService
                    loop = asyncio.get_running_loop()
                    file_bytes = await loop.run_in_executor(
                        _io_executor, drive_service.download_file, df.file_id, df.mime_type
                    )
                    filename = df.filename
                    mime = df.mime_type
                    if mime in GoogleDriveService.EXPORTABLE_MIMES:
                        filename = Path(filename).stem + ".pdf"
                        mime = "application/pdf"
                    doc_id = await self._ingest._save_document(
                        candidate, upload_batch, filename, mime, file_bytes,
                        batch.correlation_id,
                    )
                    document_ids.append(doc_id)
                except Exception as e:
                    bc.documents_failed += 1
                    await self._status.log(batch.id, bc.id, "error", "download",
                                           f"{prefix}: Failed to download Drive file '{df.filename}': {e}")

            # === PIPELINE PROCESSING ===
            bc.status = BatchCandidateStatus.PROCESSING.value
            await self._status.log(batch.id, bc.id, "info", "pipeline",
                                   f"{prefix}: Processing {len(document_ids)} documents through pipeline")
            await self.db.flush()
            await self._status.emit_candidate_status(batch.id, bc)

            required_rules = await self._get_required_document_rules()
            mandatory_doc_names = {
                ChecklistMatcher.normalize_doc_type(r.document_name)
                for r in required_rules if r.is_mandatory
            }

            if self._pipeline_factory:
                pipeline = self._pipeline_factory(self.db)
            else:
                from app.services.dependencies import get_processing_pipeline
                pipeline = get_processing_pipeline(self.db)
            confirmed_doc_ids = []
            uploaded_doc_types = set()
            storage_folder_id = None

            for doc_id in document_ids:
                try:
                    await pipeline.process_document(doc_id)
                    bc.documents_processed += 1
                    await self.db.flush()

                    # Check if document was split into children
                    child_result = await self.db.execute(
                        select(Document).where(Document.parent_document_id == doc_id)
                    )
                    child_docs = child_result.scalars().all()

                    # Determine which doc IDs to check for validation/upload
                    docs_to_check = [c.id for c in child_docs] if child_docs else [doc_id]

                    for check_id in docs_to_check:
                        vr_result = await self.db.execute(
                            select(ValidationResult).where(
                                ValidationResult.document_id == check_id,
                                ValidationResult.ownership_confirmed == True,
                            )
                        )
                        if vr_result.scalar_one_or_none():
                            confirmed_doc_ids.append(check_id)

                            doc_type = await self._drive_upload._get_document_type(check_id)
                            normalized_type = ChecklistMatcher.normalize_doc_type(doc_type)

                            if not mandatory_doc_names or ChecklistMatcher.doc_type_matches_checklist(normalized_type, mandatory_doc_names):
                                if drive_service:
                                    drive_service, storage_folder_id = await self._drive_upload.upload_document(
                                        drive_service, storage_folder_id, batch, bc, check_id
                                    )
                                    await self._status.log(batch.id, bc.id, "info", "drive_upload",
                                                          f"{prefix}: Uploaded '{doc_type}' to Drive (ownership confirmed)")
                                uploaded_doc_types.add(normalized_type)
                            else:
                                await self._status.log(batch.id, bc.id, "info", "checklist",
                                                       f"{prefix}: '{doc_type}' not in required document checklist - skipping upload")
                        else:
                            await self._status.log(batch.id, bc.id, "warning", "ownership",
                                                   f"{prefix}: Document {check_id} failed ownership verification - not uploaded")

                except Exception as e:
                    bc.documents_failed += 1
                    await self._status.log(batch.id, bc.id, "error", "pipeline",
                                           f"{prefix}: Pipeline failed for document {doc_id}: {e}")

            # === POST-PROCESSING STATUS ===
            await self._finalize_candidate_status(
                batch, bc, upload_batch, confirmed_doc_ids, uploaded_doc_types,
                required_rules, mandatory_doc_names, prefix,
            )

        except Exception as e:
            bc.status = BatchCandidateStatus.FAILED.value
            bc.error_message = str(e)[:1000]
            await self._status.log(batch.id, bc.id, "error", "candidate",
                                   f"{prefix}: Failed: {e}")
            await self.db.flush()
            await self._status.emit_candidate_status(batch.id, bc)
            await self._status.emit_summary(batch)

    async def _finalize_candidate_status(
        self,
        batch: BatchImport,
        bc: BatchImportCandidate,
        upload_batch: UploadBatch,
        confirmed_doc_ids: list,
        uploaded_doc_types: set,
        required_rules: list,
        mandatory_doc_names: set,
        prefix: str,
    ) -> None:
        """Update candidate and batch status after pipeline processing."""
        unconfirmed_count = bc.documents_processed - len(confirmed_doc_ids)

        if not confirmed_doc_ids:
            bc.documents_found = 0
            bc.documents_processed = 0
            bc.status = BatchCandidateStatus.NO_DOCUMENTS.value
            await self._status.log(batch.id, bc.id, "warning", "ownership",
                                   f"{prefix}: Ownership not confirmed for any document. Marking as no documents found.")
            await self.db.flush()
            await self._status.emit_candidate_status(batch.id, bc)
            await self._status.emit_summary(batch)
        else:
            matched_mandatory, missing_mandatory = ChecklistMatcher.get_matched_mandatory(uploaded_doc_types, mandatory_doc_names)

            bc.documents_found = len(mandatory_doc_names) if mandatory_doc_names else len(confirmed_doc_ids)
            bc.documents_processed = len(uploaded_doc_types) if mandatory_doc_names else len(confirmed_doc_ids)

            upload_batch.processed_files = len(uploaded_doc_types) if mandatory_doc_names else len(confirmed_doc_ids)
            upload_batch.failed_files = bc.documents_failed + unconfirmed_count
            upload_batch.processing_status = ProcessingStatus.COMPLETED.value

            if not mandatory_doc_names:
                bc.status = BatchCandidateStatus.COMPLETED.value
                await self._status.log(batch.id, bc.id, "info", "complete",
                                       f"{prefix}: Completed. {len(confirmed_doc_ids)} verified & uploaded, "
                                       f"{unconfirmed_count} rejected (ownership), {bc.documents_failed} failed")
            elif missing_mandatory and not matched_mandatory:
                bc.status = BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value
                missing_names = [r.document_name for r in required_rules
                                 if r.is_mandatory and ChecklistMatcher.normalize_doc_type(r.document_name) in missing_mandatory]
                await self._status.log(batch.id, bc.id, "warning", "checklist",
                                       f"{prefix}: No required documents found. Missing: {', '.join(missing_names)}")
            elif missing_mandatory:
                bc.status = BatchCandidateStatus.PARTIAL.value
                missing_names = [r.document_name for r in required_rules
                                 if r.is_mandatory and ChecklistMatcher.normalize_doc_type(r.document_name) in missing_mandatory]
                await self._status.log(batch.id, bc.id, "warning", "checklist",
                                       f"{prefix}: Partial. {len(matched_mandatory)}/{len(mandatory_doc_names)} mandatory docs. "
                                       f"Missing: {', '.join(missing_names)}")
            else:
                bc.status = BatchCandidateStatus.COMPLETED.value
                await self._status.log(batch.id, bc.id, "info", "complete",
                                       f"{prefix}: Completed. All {len(mandatory_doc_names)} mandatory documents verified & uploaded.")

            await self.db.flush()
            await self._status.emit_candidate_status(batch.id, bc)
            await self._status.emit_summary(batch)

    async def _ensure_candidate(self, bc: BatchImportCandidate, correlation_id: str) -> Candidate:
        """Get or create a Candidate record from batch candidate data."""
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

    async def _get_required_document_rules(self) -> list:
        """Load all active required document rules from the checklist."""
        result = await self.db.execute(
            select(RequiredDocumentRule).where(RequiredDocumentRule.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def _cleanup_batch_local_files(self, batch: BatchImport) -> None:
        """Remove local files for a concluded batch. Called after batch completes/fails."""
        batch_dir = settings.upload_path / batch.correlation_id
        if batch_dir.exists():
            try:
                shutil.rmtree(batch_dir)
                logger.info("batch_local_cleanup", batch_id=batch.id, path=str(batch_dir))
                await self._status.log(batch.id, None, "info", "cleanup",
                                       f"Local files cleaned up: {batch_dir}")
            except Exception as e:
                logger.warning("batch_local_cleanup_failed", batch_id=batch.id, error=str(e))
                await self._status.log(batch.id, None, "warning", "cleanup",
                                       f"Failed to clean up local files: {e}")
