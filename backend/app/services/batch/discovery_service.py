"""Service responsible for discovering candidate documents from Gmail and Google Drive."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.integration_config import IntegrationConfig
from app.models.enums import IntegrationProvider
from app.services.integrations.gmail_scanner import GmailScanner, DiscoveredAttachment
from app.services.integrations.drive_service import GoogleDriveService, DiscoveredDriveFile
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger("batch.discovery")

# Dedicated thread pool for blocking Google API I/O calls
_io_executor = ThreadPoolExecutor(max_workers=settings.google_io_pool_size, thread_name_prefix="google-io")


class DiscoveryService:
    """Handles integration config loading and document discovery from Gmail/Drive."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_gmail_scanner(self) -> Optional[GmailScanner]:
        """Load Gmail integration config and create scanner."""
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

    async def get_drive_service(self) -> Optional[GoogleDriveService]:
        """Load Google Drive integration config and create service."""
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

    async def discover_documents(
        self,
        candidate_name: str,
        candidate_email: Optional[str],
        gmail_scanner: Optional[GmailScanner],
        drive_service: Optional[GoogleDriveService],
    ) -> tuple[list[DiscoveredAttachment], list[DiscoveredDriveFile]]:
        """Discover documents from Gmail and Drive for a candidate.

        Returns (gmail_attachments, drive_files).
        """
        gmail_attachments: list[DiscoveredAttachment] = []
        drive_files: list[DiscoveredDriveFile] = []

        if gmail_scanner:
            try:
                loop = asyncio.get_running_loop()
                gmail_attachments = await loop.run_in_executor(
                    _io_executor, gmail_scanner.search_for_candidate,
                    candidate_name, candidate_email,
                )
            except Exception as e:
                logger.warning("gmail_scan_failed", name=candidate_name, error=str(e))
                raise

        return gmail_attachments, drive_files
