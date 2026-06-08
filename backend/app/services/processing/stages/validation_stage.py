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
from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.openai_validator import OpenAIOwnershipResult

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

        # If the document was split into children, validate each child separately
        if ctx.is_split and ctx.child_document_ids:
            await self._validate_child_documents(ctx)
        else:
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

    async def _validate_child_documents(self, ctx: PipelineContext) -> None:
        """Validate ownership for each child document independently."""
        correlation_id = ctx.correlation_id

        for child_id in ctx.child_document_ids:
            # Load child document
            result = await self.db.execute(
                select(Document).where(Document.id == child_id)
            )
            child_doc = result.scalar_one_or_none()
            if not child_doc:
                continue

            # Get the full-doc classification for this child
            cls_result = await self.db.execute(
                select(AIClassification).where(
                    AIClassification.document_id == child_id,
                    AIClassification.page_id == None,
                ).order_by(AIClassification.confidence_score.desc())
            )
            child_classification = cls_result.scalar_one_or_none()

            child_doc.processing_status = ProcessingStatus.VALIDATING.value
            await self.db.flush()

            logger.info(
                "validating_child_document",
                child_id=child_id,
                parent_id=ctx.document_id,
                doc_type=child_classification.document_type if child_classification else "unknown",
            )

            await self._validate_ownership(child_doc, child_classification, correlation_id)

            child_doc.processing_status = ProcessingStatus.VALIDATION_COMPLETE.value
            await self.db.flush()

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


        # === OpenAI FALLBACK (Level 3) ===
        # Only triggers if existing validation failed and feature is enabled
        openai_used = False
        openai_result = None

        if settings.openai_enabled and settings.openai_api_key:
            should_fallback = self._should_trigger_openai_fallback(
                validation_result=validation_result,
                ocr_records=ocr_records,
                classification=best_classification,
            )

            if should_fallback:
                logger.info(
                    "openai_fallback_triggered",
                    document_id=document.id,
                    rule_based_status=validation_result.validation_status,
                    rule_based_score=validation_result.ownership_score,
                    correlation_id=correlation_id,
                )

                try:
                    openai_validator = OpenAIOwnershipValidator()

                    # Extract gender from classification
                    extracted_gender = None
                    if best_classification:
                        if getattr(best_classification, "extracted_gender", None):
                            extracted_gender = best_classification.extracted_gender
                        elif getattr(best_classification, "extracted_fields_json", None):
                            try:
                                fields = json.loads(best_classification.extracted_fields_json)
                                extracted_gender = fields.get("extracted_gender")
                            except (json.JSONDecodeError, TypeError):
                                pass

                    openai_result = await openai_validator.validate(
                        candidate_name=candidate.name,
                        candidate_dob=candidate.dob,
                        candidate_gender=candidate.gender,
                        document_type=best_classification.document_type if best_classification else "unknown",
                        ocr_text=combined_ocr_text,
                        extracted_name=best_classification.extracted_name if best_classification else None,
                        extracted_dob=best_classification.extracted_dob if best_classification else None,
                        extracted_gender=extracted_gender,
                        rule_based_score=validation_result.ownership_score,
                        rule_based_reasoning=validation_result.reasoning,
                        document_file_path=document.file_path,
                        document_mime_type=document.mime_type,
                    )

                    openai_used = True

                    await self.audit.record_processing_event(
                        correlation_id=correlation_id,
                        document_id=document.id,
                        event_type="openai_fallback_complete",
                        stage="validation",
                        status="completed",
                        message=f"OpenAI: {openai_result.validation_status} (conf: {openai_result.confidence_score:.2f})",
                        metadata={
                            "openai_confirmed": openai_result.ownership_confirmed,
                            "openai_confidence": openai_result.confidence_score,
                            "tokens": openai_result.total_tokens,
                            "cost_usd": openai_result.cost_usd,
                        },
                    )

                    # Merge OpenAI result with existing validation
                    validation_result = self._merge_validation_results(
                        rule_based=validation_result,
                        openai_result=openai_result,
                        candidate_name=candidate.name,
                    )

                except Exception as e:
                    logger.error(
                        "openai_fallback_failed",
                        error=str(e),
                        document_id=document.id,
                        correlation_id=correlation_id,
                    )
                    # Continue with original rule-based result
                    await self.audit.record_processing_event(
                        correlation_id=correlation_id,
                        document_id=document.id,
                        event_type="openai_fallback_error",
                        stage="validation",
                        status="failed",
                        message=f"OpenAI error (using rule-based): {str(e)[:200]}",
                        error_details=str(e),
                    )

        # === END: OpenAI FALLBACK ===
        
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
             # OpenAI fallback fields
            openai_fallback_used=openai_used,
            openai_confidence=openai_result.confidence_score if openai_result else None,
            openai_reasoning=openai_result.reasoning if openai_result else None,
            openai_model_used=openai_result.model_used if openai_result else None,
            openai_prompt_tokens=openai_result.prompt_tokens if openai_result else None,
            openai_completion_tokens=openai_result.completion_tokens if openai_result else None,
            openai_total_tokens=openai_result.total_tokens if openai_result else None,
            openai_cost_usd=openai_result.cost_usd if openai_result else None,
            openai_duration_ms=openai_result.duration_ms if openai_result else None,
            openai_key_evidence_json=json.dumps(openai_result.key_evidence) if openai_result and openai_result.key_evidence else None,
            openai_concerns_json=json.dumps(openai_result.concerns) if openai_result and openai_result.concerns else None,
            openai_extracted_owner_name=openai_result.extracted_owner_name if openai_result else None,
            openai_extracted_owner_dob=openai_result.extracted_owner_dob if openai_result else None,
            openai_name_match_score=openai_result.name_match_score if openai_result else None,
            openai_error=openai_result.error if openai_result else None,
            
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
        
        
    def _should_trigger_openai_fallback(
        self,
        validation_result,
        ocr_records: list,
        classification,
    ) -> bool:
        """Determine if OpenAI fallback should be triggered.

        Triggers ONLY when:
        1. Existing validation (Level 1 & 2) completed
        2. Result is UNMATCHED or low PARTIAL_MATCH
        3. OCR and classification are sufficient quality
        4. Not a multi-person document
        """
        from app.models.enums import ValidationStatus

        # Check OCR sufficiency
        has_sufficient_ocr = any(
            r.extracted_text
            and len((r.extracted_text or "").split()) >= 3
            and (r.confidence_score or 0) >= settings.openai_fallback_min_ocr_confidence
            for r in ocr_records
        )

        # Check classification success
        classification_successful = (
            classification is not None
            and getattr(classification, "document_type", None) not in [None, "unknown", "photograph"]
            and (getattr(classification, "confidence_score", 0) or 0) >= settings.openai_fallback_min_classification_confidence
            and not getattr(classification, "error_message", None)
        )

        # Check existing validation failed or low confidence
        validation_needs_help = (
            validation_result.validation_status == ValidationStatus.UNMATCHED.value
            or (
                validation_result.validation_status == ValidationStatus.PARTIAL_MATCH.value
                and validation_result.ownership_score < settings.openai_fallback_max_ownership_score
            )
        )

        # Additional safeguards
        not_multi_person = not validation_result.multi_person_detected
        not_already_matched = validation_result.validation_status != ValidationStatus.MATCHED.value
        not_not_applicable = validation_result.validation_status != ValidationStatus.NOT_APPLICABLE.value

        should_trigger = (
            has_sufficient_ocr
            and classification_successful
            and validation_needs_help
            and not_multi_person
            and not_already_matched
            and not_not_applicable
        )

        if should_trigger:
            logger.info(
                "openai_fallback_eligible",
                validation_status=validation_result.validation_status,
                ownership_score=validation_result.ownership_score,
            )

        return should_trigger

    def _merge_validation_results(self, rule_based, openai_result: OpenAIOwnershipResult, candidate_name: str = ""):
        """Merge existing validation result with OpenAI result.

        Strategy:
        - Compare candidate name against OpenAI-extracted owner name (not OCR-extracted)
        - Use NameMatcher for structured comparison
        - HIGH OpenAI confidence (>=0.8) + name match confirmed: Override to MATCHED
        - MEDIUM confidence (0.5-0.8): Use name match score for decision
        - LOW confidence (<0.5): Keep original, add OpenAI context
        """
        from app.models.enums import ValidationStatus
        from app.services.validation.ownership import OwnershipValidationResult
        from app.services.validation.matcher import NameMatcher

        # Perform candidate name vs OpenAI-extracted owner name comparison
        name_matcher = NameMatcher()
        openai_name_match_score = None
        openai_name_match_confirmed = None

        if openai_result.extracted_owner_name and candidate_name:
            # This is the KEY comparison: candidate name vs document owner name (per OpenAI)
            # NameMatcher.match(candidate_name, text_to_search) - we pass extracted owner name as text
            name_result = name_matcher.match(
                candidate_name=candidate_name,
                ocr_text=openai_result.extracted_owner_name,
            )
            openai_name_match_score = name_result.score
            openai_name_match_confirmed = name_result.score >= 85.0

            # Store on the openai_result for persistence
            openai_result.name_match_score = openai_name_match_score
            openai_result.name_match_confirmed = openai_name_match_confirmed

            logger.info(
                "openai_name_comparison",
                extracted_owner_name=openai_result.extracted_owner_name,
                name_match_score=openai_name_match_score,
                name_match_confirmed=openai_name_match_confirmed,
            )

        # HIGH CONFIDENCE OVERRIDE
        if openai_result.confidence_score >= 0.8 and openai_result.ownership_confirmed:
            # If we have a name match score from OpenAI extraction, use it for final decision
            if openai_name_match_confirmed is not None:
                confirmed = openai_name_match_confirmed
                if confirmed:
                    status = ValidationStatus.MATCHED.value
                    confidence = "HIGH"
                    score = max(openai_name_match_score or 0, openai_result.confidence_score * 100)
                else:
                    # OpenAI says confirmed but our name comparison disagrees
                    status = ValidationStatus.PARTIAL_MATCH.value
                    confidence = "MEDIUM"
                    score = openai_result.confidence_score * 100
                    confirmed = False
            else:
                confirmed = True
                status = ValidationStatus.MATCHED.value
                confidence = "HIGH"
                score = openai_result.confidence_score * 100

            logger.info(
                "openai_override_applied",
                original_status=rule_based.validation_status,
                original_score=rule_based.ownership_score,
                openai_confidence=openai_result.confidence_score,
                openai_extracted_owner=openai_result.extracted_owner_name,
                name_match_score=openai_name_match_score,
            )
            return OwnershipValidationResult(
                validation_status=status,
                ownership_score=score,
                confidence=confidence,
                name_match_score=openai_name_match_score if openai_name_match_score is not None else rule_based.name_match_score,
                name_match_level=rule_based.name_match_level,
                name_matched_tokens=rule_based.name_matched_tokens,
                name_total_tokens=rule_based.name_total_tokens,
                dob_match=rule_based.dob_match,
                dob_partial=rule_based.dob_partial,
                gender_match=rule_based.gender_match,
                multi_person_detected=rule_based.multi_person_detected,
                ownership_confirmed=confirmed,
                reasoning=f"OpenAI Validation (confidence: {openai_result.confidence_score:.2f}, extracted owner: '{openai_result.extracted_owner_name}'): {openai_result.reasoning}",
                mismatches=rule_based.mismatches,
                requires_manual_review=len(openai_result.concerns) > 0,
                manual_review_reasons=openai_result.concerns if openai_result.concerns else [],
                processing_duration_ms=rule_based.processing_duration_ms,
            )

        # MEDIUM CONFIDENCE - Use name comparison for decision
        elif openai_result.confidence_score >= 0.5:
            # If we have a name match from OpenAI extraction, weigh it heavily
            if openai_name_match_score is not None:
                combined_score = (rule_based.ownership_score + openai_name_match_score) / 2
            else:
                combined_score = (rule_based.ownership_score + openai_result.confidence_score * 100) / 2

            if combined_score >= 85:
                status = ValidationStatus.MATCHED.value
                confidence = "HIGH"
                confirmed = True
            elif combined_score >= 60:
                status = ValidationStatus.PARTIAL_MATCH.value
                confidence = "MEDIUM"
                confirmed = False
            else:
                status = ValidationStatus.UNMATCHED.value
                confidence = "LOW"
                confirmed = False

            return OwnershipValidationResult(
                validation_status=status,
                ownership_score=combined_score,
                confidence=confidence,
                name_match_score=openai_name_match_score if openai_name_match_score is not None else rule_based.name_match_score,
                name_match_level=rule_based.name_match_level,
                name_matched_tokens=rule_based.name_matched_tokens,
                name_total_tokens=rule_based.name_total_tokens,
                dob_match=rule_based.dob_match,
                dob_partial=rule_based.dob_partial,
                gender_match=rule_based.gender_match,
                multi_person_detected=rule_based.multi_person_detected,
                ownership_confirmed=confirmed,
                reasoning=f"Combined (rule: {rule_based.ownership_score:.1f}, OpenAI name match: {openai_name_match_score or 'N/A'}, extracted owner: '{openai_result.extracted_owner_name}'): {openai_result.reasoning}",
                mismatches=rule_based.mismatches,
                requires_manual_review=True,
                manual_review_reasons=["OpenAI fallback used - combined scoring"] + (openai_result.concerns or []) + rule_based.manual_review_reasons,
                processing_duration_ms=rule_based.processing_duration_ms,
            )

        # LOW CONFIDENCE - Keep original
        else:
            enhanced_reasoning = f"{rule_based.reasoning} | OpenAI low confidence ({openai_result.confidence_score:.2f}): {openai_result.reasoning[:200]}"
            enhanced_manual_reasons = rule_based.manual_review_reasons.copy()
            if openai_result.concerns:
                enhanced_manual_reasons.extend([f"OpenAI concern: {c}" for c in openai_result.concerns])

            return OwnershipValidationResult(
                validation_status=rule_based.validation_status,
                ownership_score=rule_based.ownership_score,
                confidence=rule_based.confidence,
                name_match_score=rule_based.name_match_score,
                name_match_level=rule_based.name_match_level,
                name_matched_tokens=rule_based.name_matched_tokens,
                name_total_tokens=rule_based.name_total_tokens,
                dob_match=rule_based.dob_match,
                dob_partial=rule_based.dob_partial,
                gender_match=rule_based.gender_match,
                multi_person_detected=rule_based.multi_person_detected,
                ownership_confirmed=rule_based.ownership_confirmed,
                reasoning=enhanced_reasoning,
                mismatches=rule_based.mismatches,
                requires_manual_review=rule_based.requires_manual_review or len(openai_result.concerns) > 0,
                manual_review_reasons=enhanced_manual_reasons,
                processing_duration_ms=rule_based.processing_duration_ms,
            )
        
