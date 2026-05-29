import uuid
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ocr.preprocessor import DocumentPreprocessor

logger = get_logger("processing.normalizer")


class DocumentNormalizer:
    """Normalizes uploaded documents: extracts pages, handles formats."""

    def __init__(self):
        self.preprocessor = DocumentPreprocessor()

    def get_document_dir(self, correlation_id: str, document_id: str) -> Path:
        doc_dir = settings.upload_path / correlation_id / document_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir

    def get_pages_dir(self, doc_dir: Path) -> Path:
        pages_dir = doc_dir / "pages"
        pages_dir.mkdir(parents=True, exist_ok=True)
        return pages_dir

    def extract_pages(self, file_path: Path, doc_dir: Path, mime_type: str) -> list[Path]:
        pages_dir = self.get_pages_dir(doc_dir)

        if mime_type == "application/pdf":
            return self.preprocessor.extract_pages_from_pdf(file_path, pages_dir)
        else:
            # Single image - copy as page 1
            import shutil
            page_path = pages_dir / f"page_0001{file_path.suffix}"
            shutil.copy2(str(file_path), str(page_path))
            return [page_path]

    def count_pdf_pages(self, file_path: Path) -> int:
        import fitz
        doc = fitz.open(str(file_path))
        count = len(doc)
        doc.close()
        return count
