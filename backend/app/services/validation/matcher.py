import re
from typing import Optional
from dataclasses import dataclass
from enum import Enum

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler

from app.core.logging import get_logger

logger = get_logger("validation.matcher")


class MatchLevel(str, Enum):
    EXACT = "exact"
    STRONG = "strong"
    PARTIAL = "partial"
    WEAK = "weak"
    NONE = "none"


@dataclass
class NameMatchResult:
    score: float
    level: MatchLevel
    matched_tokens: int
    total_tokens: int
    details: str = ""


@dataclass
class DOBMatchResult:
    matched: bool
    partial: bool  # year-only match
    details: str = ""

    @property
    def score(self) -> float:
        if self.matched:
            return 1.0
        if self.partial:
            return 0.5
        return 0.0


@dataclass
class GenderMatchResult:
    matched: bool
    candidate_gender: str
    extracted_gender: str
    details: str = ""

    @property
    def score(self) -> float:
        return 1.0 if self.matched else 0.0


# OCR common character confusions
OCR_SUBSTITUTIONS = {
    "0": "o",
    "o": "0",
    "1": "l",
    "l": "1",
    "i": "l",
    "5": "s",
    "s": "5",
    "8": "b",
    "b": "8",
}

OCR_DIGRAPH_REPLACEMENTS = [
    ("rn", "m"),
    ("m", "rn"),
    ("cl", "d"),
    ("d", "cl"),
    ("vv", "w"),
    ("w", "vv"),
]


class NameMatcher:
    """Sequence-independent name matching with OCR error tolerance."""

    # Thresholds per spec
    THRESHOLD_EXACT = 90
    THRESHOLD_PARTIAL = 75

    # Common Indian name prefixes/suffixes to strip
    PREFIXES = {"mr", "mrs", "ms", "dr", "shri", "smt", "kumari", "kumar", "sri", "late"}
    SUFFIXES = {"ji", "sahab", "sir", "madam", "devi"}

    def match(self, candidate_name: str, ocr_text: str) -> NameMatchResult:
        if not candidate_name or not ocr_text:
            return NameMatchResult(score=0.0, level=MatchLevel.NONE, matched_tokens=0, total_tokens=0, details="Empty input")

        # Step 6: Normalize candidate name
        norm_candidate = self._normalize_name(candidate_name)
        # Step 7: Split into tokens
        candidate_tokens = self._split_tokens(norm_candidate)

        if not candidate_tokens:
            return NameMatchResult(score=0.0, level=MatchLevel.NONE, matched_tokens=0, total_tokens=0, details="No candidate tokens")

        # Step 8: Normalize OCR text for name extraction
        norm_ocr = self._normalize_name(ocr_text)
        ocr_tokens = self._split_tokens(norm_ocr)

        if not ocr_tokens:
            return NameMatchResult(score=0.0, level=MatchLevel.NONE, matched_tokens=0, total_tokens=0, details="No OCR tokens")

        # Step 9: Sequence-independent token matching
        matched_count, token_details = self._match_tokens(candidate_tokens, ocr_tokens)
        total_tokens = len(candidate_tokens)
        token_ratio = (matched_count / total_tokens) * 100 if total_tokens > 0 else 0

        # Also compute full-string fuzzy scores
        full_jaro = JaroWinkler.similarity(norm_candidate, norm_ocr) * 100
        full_ratio = fuzz.token_sort_ratio(norm_candidate, norm_ocr)

        # Take best score from token-based and full-string approaches
        best_score = max(token_ratio, full_jaro, full_ratio)

        # Determine match level
        if best_score >= self.THRESHOLD_EXACT:
            level = MatchLevel.EXACT if best_score >= 95 else MatchLevel.STRONG
        elif best_score >= self.THRESHOLD_PARTIAL:
            level = MatchLevel.PARTIAL
        elif best_score >= 60:
            level = MatchLevel.WEAK
        else:
            level = MatchLevel.NONE

        details = f"tokens={matched_count}/{total_tokens}, jaro={full_jaro:.1f}, ratio={full_ratio:.1f}"
        logger.debug("name_match_detail", candidate=norm_candidate, ocr=norm_ocr[:50],
                     score=f"{best_score:.1f}", level=level.value, details=details)

        return NameMatchResult(
            score=best_score,
            level=level,
            matched_tokens=matched_count,
            total_tokens=total_tokens,
            details=details,
        )

    def _normalize_name(self, name: str) -> str:
        """Step 6 & 8: Normalize name text."""
        name = name.lower().strip()
        # Remove special characters except spaces
        name = re.sub(r"[^a-z\s]", "", name)
        # Remove extra spaces
        name = re.sub(r"\s+", " ", name).strip()
        # Remove prefixes/suffixes
        tokens = name.split()
        tokens = [t for t in tokens if t not in self.PREFIXES and t not in self.SUFFIXES]
        return " ".join(tokens)

    def _split_tokens(self, name: str) -> list[str]:
        """Step 7: Split into meaningful tokens."""
        tokens = [t for t in name.split() if len(t) > 0]
        return tokens

    def _match_tokens(self, candidate_tokens: list[str], ocr_tokens: list[str]) -> tuple[float, list[str]]:
        """Step 9: Sequence-independent token matching with fuzzy + OCR error tolerance."""
        matched = 0.0
        details = []
        used_ocr_indices = set()

        for c_token in candidate_tokens:
            best_match_score = 0.0
            best_match_idx = -1

            for idx, o_token in enumerate(ocr_tokens):
                if idx in used_ocr_indices:
                    continue

                # Exact match
                if c_token == o_token:
                    best_match_score = 100.0
                    best_match_idx = idx
                    break

                # Fuzzy match (Jaro-Winkler)
                jw_score = JaroWinkler.similarity(c_token, o_token) * 100

                # Levenshtein ratio
                lev_score = fuzz.ratio(c_token, o_token)

                # OCR error variant match
                ocr_score = self._ocr_variant_score(c_token, o_token)

                token_best = max(jw_score, lev_score, ocr_score)
                if token_best > best_match_score:
                    best_match_score = token_best
                    best_match_idx = idx

            if best_match_score >= self.THRESHOLD_EXACT and best_match_idx >= 0:
                matched += 1
                used_ocr_indices.add(best_match_idx)
                details.append(f"{c_token}={ocr_tokens[best_match_idx]}@{best_match_score:.0f}")
            elif best_match_score >= self.THRESHOLD_PARTIAL and best_match_idx >= 0:
                matched += 0.5  # Partial credit for fuzzy match
                used_ocr_indices.add(best_match_idx)
                details.append(f"{c_token}~{ocr_tokens[best_match_idx]}@{best_match_score:.0f}")

        return matched, details

    def _ocr_variant_score(self, token1: str, token2: str) -> float:
        """Handle OCR confusion patterns (0↔O, I↔l, rn↔m)."""
        variants1 = self._generate_ocr_variants(token1)
        variants2 = self._generate_ocr_variants(token2)

        best = 0.0
        for v1 in variants1:
            for v2 in variants2:
                if v1 == v2:
                    return 95.0
                score = fuzz.ratio(v1, v2)
                if score > best:
                    best = score
        return best

    def _generate_ocr_variants(self, token: str) -> list[str]:
        """Generate OCR error variants of a token."""
        variants = [token]
        for old, new in OCR_DIGRAPH_REPLACEMENTS:
            if old in token:
                variants.append(token.replace(old, new, 1))
        for i, ch in enumerate(token):
            if ch in OCR_SUBSTITUTIONS:
                variant = token[:i] + OCR_SUBSTITUTIONS[ch] + token[i + 1:]
                variants.append(variant)
        return variants


class DOBMatcher:
    """Date of birth matching with format flexibility and partial (year-only) support."""

    def match(self, candidate_dob: str, ocr_text: str) -> DOBMatchResult:
        if not candidate_dob or not ocr_text:
            return DOBMatchResult(matched=False, partial=False, details="Missing input")

        candidate_parts = self._parse_date(candidate_dob)
        if not candidate_parts:
            return DOBMatchResult(matched=False, partial=False, details=f"Cannot parse candidate DOB: {candidate_dob}")

        c_day, c_month, c_year = candidate_parts

        # Extract all dates from OCR text
        ocr_dates = self._extract_dates(ocr_text)

        if not ocr_dates:
            # Fallback: check if year string exists in text
            if str(c_year) in ocr_text:
                return DOBMatchResult(matched=False, partial=True, details=f"Year found in text: {c_year}")
            return DOBMatchResult(matched=False, partial=False, details="No dates found in OCR text")

        # Check for exact match
        for o_day, o_month, o_year in ocr_dates:
            if o_day and o_month and o_year:
                if c_day == o_day and c_month == o_month and c_year == o_year:
                    return DOBMatchResult(matched=True, partial=False, details="Exact DOB match")

        # Check for year-only match (partial)
        for o_day, o_month, o_year in ocr_dates:
            if o_year == c_year:
                if o_day is None and o_month is None:
                    return DOBMatchResult(matched=False, partial=True, details=f"Year-only match: {c_year}")

        # Year found in text at all
        if str(c_year) in ocr_text:
            return DOBMatchResult(matched=False, partial=True, details=f"Year found in text: {c_year}")

        return DOBMatchResult(matched=False, partial=False, details="No DOB match found")

    def _parse_date(self, date_str: str) -> Optional[tuple[int, int, int]]:
        """Parse a date string into (day, month, year)."""
        date_str = date_str.strip()

        # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
        m = re.match(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", date_str)
        if m:
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= day <= 31 and 1 <= month <= 12:
                return (day, month, year)

        # YYYY-MM-DD
        m = re.match(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", date_str)
        if m:
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= day <= 31 and 1 <= month <= 12:
                return (day, month, year)

        # Digits only: DDMMYYYY or YYYYMMDD
        digits = re.sub(r"[^0-9]", "", date_str)
        if len(digits) == 8:
            if int(digits[:4]) > 1900:
                return (int(digits[6:8]), int(digits[4:6]), int(digits[:4]))
            else:
                return (int(digits[:2]), int(digits[2:4]), int(digits[4:8]))

        return None

    def _extract_dates(self, text: str) -> list[tuple[Optional[int], Optional[int], Optional[int]]]:
        """Extract all date-like patterns from OCR text."""
        dates = []

        # Full dates: DD/MM/YYYY or DD-MM-YYYY
        for m in re.finditer(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", text):
            day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                dates.append((day, month, year))

        # YYYY-MM-DD
        for m in re.finditer(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", text):
            year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100:
                dates.append((day, month, year))

        # Standalone year
        for m in re.finditer(r"\b(19\d{2}|20\d{2})\b", text):
            year = int(m.group(1))
            dates.append((None, None, year))

        return dates


class GenderMatcher:
    """Gender validation from OCR text."""

    MALE_KEYWORDS = {"male", "m", "पुरुष", "purusha"}
    FEMALE_KEYWORDS = {"female", "f", "महिला", "stri", "स्त्री"}
    TRANSGENDER_KEYWORDS = {"transgender", "t", "other"}

    def match(self, candidate_gender: str, ocr_text: str) -> GenderMatchResult:
        if not candidate_gender or not ocr_text:
            return GenderMatchResult(matched=False, candidate_gender=candidate_gender or "", extracted_gender="", details="Missing input")

        norm_candidate = self._normalize_gender(candidate_gender)
        if not norm_candidate:
            return GenderMatchResult(matched=False, candidate_gender=candidate_gender, extracted_gender="", details="Cannot parse candidate gender")

        extracted = self._extract_gender(ocr_text)
        if not extracted:
            return GenderMatchResult(matched=False, candidate_gender=norm_candidate, extracted_gender="", details="No gender found in OCR")

        matched = norm_candidate == extracted
        return GenderMatchResult(
            matched=matched,
            candidate_gender=norm_candidate,
            extracted_gender=extracted,
            details=f"{'Match' if matched else 'Mismatch'}: candidate={norm_candidate}, ocr={extracted}",
        )

    def _normalize_gender(self, gender: str) -> Optional[str]:
        """Normalize gender to M/F/T."""
        g = gender.lower().strip()
        if g in self.MALE_KEYWORDS or g.startswith("mal"):
            return "M"
        if g in self.FEMALE_KEYWORDS or g.startswith("fem"):
            return "F"
        if g in self.TRANSGENDER_KEYWORDS or g.startswith("trans"):
            return "T"
        return None

    def _extract_gender(self, text: str) -> Optional[str]:
        """Extract gender keyword from OCR text."""
        text_lower = text.lower()

        # Look for explicit gender labels (common in Indian documents)
        gender_patterns = [
            r"\b(?:sex|gender|लिंग)\s*[:\-]?\s*(male|female|m|f|transgender|पुरुष|महिला)\b",
            r"\b(male|female)\b",
        ]

        for pattern in gender_patterns:
            m = re.search(pattern, text_lower)
            if m:
                found = m.group(1).strip()
                if found in self.MALE_KEYWORDS or found.startswith("mal"):
                    return "M"
                if found in self.FEMALE_KEYWORDS or found.startswith("fem"):
                    return "F"
                if found in self.TRANSGENDER_KEYWORDS:
                    return "T"

        # Check for standalone M/F near gender context
        m = re.search(r"\b(?:sex|gender)\s*[:\-]?\s*([mf])\b", text_lower)
        if m:
            return m.group(1).upper()

        return None


class ConflictDetector:
    """Detect multiple persons/identities in a single document."""

    def detect(self, ocr_text: str, extracted_name: Optional[str] = None) -> dict:
        """Check for multi-person indicators."""
        conflicts = {
            "multi_person": False,
            "multiple_names": False,
            "multiple_dobs": False,
            "multiple_ids": False,
            "details": [],
        }

        if not ocr_text:
            return conflicts

        # Count Aadhaar patterns (12-digit)
        aadhaar_patterns = re.findall(r"\b\d{4}\s?\d{4}\s?\d{4}\b", ocr_text)
        if len(aadhaar_patterns) > 1:
            conflicts["multiple_ids"] = True
            conflicts["details"].append(f"Multiple Aadhaar numbers found: {len(aadhaar_patterns)}")

        # Count PAN patterns
        pan_patterns = re.findall(r"\b[A-Z]{5}\d{4}[A-Z]\b", ocr_text.upper())
        if len(pan_patterns) > 1:
            conflicts["multiple_ids"] = True
            conflicts["details"].append(f"Multiple PAN numbers found: {len(pan_patterns)}")

        # Count DOB patterns
        dob_patterns = re.findall(r"\d{1,2}[/\-]\d{1,2}[/\-]\d{4}", ocr_text)
        unique_dobs = set(dob_patterns)
        if len(unique_dobs) > 1:
            conflicts["multiple_dobs"] = True
            conflicts["details"].append(f"Multiple DOBs found: {list(unique_dobs)}")

        # Multiple name labels indicating multi-person
        name_labels = re.findall(r"\b(?:name|नाम)\s*[:\-]", ocr_text.lower())
        if len(name_labels) > 2:
            conflicts["multiple_names"] = True
            conflicts["details"].append(f"Multiple name labels found: {len(name_labels)}")

        conflicts["multi_person"] = conflicts["multiple_ids"] or (
            conflicts["multiple_dobs"] and conflicts["multiple_names"]
        )

        return conflicts


class IDNumberMatcher:
    """ID number matching (PAN, Aadhaar last 4, etc.)."""

    def match_pan(self, candidate_pan: str, extracted_pan: str) -> bool:
        if not candidate_pan or not extracted_pan:
            return False
        return self._normalize_id(candidate_pan) == self._normalize_id(extracted_pan)

    def match_aadhaar_last_four(self, candidate_last_four: str, extracted_aadhaar: str) -> bool:
        if not candidate_last_four or not extracted_aadhaar:
            return False
        c = re.sub(r"[^0-9]", "", candidate_last_four)
        e = re.sub(r"[^0-9]", "", extracted_aadhaar)
        return c[-4:] == e[-4:] if len(c) >= 4 and len(e) >= 4 else False

    def _normalize_id(self, id_str: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", id_str.upper().strip())
