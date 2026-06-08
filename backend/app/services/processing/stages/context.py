"""Pipeline context: carries state between pipeline stages."""

from dataclasses import dataclass, field
from typing import Optional, List

from app.models.document import Document, DocumentPage
from app.models.ocr_result import OCRResult
from app.models.classification import AIClassification
from app.services.processing.splitter import PageClassification


@dataclass
class PipelineContext:
    """Mutable context object passed through pipeline stages.

    Each stage reads from and writes to this context, enabling
    loose coupling between stages without changing the data flow.
    """

    # Input
    document_id: str
    document: Optional[Document] = None
    correlation_id: str = ""

    # Normalization outputs
    pages: List[DocumentPage] = field(default_factory=list)

    # OCR outputs
    ocr_results: List[OCRResult] = field(default_factory=list)
    all_ocr_text: List[str] = field(default_factory=list)
    all_confidences: List[float] = field(default_factory=list)
    combined_text: str = ""
    avg_confidence: float = 0.0

    # Classification outputs
    page_classifications: List[PageClassification] = field(default_factory=list)
    full_classification: Optional[AIClassification] = None

    # Pipeline control
    should_stop: bool = False
    stop_reason: str = ""
