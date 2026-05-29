import json
import time
from typing import Optional
from dataclasses import dataclass, field

from app.services.validation.matcher import (
    NameMatcher, DOBMatcher, GenderMatcher, ConflictDetector, IDNumberMatcher,
    NameMatchResult, DOBMatchResult, GenderMatchResult, MatchLevel,
)
from app.models.enums import ValidationStatus
from app.core.logging import get_logger

logger = get_logger("validation.ownership")

# Scoring weights (only Name determines ownership)
WEIGHT_NAME = 100

# Thresholds per spec (Step 12)
THRESHOLD_MATCHED = 85
THRESHOLD_PARTIAL = 60


@dataclass
class OwnershipValidationResult:
    validation_status: str  # MATCHED, PARTIAL_MATCH, UNMATCHED, NOT_APPLICABLE
    ownership_score: float = 0.0
    confidence: str = ""  # HIGH, MEDIUM, LOW
    # Name
    name_match_score: Optional[float] = None
    name_match_level: Optional[str] = None
    name_matched_tokens: int = 0
    name_total_tokens: int = 0
    # DOB
    dob_match: Optional[bool] = None
    dob_partial: Optional[bool] = None
    # Gender
    gender_match: Optional[bool] = None
    # Conflict detection
    multi_person_detected: bool = False
    # Legacy compatibility
    ownership_confirmed: bool = False
    id_number_match: Optional[bool] = None
    reasoning: str = ""
    mismatches: list = field(default_factory=list)
    requires_manual_review: bool = False
    manual_review_reasons: list = field(default_factory=list)
    processing_duration_ms: int = 0


class OwnershipValidator:
    """Validates document ownership using weighted scoring:
    Name (50) + DOB (35) + Gender (15) = 100
    """

    def __init__(self):
        self.name_matcher = NameMatcher()
        self.dob_matcher = DOBMatcher()
        self.gender_matcher = GenderMatcher()
        self.conflict_detector = ConflictDetector()
        self.id_matcher = IDNumberMatcher()

    def validate(
        self,
        candidate_name: str,
        candidate_dob: Optional[str],
        candidate_gender: Optional[str],
        extracted_name: Optional[str],
        extracted_dob: Optional[str],
        extracted_gender: Optional[str],
        ocr_text: Optional[str],
        document_type: str,
        ocr_confidence: float = 0.0,
        # Legacy ID fields
        candidate_pan: Optional[str] = None,
        candidate_aadhaar_last_four: Optional[str] = None,
        extracted_id_number: Optional[str] = None,
    ) -> OwnershipValidationResult:
        start_time = time.time()
        logger.info(
            "validation_start",
            document_type=document_type,
            candidate_name=candidate_name,
            extracted_name=extracted_name,
            has_dob=bool(candidate_dob),
            has_gender=bool(candidate_gender),
        )

        mismatches = []
        manual_review_reasons = []

        # Step 4: Non-document detection
        if not ocr_text or len((ocr_text or "").split()) < 3:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("validation_not_applicable", reason="insufficient_text", duration_ms=duration_ms)
            return OwnershipValidationResult(
                validation_status=ValidationStatus.NOT_APPLICABLE.value,
                reasoning="No meaningful text for ownership validation",
                processing_duration_ms=duration_ms,
            )

        if ocr_confidence > 0 and ocr_confidence < 0.3:
            manual_review_reasons.append("OCR confidence below threshold")

        # Step 13: Conflict detection
        conflicts = self.conflict_detector.detect(ocr_text, extracted_name)
        multi_person = conflicts["multi_person"]
        if multi_person:
            manual_review_reasons.append(f"Multi-person document: {'; '.join(conflicts['details'])}")

        # Step 9: Name matching (Weight: 50)
        name_score_normalized = 0.0
        name_result: Optional[NameMatchResult] = None
        if extracted_name and candidate_name:
            name_result = self.name_matcher.match(candidate_name, extracted_name)
            name_score_normalized = name_result.score / 100.0  # Normalize to 0-1

            if name_result.level == MatchLevel.NONE:
                mismatches.append(f"Name mismatch: candidate='{candidate_name}', document='{extracted_name}' (score: {name_result.score:.1f})")
            elif name_result.level in (MatchLevel.WEAK, MatchLevel.PARTIAL):
                mismatches.append(f"Name partial: candidate='{candidate_name}', document='{extracted_name}' (score: {name_result.score:.1f})")

            # Safety: never auto-match on single token or surname only
            if name_result.total_tokens >= 2 and name_result.matched_tokens <= 1 and name_result.score >= THRESHOLD_MATCHED:
                manual_review_reasons.append("Only single name token matched from multi-token name")
        elif not extracted_name:
            # No name extracted - can't validate, reduce score
            name_score_normalized = 0.0

        # DOB matching (stored for data, NOT used in scoring)
        dob_result: Optional[DOBMatchResult] = None
        if candidate_dob and ocr_text:
            dob_result = self.dob_matcher.match(candidate_dob, extracted_dob or ocr_text)

        # Gender matching (stored for data, NOT used in scoring)
        gender_result: Optional[GenderMatchResult] = None
        if candidate_gender and ocr_text:
            gender_result = self.gender_matcher.match(candidate_gender, extracted_gender or ocr_text)

        # Weighted scoring (Name only)
        name_weight = WEIGHT_NAME if (extracted_name and candidate_name) else 0
        total_weight = name_weight

        if total_weight == 0:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("validation_not_applicable", reason="no_validation_data", duration_ms=duration_ms)
            return OwnershipValidationResult(
                validation_status=ValidationStatus.NOT_APPLICABLE.value,
                reasoning="No ownership data could be validated (no name provided or extracted)",
                processing_duration_ms=duration_ms,
            )

        # Compute weighted score scaled to available weights
        raw_score = name_score_normalized * name_weight
        # Scale to 100 based on available weights
        ownership_score = (raw_score / total_weight) * 100

        # Step 14: Final ownership decision
        if ownership_score >= THRESHOLD_MATCHED:
            status = ValidationStatus.MATCHED.value
            confidence = "HIGH"
            confirmed = True
        elif ownership_score >= THRESHOLD_PARTIAL:
            status = ValidationStatus.PARTIAL_MATCH.value
            confidence = "MEDIUM"
            confirmed = False
            manual_review_reasons.append("Partial match requires review")
        else:
            status = ValidationStatus.UNMATCHED.value
            confidence = "LOW"
            confirmed = False

        requires_review = len(manual_review_reasons) > 0

        duration_ms = int((time.time() - start_time) * 1000)

        reasoning = (
            f"Ownership score: {ownership_score:.1f}/100 "
            f"(Name: {name_score_normalized * 100:.1f})"
        )

        logger.info(
            "validation_complete",
            status=status,
            ownership_score=f"{ownership_score:.1f}",
            confidence=confidence,
            ownership_confirmed=confirmed,
            name_score=f"{name_score_normalized * 100:.1f}" if name_result else "N/A",
            dob_matched=dob_result.matched if dob_result else "N/A",
            gender_matched=gender_result.matched if gender_result else "N/A",
            multi_person=multi_person,
            requires_review=requires_review,
            duration_ms=duration_ms,
        )

        return OwnershipValidationResult(
            validation_status=status,
            ownership_score=ownership_score,
            confidence=confidence,
            name_match_score=name_result.score if name_result else None,
            name_match_level=name_result.level.value if name_result else None,
            name_matched_tokens=int(name_result.matched_tokens) if name_result else 0,
            name_total_tokens=name_result.total_tokens if name_result else 0,
            dob_match=dob_result.matched if dob_result else None,
            dob_partial=dob_result.partial if dob_result else None,
            gender_match=gender_result.matched if gender_result else None,
            multi_person_detected=multi_person,
            ownership_confirmed=confirmed,
            id_number_match=None,
            reasoning=reasoning,
            mismatches=mismatches,
            requires_manual_review=requires_review,
            manual_review_reasons=manual_review_reasons,
            processing_duration_ms=duration_ms,
        )
