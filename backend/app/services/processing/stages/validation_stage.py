"""Validation stage: ownership verification using best-match strategy."""

import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.document import Document
from app.models.ocr_result import OCRResult
from app.models.classification import AIClassification
from app.models.validation_result import ValidationResult
from app.models.candidate import Candidate
from app.models.enums import ProcessingStatus, AuditAction
from app.services.validation.ownership import OwnershipValidator
from app.services.processing.stages.context import PipelineContext
from app.services.audit.logger import AuditService
from app.core.logging import get_logger

logger = get_logger("processing.stages.validation")


class ValidationStage:
    """Validates document ownership using best-match strategy across all classifications."""

    def __init__(self, db: AsyncSession, ownership_validator: OwnershipValidator, audit: AuditService):
        self.db = db
        self.ownership_validator = ownership_validator
        self.audit = audit

    async def execute(self, ctx: PipelineContext) -> None:
        """Run ownership validation against all classifications."""
        document = ctx.document
        document_id = ctx.document_id
        correlation_id = ctx.correlation_id
        classification = ctx.full_classification

        logger.info("stage_start", stage="validation", document_id=document_id)
        document.processing_status = ProcessingStatus.VALIDATING.value
        await self.db.flush()

        await self.audit.log(
            correlation_id=correlation_id,
            action=AuditAction.VALIDATION_START.value,
            message="Ownership validation started",
            document_id=document_id,
            processing_stage="validation",
        )

        await self._validate_ownership(document, classification, correlation_id)

        logger.info("stage_complete", stage="validation", document_id=document_id)
        document.processing_status = ProcessingStatus.VALIDATION_COMPLETE.value
        await self.db.flush()

        await self.audit.log(
            correlation_id=correlation_id,
            action=AuditAction.VALIDATION_COMPLETE.value,
            message="Ownership validation complete",
            document_id=document_id,
            processing_stage="validation",
        )

    async def _validate_ownership(
        self, document: Document, classification: Optional[AIClassification], correlation_id: str
    ) -> None:
        """Best-match ownership validation against all page/full-doc classifications."""
        # Load candidate
        result = await self.db.execute(
            select(Candidate).where(Candidate.id == document.candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            return

        # Get full OCR text for this document
        ocr_results = await self.db.execute(
            select(OCRResult).where(OCRResult.document_id == document.id)
        )
        ocr_records = ocr_results.scalars().all()
        combined_ocr_text = "\n".join(r.extracted_text for r in ocr_records if r.extracted_text)
        avg_confidence = (
            sum(r.confidence_score for r in ocr_records if r.confidence_score)
            / len(ocr_records) if ocr_records else 0.0
        )

        # === BEST-MATCH STRATEGY ===
        # Query ALL classifications for this document (per-page + full-doc).
        # Validate ownership against each classification that has an extracted_name.
        # Use the result with the highest ownership score.
        all_classifications_result = await self.db.execute(
            select(AIClassification).where(
                AIClassification.document_id == document.id
            ).order_by(AIClassification.confidence_score.desc())
        )
        all_classifications = all_classifications_result.scalars().all()

        # Collect candidates for validation: classifications with extracted_name
        classifications_with_name = [
            c for c in all_classifications if c.extracted_name
        ]

        # If no classification has extracted_name, fall back to the full-doc classification
        if not classifications_with_name and classification:
            classifications_with_name = [classification]

        best_result = None
        best_score = -1.0
        best_classification = None

        for cls in classifications_with_name:
            extracted_name = cls.extracted_name
            extracted_dob = cls.extracted_dob
            doc_type = cls.document_type or "unknown"

            # Extract gender
            extracted_gender = None
            if cls.extracted_gender:
                extracted_gender = cls.extracted_gender
            elif cls.extracted_fields_json:
                try:
                    fields = json.loads(cls.extracted_fields_json)
                    extracted_gender = fields.get("extracted_gender")
                except (json.JSONDecodeError, TypeError):
                    pass

            vr = self.ownership_validator.validate(
                candidate_name=candidate.name,
                candidate_dob=candidate.dob,
                candidate_gender=candidate.gender,
                extracted_name=extracted_name,
                extracted_dob=extracted_dob,
                extracted_gender=extracted_gender,
                ocr_text=combined_ocr_text,
                document_type=doc_type,
                ocr_confidence=avg_confidence,
            )

            if vr.ownership_score > best_score:
                best_score = vr.ownership_score
                best_result = vr
                best_classification = cls

        # If no classifications at all, run validation with no extracted data
        if best_result is None:
            doc_type = classification.document_type if classification else "unknown"
            best_result = self.ownership_validator.validate(
                candidate_name=candidate.name,
                candidate_dob=candidate.dob,
                candidate_gender=candidate.gender,
                extracted_name=None,
                extracted_dob=None,
                extracted_gender=None,
                ocr_text=combined_ocr_text,
                document_type=doc_type,
                ocr_confidence=avg_confidence,
            )
            best_classification = classification

        # If multi-person detected and only partial match, require manual review
        if best_result.multi_person_detected and not best_result.ownership_confirmed:
            best_result.requires_manual_review = True
            if "Multi-person document with partial match" not in best_result.manual_review_reasons:
                best_result.manual_review_reasons.append("Multi-person document with partial match")

        validation_result = best_result

        logger.info(
            "ownership_best_match",
            document_id=document.id,
            classifications_checked=len(classifications_with_name),
            best_score=f"{validation_result.ownership_score:.1f}",
            best_source="page" if (best_classification and best_classification.page_id) else "full_doc",
            confirmed=validation_result.ownership_confirmed,
        )

        validation_record = ValidationResult(
            document_id=document.id,
            candidate_id=candidate.id,
            validation_status=validation_result.validation_status,
            ownership_score=validation_result.ownership_score,
            confidence=validation_result.confidence,
            name_match_score=validation_result.name_match_score,
            name_match_level=validation_result.name_match_level,
            name_matched_tokens=validation_result.name_matched_tokens,
            name_total_tokens=validation_result.name_total_tokens,
            dob_match=validation_result.dob_match,
            dob_partial=validation_result.dob_partial,
            gender_match=validation_result.gender_match,
            multi_person_detected=validation_result.multi_person_detected,
            name_match=validation_result.ownership_confirmed,
            id_number_match=validation_result.id_number_match,
            ownership_confirmed=validation_result.ownership_confirmed,
            validation_reasoning=validation_result.reasoning,
            mismatches_json=json.dumps(validation_result.mismatches),
            requires_manual_review=validation_result.requires_manual_review,
            manual_review_reasons_json=json.dumps(validation_result.manual_review_reasons),
            processing_duration_ms=validation_result.processing_duration_ms,
            correlation_id=correlation_id,
        )
        self.db.add(validation_record)
        await self.db.flush()

        await self.audit.record_processing_event(
            correlation_id=correlation_id,
            document_id=document.id,
            event_type="validation_complete",
            stage="validation",
            status="completed",
            message=validation_result.reasoning,
            metadata={
                "name_score": validation_result.name_match_score,
                "ownership_score": validation_result.ownership_score,
                "ownership_confirmed": validation_result.ownership_confirmed,
                "classifications_checked": len(classifications_with_name),
                "best_source_page_id": best_classification.page_id if best_classification else None,
            },
        )
