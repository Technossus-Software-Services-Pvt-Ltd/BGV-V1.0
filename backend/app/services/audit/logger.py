import json
import re
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.processing_event import ProcessingEvent
from app.models.enums import AuditAction, LogLevel
from app.core.logging import get_logger

logger = get_logger("audit")

# PII patterns for masking in logs
PII_PATTERNS = {
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    "phone": re.compile(r"\b[6-9]\d{9}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
}


def mask_pii(text: str) -> str:
    if not text:
        return text
    masked = text
    for pii_type, pattern in PII_PATTERNS.items():
        if pii_type == "aadhaar":
            masked = pattern.sub("XXXX XXXX XXXX", masked)
        elif pii_type == "pan":
            masked = pattern.sub("XXXXX0000X", masked)
        elif pii_type == "phone":
            masked = pattern.sub("XXXXXXXXXX", masked)
        elif pii_type == "email":
            masked = pattern.sub("[EMAIL REDACTED]", masked)
    return masked


class AuditService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def log(
        self,
        correlation_id: str,
        action: str,
        message: str,
        log_level: str = LogLevel.INFO.value,
        candidate_id: Optional[str] = None,
        document_id: Optional[str] = None,
        page_id: Optional[str] = None,
        processing_stage: Optional[str] = None,
        details: Optional[dict] = None,
        duration_ms: Optional[int] = None,
        error_details: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        masked_message = mask_pii(message)
        masked_error = mask_pii(error_details) if error_details else None

        audit_entry = AuditLog(
            correlation_id=correlation_id,
            candidate_id=candidate_id,
            document_id=document_id,
            page_id=page_id,
            action=action,
            log_level=log_level,
            processing_stage=processing_stage,
            message=masked_message,
            details_json=json.dumps(details) if details else None,
            duration_ms=duration_ms,
            error_details=masked_error,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.db.add(audit_entry)
        await self.db.flush()

        logger.info(
            "audit_log",
            correlation_id=correlation_id,
            action=action,
            level=log_level,
            stage=processing_stage,
            message=masked_message,
        )

        return audit_entry

    async def record_processing_event(
        self,
        correlation_id: str,
        document_id: str,
        event_type: str,
        stage: str,
        status: str,
        message: Optional[str] = None,
        page_id: Optional[str] = None,
        confidence: Optional[float] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[dict] = None,
        error_details: Optional[str] = None,
    ) -> ProcessingEvent:
        event = ProcessingEvent(
            correlation_id=correlation_id,
            document_id=document_id,
            page_id=page_id,
            event_type=event_type,
            stage=stage,
            status=status,
            message=message,
            confidence=confidence,
            duration_ms=duration_ms,
            metadata_json=json.dumps(metadata) if metadata else None,
            error_details=error_details,
        )

        self.db.add(event)
        await self.db.flush()

        return event
