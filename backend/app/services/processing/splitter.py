from typing import List, Dict
from dataclasses import dataclass, field
from pathlib import Path

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

    def reconstruct_pdf_from_pages(
        self, page_paths: List[Path], output_path: Path
    ) -> Path:
        """Reconstruct a PDF from page image files.

        Args:
            page_paths: List of paths to page image files (PNG/JPEG).
            output_path: Path where the reconstructed PDF should be saved.

        Returns:
            The output_path of the created PDF.
        """
        import fitz  # PyMuPDF

        doc = fitz.open()
        try:
            for page_path in page_paths:
                img = fitz.open(str(page_path))
                # Get image dimensions for page size
                rect = img[0].rect
                pdf_page = doc.new_page(width=rect.width, height=rect.height)
                pdf_page.insert_image(rect, filename=str(page_path))
                img.close()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output_path))
            logger.info(
                "pdf_reconstructed",
                pages=len(page_paths),
                output=str(output_path),
            )
        finally:
            doc.close()

        return output_path
