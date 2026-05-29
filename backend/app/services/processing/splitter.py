from typing import List, Dict
from dataclasses import dataclass, field

from app.models.enums import DocumentType
from app.core.logging import get_logger

logger = get_logger("processing.splitter")


@dataclass
class PageClassification:
    page_number: int
    document_type: str
    confidence: float


@dataclass
class DocumentGroup:
    document_type: str
    pages: List[int]
    confidence: float


class DocumentSplitter:
    """Groups multi-page PDF pages by their classified document type."""

    MERGE_THRESHOLD = 0.7

    def group_pages_by_type(self, page_classifications: List[PageClassification]) -> List[DocumentGroup]:
        if not page_classifications:
            return []

        if len(page_classifications) == 1:
            pc = page_classifications[0]
            return [DocumentGroup(
                document_type=pc.document_type,
                pages=[pc.page_number],
                confidence=pc.confidence,
            )]

        # Group consecutive pages of the same type
        groups: List[DocumentGroup] = []
        current_type = page_classifications[0].document_type
        current_pages = [page_classifications[0].page_number]
        confidences = [page_classifications[0].confidence]

        for pc in page_classifications[1:]:
            if pc.document_type == current_type:
                current_pages.append(pc.page_number)
                confidences.append(pc.confidence)
            else:
                groups.append(DocumentGroup(
                    document_type=current_type,
                    pages=current_pages,
                    confidence=sum(confidences) / len(confidences),
                ))
                current_type = pc.document_type
                current_pages = [pc.page_number]
                confidences = [pc.confidence]

        # Don't forget the last group
        groups.append(DocumentGroup(
            document_type=current_type,
            pages=current_pages,
            confidence=sum(confidences) / len(confidences),
        ))

        return groups

    def detect_mixed_documents(self, groups: List[DocumentGroup]) -> bool:
        unique_types = {g.document_type for g in groups if g.document_type != DocumentType.UNKNOWN.value}
        return len(unique_types) > 1
