import base64
import json
from dataclasses import dataclass
from typing import List, Optional

from app.core.logging import get_logger

logger = get_logger("integrations.gmail")


@dataclass
class DiscoveredAttachment:
    """An attachment found in a Gmail message."""
    message_id: str
    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int
    subject: str
    sender: str
    date: str


class GmailScanner:
    """Scans Gmail for emails containing document attachments for a candidate."""

    SUPPORTED_MIMES = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    def __init__(self, credentials_json: str):
        """Initialize with OAuth2 credentials JSON string."""
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
        self._service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        logger.info("gmail_scanner_initialized")

    def search_for_candidate(
        self,
        candidate_name: str,
        candidate_email: Optional[str] = None,
        max_results: int = 50,
    ) -> List[DiscoveredAttachment]:
        """Search Gmail for messages with attachments related to a candidate.

        Strategy:
        - Find emails FROM the candidate email (from Excel)
        - Accept all supported attachments; OCR will handle document ownership verification.
        """
        attachments: List[DiscoveredAttachment] = []
        seen_message_ids: set = set()

        if candidate_email:
            query = f"from:{candidate_email} has:attachment"
            try:
                result = (
                    self._service.users()
                    .messages()
                    .list(userId="me", q=query, maxResults=max_results)
                    .execute()
                )
                messages = result.get("messages", [])
                logger.info("gmail_search", query=query, results=len(messages))

                for msg_ref in messages:
                    msg_id = msg_ref["id"]
                    if msg_id in seen_message_ids:
                        continue
                    seen_message_ids.add(msg_id)

                    msg = (
                        self._service.users()
                        .messages()
                        .get(userId="me", id=msg_id, format="full")
                        .execute()
                    )

                    headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                    subject = headers.get("Subject", "(no subject)")
                    sender = headers.get("From", "")
                    date = headers.get("Date", "")

                    found = self._extract_attachments(msg_id, msg.get("payload", {}), subject, sender, date)
                    attachments.extend(found)

            except Exception as e:
                logger.error("gmail_search_error", query=query, error=str(e))

        logger.info("gmail_scan_complete", candidate=candidate_name, total_attachments=len(attachments))
        return attachments

    def _extract_attachments(  # noqa: PLR0913
        self, message_id: str, payload: dict, subject: str, sender: str, date: str
    ) -> List[DiscoveredAttachment]:
        """Recursively extract attachment metadata from message payload."""
        attachments = []
        parts = payload.get("parts", [])
        if not parts and payload.get("filename"):
            parts = [payload]

        for part in parts:
            mime = part.get("mimeType", "")
            filename = part.get("filename", "")
            body = part.get("body", {})
            attachment_id = body.get("attachmentId")
            size = body.get("size", 0)

            if filename and attachment_id and mime in self.SUPPORTED_MIMES:
                attachments.append(
                    DiscoveredAttachment(
                        message_id=message_id,
                        attachment_id=attachment_id,
                        filename=filename,
                        mime_type=mime,
                        size_bytes=size,
                        subject=subject,
                        sender=sender,
                        date=date,
                    )
                )

            # Recurse into nested parts
            if part.get("parts"):
                attachments.extend(
                    self._extract_attachments(message_id, part, subject, sender, date)
                )

        return attachments

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download an attachment's raw bytes."""
        result = (
            self._service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        data = result.get("data", "")
        return base64.urlsafe_b64decode(data)
