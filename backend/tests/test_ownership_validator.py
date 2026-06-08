"""Tests for app.services.validation.ownership module."""

import pytest
from app.services.validation.ownership import OwnershipValidator, OwnershipValidationResult
from app.models.enums import ValidationStatus


class TestOwnershipValidator:
    def setup_method(self):
        self.validator = OwnershipValidator()

    def test_matched_high_confidence(self):
        result = self.validator.validate(
            candidate_name="Priya Sharma",
            candidate_dob="14/03/1992",
            candidate_gender="Female",
            extracted_name="Priya Sharma",
            extracted_dob="14/03/1992",
            extracted_gender="Female",
            ocr_text="Name: Priya Sharma DOB: 14/03/1992 Gender: Female PAN: BSPPS1234K",
            document_type="pan_card",
            ocr_confidence=0.95,
        )
        assert result.validation_status == ValidationStatus.MATCHED.value
        assert result.ownership_score >= 85
        assert result.confidence == "HIGH"
        assert result.ownership_confirmed is True

    def test_unmatched_different_names(self):
        result = self.validator.validate(
            candidate_name="Priya Sharma",
            candidate_dob=None,
            candidate_gender=None,
            extracted_name="Vikram Patel",
            extracted_dob=None,
            extracted_gender=None,
            ocr_text="Name: Vikram Patel PAN: ABCDE1234F",
            document_type="pan_card",
            ocr_confidence=0.9,
        )
        assert result.validation_status == ValidationStatus.UNMATCHED.value
        assert result.ownership_score < 60
        assert result.ownership_confirmed is False

    def test_not_applicable_no_text(self):
        result = self.validator.validate(
            candidate_name="Priya Sharma",
            candidate_dob=None,
            candidate_gender=None,
            extracted_name=None,
            extracted_dob=None,
            extracted_gender=None,
            ocr_text="",
            document_type="pan_card",
        )
        assert result.validation_status == ValidationStatus.NOT_APPLICABLE.value

    def test_not_applicable_insufficient_text(self):
        result = self.validator.validate(
            candidate_name="Priya Sharma",
            candidate_dob=None,
            candidate_gender=None,
            extracted_name=None,
            extracted_dob=None,
            extracted_gender=None,
            ocr_text="hi",
            document_type="unknown",
        )
        assert result.validation_status == ValidationStatus.NOT_APPLICABLE.value

    def test_partial_match(self):
        result = self.validator.validate(
            candidate_name="Rahul Kumar Singh",
            candidate_dob=None,
            candidate_gender=None,
            extracted_name="Rahul Singh",
            extracted_dob=None,
            extracted_gender=None,
            ocr_text="Name: Rahul Singh some other text here in document",
            document_type="aadhaar_card",
            ocr_confidence=0.8,
        )
        # Should be partial or matched depending on score
        assert result.validation_status in (ValidationStatus.PARTIAL_MATCH.value, ValidationStatus.MATCHED.value)

    def test_ocr_fallback_when_no_extracted_name(self):
        result = self.validator.validate(
            candidate_name="Priya Sharma",
            candidate_dob=None,
            candidate_gender=None,
            extracted_name=None,
            extracted_dob=None,
            extracted_gender=None,
            ocr_text="Name: Priya Sharma DOB: 14/03/1992 this is a valid document text",
            document_type="pan_card",
            ocr_confidence=0.9,
        )
        # Should find name via OCR fallback
        assert result.validation_status in (ValidationStatus.MATCHED.value, ValidationStatus.PARTIAL_MATCH.value)
        assert result.ownership_score > 0

    def test_low_ocr_confidence_flags_review(self):
        result = self.validator.validate(
            candidate_name="Priya Sharma",
            candidate_dob=None,
            candidate_gender=None,
            extracted_name="Priya Sharma",
            extracted_dob=None,
            extracted_gender=None,
            ocr_text="Name: Priya Sharma this document has some text for validation",
            document_type="pan_card",
            ocr_confidence=0.2,
        )
        assert result.requires_manual_review is True
        assert "OCR confidence" in result.manual_review_reasons[0]

    def test_multi_person_document_flags_review(self):
        result = self.validator.validate(
            candidate_name="Priya Sharma",
            candidate_dob=None,
            candidate_gender=None,
            extracted_name="Priya Sharma",
            extracted_dob=None,
            extracted_gender=None,
            ocr_text="PAN: BSPPS1234K and PAN: XYZAB5678C Name: Priya Sharma text",
            document_type="pan_card",
            ocr_confidence=0.9,
        )
        assert result.multi_person_detected is True
        assert result.requires_manual_review is True

    def test_not_applicable_no_name_data(self):
        result = self.validator.validate(
            candidate_name="",
            candidate_dob=None,
            candidate_gender=None,
            extracted_name=None,
            extracted_dob=None,
            extracted_gender=None,
            ocr_text="Some OCR text without any name information in the document",
            document_type="unknown",
        )
        assert result.validation_status == ValidationStatus.NOT_APPLICABLE.value

    def test_processing_duration_tracked(self):
        result = self.validator.validate(
            candidate_name="Priya",
            candidate_dob=None,
            candidate_gender=None,
            extracted_name="Priya",
            extracted_dob=None,
            extracted_gender=None,
            ocr_text="Name: Priya some text for validation purposes in document",
            document_type="pan_card",
        )
        assert result.processing_duration_ms >= 0
