import io
import json
from dataclasses import dataclass
from typing import List, Optional

from app.core.logging import get_logger

logger = get_logger("integrations.drive")


@dataclass
class DiscoveredDriveFile:
    """A file found in Google Drive."""
    file_id: str
    filename: str
    mime_type: str
    size_bytes: int
    parent_folder_id: Optional[str]
    parent_folder_name: Optional[str]
    modified_time: str
    web_view_link: str


class GoogleDriveService:
    """Scans Google Drive for candidate documents and manages storage folders."""

    SUPPORTED_MIMES = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    # Google Docs mimes that can be exported to PDF
    EXPORTABLE_MIMES = {
        "application/vnd.google-apps.document": "application/pdf",
        "application/vnd.google-apps.spreadsheet": "application/pdf",
    }

    def __init__(self, credentials_json: str, config_json: Optional[str] = None):
        """Initialize with OAuth2 credentials and optional config."""
        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError:
            raise RuntimeError(
                "Google API client libraries are required. "
                "Install with: pip install google-api-python-client google-auth-oauthlib"
            )

        creds_data = json.loads(credentials_json)
        credentials = Credentials.from_authorized_user_info(creds_data)
        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)

        # Parse config
        self._config = json.loads(config_json) if config_json else {}
        self._search_folder_ids: List[str] = self._config.get("search_folder_ids", [])
        self._storage_root_folder_id: Optional[str] = self._config.get("storage_root_folder_id")

        logger.info(
            "drive_service_initialized",
            search_folders=len(self._search_folder_ids),
            has_storage_root=bool(self._storage_root_folder_id),
        )

    def search_for_candidate(
        self,
        candidate_name: str,
        candidate_id: str,
        max_results: int = 100,
    ) -> List[DiscoveredDriveFile]:
        """Search configured Drive folders for files matching candidate name or ID."""
        files: List[DiscoveredDriveFile] = []
        seen_ids: set = set()

        search_terms = [candidate_name]
        if candidate_id:
            search_terms.append(candidate_id)

        for term in search_terms:
            query_parts = [
                f"name contains '{self._escape_query(term)}'",
                "trashed = false",
            ]

            # Restrict to supported MIME types
            mime_filter = " or ".join(
                [f"mimeType = '{m}'" for m in self.SUPPORTED_MIMES]
                + [f"mimeType = '{m}'" for m in self.EXPORTABLE_MIMES]
            )
            query_parts.append(f"({mime_filter})")

            # Restrict to search folders if configured
            if self._search_folder_ids:
                folder_filter = " or ".join(
                    [f"'{fid}' in parents" for fid in self._search_folder_ids]
                )
                query_parts.append(f"({folder_filter})")

            query = " and ".join(query_parts)

            try:
                result = (
                    self._service.files()
                    .list(
                        q=query,
                        pageSize=max_results,
                        fields="files(id, name, mimeType, size, parents, modifiedTime, webViewLink)",
                        supportsAllDrives=True,
                        includeItemsFromAllDrives=True,
                    )
                    .execute()
                )

                for f in result.get("files", []):
                    fid = f["id"]
                    if fid in seen_ids:
                        continue
                    seen_ids.add(fid)

                    files.append(
                        DiscoveredDriveFile(
                            file_id=fid,
                            filename=f.get("name", ""),
                            mime_type=f.get("mimeType", ""),
                            size_bytes=int(f.get("size", 0)),
                            parent_folder_id=f.get("parents", [None])[0] if f.get("parents") else None,
                            parent_folder_name=None,
                            modified_time=f.get("modifiedTime", ""),
                            web_view_link=f.get("webViewLink", ""),
                        )
                    )

                logger.info("drive_search", term=term, results=len(result.get("files", [])))
            except Exception as e:
                logger.error("drive_search_error", term=term, error=str(e))

        logger.info("drive_scan_complete", candidate=candidate_name, total_files=len(files))
        return files

    def download_file(self, file_id: str, mime_type: str) -> bytes:
        """Download a file's content. Exports Google Docs types to PDF."""
        if mime_type in self.EXPORTABLE_MIMES:
            export_mime = self.EXPORTABLE_MIMES[mime_type]
            request = self._service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            request = self._service.files().get_media(fileId=file_id)

        buffer = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload

        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        return buffer.getvalue()

    def create_storage_folder(self, batch_code: str, candidate_name: str) -> str:
        """Create a folder in Drive for storing processed documents.
        Returns the folder ID.
        Folder name format: batchcode-candidate-name
        """
        safe_name = candidate_name.replace("/", "-").replace("\\", "-").strip()
        folder_name = f"{batch_code}-{safe_name}"

        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if self._storage_root_folder_id:
            metadata["parents"] = [self._storage_root_folder_id]

        folder = self._service.files().create(body=metadata, fields="id").execute()
        folder_id = folder["id"]
        logger.info("drive_folder_created", folder_name=folder_name, folder_id=folder_id)
        return folder_id

    def upload_file(self, folder_id: str, filename: str, file_bytes: bytes, mime_type: str) -> str:
        """Upload a file to a specific Drive folder. Returns the file ID."""
        from googleapiclient.http import MediaInMemoryUpload

        metadata = {
            "name": filename,
            "parents": [folder_id],
        }
        media = MediaInMemoryUpload(file_bytes, mimetype=mime_type)
        uploaded = (
            self._service.files()
            .create(body=metadata, media_body=media, fields="id")
            .execute()
        )
        return uploaded["id"]

    def delete_folder(self, folder_id: str) -> None:
        """Delete a folder (and its contents) from Drive."""
        self._service.files().delete(fileId=folder_id).execute()
        logger.info("drive_folder_deleted", folder_id=folder_id)

    @staticmethod
    def _escape_query(term: str) -> str:
        """Escape single quotes in Drive query strings."""
        return term.replace("'", "\\'")
