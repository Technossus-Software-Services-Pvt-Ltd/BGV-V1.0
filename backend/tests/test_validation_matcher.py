"""Tests for app.services.validation.matcher module."""

import pytest
from app.services.validation.matcher import (
    NameMatcher, DOBMatcher, GenderMatcher, ConflictDetector, IDNumberMatcher,
    MatchLevel,
)


class TestNameMatcher:
    def setup_method(self):
        self.matcher = NameMatcher()

    def test_exact_match(self):
        result = self.matcher.match("Priya Sharma", "Priya Sharma")
        assert result.level in (MatchLevel.EXACT, MatchLevel.STRONG)
        assert result.score >= 90

    def test_case_insensitive_match(self):
        result = self.matcher.match("PRIYA SHARMA", "priya sharma")
        assert result.level in (MatchLevel.EXACT, MatchLevel.STRONG)

    def test_prefix_stripped(self):
        result = self.matcher.match("Mr Rahul Kumar", "Rahul Kumar")
        assert result.level in (MatchLevel.EXACT, MatchLevel.STRONG)

    def test_suffix_stripped(self):
        result = self.matcher.match("Rahul Ji", "Rahul")
        assert result.score >= 75

    def test_partial_match(self):
        result = self.matcher.match("Rahul Kumar Singh", "Rahul Kumar")
        assert result.level in (MatchLevel.PARTIAL, MatchLevel.STRONG, MatchLevel.WEAK)
        assert result.score >= 60

    def test_no_match(self):
        result = self.matcher.match("Priya Sharma", "Vikram Patel")
        assert result.level == MatchLevel.NONE
        assert result.score < 60

    def test_empty_candidate(self):
        result = self.matcher.match("", "Priya")
        assert result.level == MatchLevel.NONE
        assert result.score == 0

    def test_empty_ocr(self):
        result = self.matcher.match("Priya", "")
        assert result.level == MatchLevel.NONE

    def test_ocr_error_tolerance(self):
        # rn vs m confusion
        result = self.matcher.match("Sharma", "Sharrna")
        assert result.score >= 60

    def test_single_token_match(self):
        result = self.matcher.match("Priya", "Priya Sharma")
        assert result.score >= 75

    def test_token_reorder(self):
        result = self.matcher.match("Kumar Rahul", "Rahul Kumar")
        assert result.score >= 85

    def test_normalize_removes_special_chars(self):
        result = self.matcher._normalize_name("Priya@123 Sharma!")
        assert result == "priya sharma"


class TestDOBMatcher:
    def setup_method(self):
        self.matcher = DOBMatcher()

    def test_exact_match_dd_mm_yyyy(self):
        result = self.matcher.match("14/03/1992", "Date of Birth: 14/03/1992")
        assert result.matched is True

    def test_exact_match_yyyy_mm_dd(self):
        result = self.matcher.match("1992-03-14", "DOB: 14/03/1992")
        assert result.matched is True

    def test_year_only_match(self):
        result = self.matcher.match("14/03/1992", "Year: 1992")
        assert result.partial is True
        assert result.matched is False

    def test_no_match(self):
        result = self.matcher.match("14/03/1992", "No dates here at all")
        assert result.matched is False
        assert result.partial is False

    def test_empty_inputs(self):
        result = self.matcher.match("", "some text")
        assert result.matched is False

    def test_parse_various_formats(self):
        # DD-MM-YYYY
        result = self.matcher.match("14-03-1992", "14-03-1992 is the DOB")
        assert result.matched is True

    def test_multiple_dates_in_text(self):
        result = self.matcher.match("01/01/1990", "Issued: 15/06/2020. DOB: 01/01/1990")
        assert result.matched is True


class TestGenderMatcher:
    def setup_method(self):
        self.matcher = GenderMatcher()

    def test_male_match(self):
        result = self.matcher.match("Male", "Sex: Male")
        assert result.matched is True

    def test_female_match(self):
        result = self.matcher.match("Female", "Gender: Female")
        assert result.matched is True

    def test_mismatch(self):
        result = self.matcher.match("Male", "Sex: Female")
        assert result.matched is False

    def test_empty_candidate_gender(self):
        result = self.matcher.match("", "Gender: Male")
        assert result.matched is False

    def test_no_gender_in_text(self):
        result = self.matcher.match("Male", "No gender info here")
        assert result.matched is False

    def test_normalize_male_variants(self):
        assert self.matcher._normalize_gender("Male") == "M"
        assert self.matcher._normalize_gender("m") == "M"
        assert self.matcher._normalize_gender("MALE") == "M"

    def test_normalize_female_variants(self):
        assert self.matcher._normalize_gender("Female") == "F"
        assert self.matcher._normalize_gender("f") == "F"

    def test_normalize_unknown(self):
        assert self.matcher._normalize_gender("unknown") is None


class TestConflictDetector:
    def setup_method(self):
        self.detector = ConflictDetector()

    def test_no_conflict(self):
        result = self.detector.detect("Name: Priya Sharma. PAN: BSPPS1234K")
        assert result["multi_person"] is False

    def test_multiple_pan_detected(self):
        result = self.detector.detect("PAN: BSPPS1234K and also ABCDE1234F")
        assert result["multiple_ids"] is True
        assert result["multi_person"] is True

    def test_multiple_aadhaar_detected(self):
        result = self.detector.detect("Aadhaar: 1234 5678 9012 and 9876 5432 1098")
        assert result["multiple_ids"] is True

    def test_multiple_dobs_detected(self):
        text = "name: A\nname: B\nname: C\nDOB: 01/01/1990\nDOB: 15/06/1985"
        result = self.detector.detect(text)
        assert result["multiple_dobs"] is True

    def test_empty_text(self):
        result = self.detector.detect("")
        assert result["multi_person"] is False


class TestIDNumberMatcher:
    def setup_method(self):
        self.matcher = IDNumberMatcher()

    def test_pan_exact_match(self):
        assert self.matcher.match_pan("BSPPS1234K", "BSPPS1234K") is True

    def test_pan_case_insensitive(self):
        assert self.matcher.match_pan("bspps1234k", "BSPPS1234K") is True

    def test_pan_no_match(self):
        assert self.matcher.match_pan("BSPPS1234K", "ABCDE5678F") is False

    def test_pan_empty(self):
        assert self.matcher.match_pan("", "BSPPS1234K") is False

    def test_aadhaar_last_four_match(self):
        assert self.matcher.match_aadhaar_last_four("5678", "1234 5678 5678") is True

    def test_aadhaar_last_four_no_match(self):
        assert self.matcher.match_aadhaar_last_four("5678", "1234 5678 1234") is False

    def test_aadhaar_empty(self):
        assert self.matcher.match_aadhaar_last_four("", "1234567890") is False
