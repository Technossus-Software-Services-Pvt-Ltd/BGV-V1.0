from dataclasses import dataclass


@dataclass
class ConfidenceAssessment:
    overall_score: float
    is_reliable: bool
    low_confidence_regions: int
    recommendation: str


class OCRConfidenceEvaluator:
    """Evaluates OCR output quality and provides reliability assessment."""

    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.6
    LOW_CONFIDENCE_THRESHOLD = 0.4
    MIN_WORD_COUNT_FOR_DOCUMENT = 5

    def evaluate(self, confidence: float, word_count: int, text: str) -> ConfidenceAssessment:
        if word_count < self.MIN_WORD_COUNT_FOR_DOCUMENT:
            return ConfidenceAssessment(
                overall_score=confidence,
                is_reliable=False,
                low_confidence_regions=0,
                recommendation="Insufficient text extracted. Document may be blank, image-only, or severely degraded.",
            )

        if confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            return ConfidenceAssessment(
                overall_score=confidence,
                is_reliable=True,
                low_confidence_regions=0,
                recommendation="High confidence OCR. Text reliable for classification.",
            )

        if confidence >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            return ConfidenceAssessment(
                overall_score=confidence,
                is_reliable=True,
                low_confidence_regions=1,
                recommendation="Medium confidence. Some regions may have errors. Classification should proceed with caution.",
            )

        if confidence >= self.LOW_CONFIDENCE_THRESHOLD:
            return ConfidenceAssessment(
                overall_score=confidence,
                is_reliable=False,
                low_confidence_regions=3,
                recommendation="Low confidence OCR. Document quality is poor. Manual review recommended.",
            )

        return ConfidenceAssessment(
            overall_score=confidence,
            is_reliable=False,
            low_confidence_regions=5,
            recommendation="Very low confidence. OCR output unreliable. Document may need re-scan.",
        )
