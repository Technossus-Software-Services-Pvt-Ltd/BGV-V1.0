import asyncio
import json
import re
import uuid
from datetime import datetime, timezone
from typing import List, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.batch_import_candidate import BatchImportCandidate
from app.models.integration_config import IntegrationConfig
from app.models.notification_log import NotificationLog
from app.models.required_document_rule import RequiredDocumentRule
from app.models.enums import NotificationStatus, BatchCandidateStatus

logger = get_logger("services.notifications")


class NotificationService:
    """Handles composing and sending email notifications for review queue candidates."""

    @staticmethod
    async def queue_notifications(
        db: AsyncSession,
        candidate_ids: List[str],
    ) -> List[str]:
        """Create notification_log entries for the given candidates. Returns created log IDs."""
        # Load candidates
        result = await db.execute(
            select(BatchImportCandidate).where(BatchImportCandidate.id.in_(candidate_ids))
        )
        candidates = list(result.scalars().all())

        if not candidates:
            return []

        # Load required document rules for email content
        rules_result = await db.execute(
            select(RequiredDocumentRule).where(
                RequiredDocumentRule.is_active.is_(True),
                RequiredDocumentRule.is_mandatory.is_(True),
            )
        )
        mandatory_rules = list(rules_result.scalars().all())
        mandatory_names = {r.document_name for r in mandatory_rules}

        log_ids = []
        for candidate in candidates:
            if not candidate.source_email:
                continue

            subject, body_html = NotificationService._compose_email(
                candidate, mandatory_names
            )

            log_entry = NotificationLog(
                id=str(uuid.uuid4()),
                candidate_id=candidate.id,
                recipient_email=candidate.source_email,
                subject=subject,
                body_html=body_html,
                status=NotificationStatus.QUEUED.value,
            )
            db.add(log_entry)
            log_ids.append(log_entry.id)

        await db.commit()
        return log_ids

    @staticmethod
    def _compose_email(
        candidate: BatchImportCandidate,
        mandatory_names: Set[str],
    ) -> tuple[str, str]:
        """Generate subject and HTML body based on candidate status."""
        name = candidate.source_name

        if candidate.status == BatchCandidateStatus.AWAITING_REQUIRED_DOCUMENTS.value:
            subject = f"Action Required: Submit Required Documents - {name}"
            doc_list = "".join(f"<li>{doc}</li>" for doc in sorted(mandatory_names))
            body_html = f"""
<p>Dear {name},</p>
<p>We have not received any of the required documents for your background verification.</p>
<p><strong>Please submit the following mandatory documents:</strong></p>
<ul>{doc_list}</ul>
<p>Kindly submit all the above documents at the earliest to proceed with your verification.</p>
<p>Regards,<br/>BGV Team</p>
"""

        elif candidate.status == BatchCandidateStatus.PARTIAL.value:
            # Determine missing docs from error_message or compute
            missing = NotificationService._extract_missing_docs(
                candidate.error_message, mandatory_names
            )
            doc_list = "".join(f"<li>{doc}</li>" for doc in sorted(missing))
            subject = f"Action Required: Missing Documents - {name}"
            body_html = f"""
<p>Dear {name},</p>
<p>Some of your mandatory documents are still missing for background verification.</p>
<p><strong>Missing documents:</strong></p>
<ul>{doc_list}</ul>
<p>Please submit the above documents to complete your verification process.</p>
<p>Regards,<br/>BGV Team</p>
"""

        elif candidate.status == BatchCandidateStatus.NO_DOCUMENTS.value:
            doc_list = "" .join(f"<li>{doc}</li>" for doc in sorted(mandatory_names))
            subject = f"Action Required: No Documents Received - {name}"
            body_html = f"""
<p>Dear {name},</p>
<p>We have not received any documents from you for the background verification process.</p>
<p><strong>Please submit the following mandatory documents:</strong></p>
<ul>{doc_list}</ul>
<p>You can reply to this email with the documents attached or upload them through the portal.</p>
<p>Regards,<br/>BGV Team</p>
"""

        elif candidate.status == BatchCandidateStatus.FAILED.value:
            error_reason = candidate.error_message or "Processing error"
            subject = f"Action Required: Document Resubmission - {name}"
            body_html = f"""
<p>Dear {name},</p>
<p>Your document processing has failed due to the following reason:</p>
<p><strong>{error_reason}</strong></p>
<p>Please resubmit the document in higher quality (clear scan, minimum 300 DPI, PDF or JPEG format).</p>
<p>Regards,<br/>BGV Team</p>
"""

        else:
            subject = f"BGV Notification - {name}"
            body_html = f"<p>Dear {name},</p><p>Please check your verification status.</p><p>Regards,<br/>BGV Team</p>"

        return subject, body_html.strip()

    @staticmethod
    def _extract_missing_docs(error_message: str | None, mandatory_names: Set[str]) -> Set[str]:
        """Extract missing document names from error_message or return all mandatory."""
        if not error_message:
            return mandatory_names

        # Try to parse comma-separated doc names from error message
        # e.g. "Missing mandatory documents: Aadhaar Card, PAN Card"
        found = set()
        for doc_name in mandatory_names:
            normalized = re.sub(r'[\s_\-]+', '', doc_name.lower())
            if normalized in re.sub(r'[\s_\-]+', '', error_message.lower()):
                continue  # This doc was mentioned as present or similar
            found.add(doc_name)

        return found if found else mandatory_names

    @staticmethod
    async def send_notifications_background(log_ids: List[str]) -> None:
        """Background task: send queued emails via Gmail API. Non-blocking."""
        try:
            async with AsyncSessionLocal() as db:
                # Load Gmail credentials
                gmail_config = await db.execute(
                    select(IntegrationConfig).where(IntegrationConfig.provider == "gmail")
                )
                config = gmail_config.scalar_one_or_none()

                if not config or not config.credentials_json or not config.is_enabled:
                    logger.error("notification_send_failed", reason="Gmail not configured or disabled")
                    # Mark all as failed
                    await NotificationService._mark_failed(
                        db, log_ids, "Gmail integration not configured or disabled"
                    )
                    return

                # Load notification logs
                result = await db.execute(
                    select(NotificationLog).where(NotificationLog.id.in_(log_ids))
                )
                logs = list(result.scalars().all())

                for log_entry in logs:
                    try:
                        # Retry up to 3 times with exponential backoff
                        last_err = None
                        for attempt in range(3):
                            try:
                                await NotificationService._send_single_email(
                                    config.credentials_json, log_entry
                                )
                                last_err = None
                                break
                            except Exception as e:
                                last_err = e
                                if attempt < 2:
                                    await asyncio.sleep(2 ** attempt)

                        if last_err:
                            raise last_err

                        log_entry.status = NotificationStatus.SENT.value
                        log_entry.sent_at = datetime.now(timezone.utc)
                        logger.info("notification_sent", log_id=log_entry.id, to=log_entry.recipient_email)
                    except Exception as e:
                        log_entry.status = NotificationStatus.FAILED.value
                        log_entry.error_message = str(e)[:500]
                        logger.error("notification_send_error", log_id=log_entry.id, error=str(e))

                await db.commit()
                sent_count = sum(1 for l in logs if l.status == NotificationStatus.SENT.value)
                failed_count = sum(1 for l in logs if l.status == NotificationStatus.FAILED.value)
                logger.info(
                    "notification_batch_complete",
                    total=len(logs),
                    sent=sent_count,
                    failed=failed_count,
                )

        except Exception as e:
            logger.error("notification_background_task_error", error=str(e))

    @staticmethod
    async def _send_single_email(credentials_json: str, log_entry: NotificationLog) -> None:
        """Send a single email via Gmail API."""
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds_data = json.loads(credentials_json)
        credentials = Credentials.from_authorized_user_info(creds_data)
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

        # Get sender email (authenticated user)
        profile = service.users().getProfile(userId="me").execute()
        sender_email = profile.get("emailAddress", "")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = log_entry.subject
        msg["From"] = sender_email
        msg["To"] = log_entry.recipient_email

        html_part = MIMEText(log_entry.body_html, "html")
        msg.attach(html_part)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()

    @staticmethod
    async def _mark_failed(db: AsyncSession, log_ids: List[str], reason: str) -> None:
        """Mark all notification logs as failed."""
        result = await db.execute(
            select(NotificationLog).where(NotificationLog.id.in_(log_ids))
        )
        for log_entry in result.scalars().all():
            log_entry.status = NotificationStatus.FAILED.value
            log_entry.error_message = reason
        await db.commit()
