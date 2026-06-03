"""Service responsible for uploading verified documents to Google Drive."""

from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document
from app.models.batch_import import BatchImport
from app.models.batch_import_candidate import BatchImportCandidate
from app.models.classification import AIClassification
from app.services.integrations.drive_service import GoogleDriveService
from app.services.settings.file_naming_service import FileNamingRuleService
from app.core.logging import get_logger

logger = get_logger("batch.drive_upload")


class DriveUploadService:
    """Handles uploading confirmed documents to Google Drive with proper naming."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def upload_document(
        self,
        drive_service: GoogleDriveService,
        storage_folder_id: Optional[str],
        batch: BatchImport,
        bc: BatchImportCandidate,
        doc_id: str,
    ) -> tuple[GoogleDriveService, Optional[str]]:
        """Upload a confirmed document to Drive with lazy folder creation and retry on connection error.

        Returns the (possibly refreshed) drive_service and storage_folder_id.
        """
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
                    logger.info("drive_folder_created", folder=folder_name, candidate=bc.source_name)

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
                logger.info("drive_upload_success", filename=resolved_filename, doc_id=doc_id)
                return drive_service, storage_folder_id

            except (OSError, ConnectionError) as e:
                if attempt == 0:
                    logger.warning("drive_connection_stale", doc_id=doc_id, error=str(e))
                    # Attempt to refresh the drive service
                    from app.services.batch.discovery_service import DiscoveryService
                    discovery = DiscoveryService(self.db)
                    refreshed = await discovery.get_drive_service()
                    drive_service = refreshed or drive_service
                else:
                    logger.warning("drive_upload_failed", doc_id=doc_id, error=str(e))

            except Exception as e:
                logger.warning("drive_upload_failed", doc_id=doc_id, error=str(e))
                break

        return drive_service, storage_folder_id

    async def _get_document_type(self, doc_id: str) -> str:
        """Get the AI-classified document type for a document."""
        result = await self.db.execute(
            select(AIClassification.document_type)
            .where(
                AIClassification.document_id == doc_id,
                AIClassification.page_id.is_(None),
            )
            .order_by(AIClassification.confidence_score.desc())
        )
        doc_type = result.scalar_one_or_none()
        return doc_type or "Document"
