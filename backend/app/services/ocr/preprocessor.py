import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import fitz  # PyMuPDF

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("ocr.preprocessor")


class DocumentPreprocessor:
    """Handles document normalization: format conversion, rotation, deskew, denoise."""

    SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    TARGET_DPI = 300
    MAX_DIMENSION = settings.ocr_max_dimension

    def extract_pages_from_pdf(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        logger.info("pdf_extraction_start", pdf_path=str(pdf_path))
        page_paths = []
        doc = fitz.open(str(pdf_path))

        # Detect encrypted/password-protected PDFs
        if doc.is_encrypted:
            doc.close()
            raise ValueError(f"PDF is encrypted/password-protected and cannot be processed: {pdf_path.name}")

        total_pages = len(doc)
        max_pages = settings.max_pdf_pages
        pages_to_extract = min(total_pages, max_pages)

        if total_pages > max_pages:
            logger.warning(
                "pdf_page_limit_applied",
                pdf_path=str(pdf_path),
                total_pages=total_pages,
                max_pages=max_pages,
            )

        for page_num in range(pages_to_extract):
            page = doc[page_num]
            # Render at 300 DPI for OCR quality
            zoom = self.TARGET_DPI / 72
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix)

            # PDF bomb protection: reject pages with excessive pixel dimensions
            max_pixels = 10000
            if pixmap.width > max_pixels or pixmap.height > max_pixels:
                logger.warning(
                    "pdf_page_dimension_exceeded",
                    page_num=page_num + 1,
                    width=pixmap.width,
                    height=pixmap.height,
                    max_pixels=max_pixels,
                )
                raise ValueError(
                    f"PDF page {page_num + 1} exceeds maximum dimensions "
                    f"({pixmap.width}x{pixmap.height} > {max_pixels}x{max_pixels}). "
                    f"Possible decompression bomb."
                )

            output_path = output_dir / f"page_{page_num + 1:04d}.png"
            pixmap.save(str(output_path))
            page_paths.append(output_path)

        doc.close()
        logger.info("pdf_extraction_complete", page_count=len(page_paths), total_in_pdf=total_pages)
        return page_paths

    def normalize_image(self, image_path: Path) -> tuple[np.ndarray, dict]:
        logger.info("image_normalize_start", image_path=str(image_path))
        img = Image.open(str(image_path))
        metadata = {
            "original_width": img.width,
            "original_height": img.height,
            "original_mode": img.mode,
            "orientation_corrected": False,
            "deskewed": False,
            "denoised": False,
        }

        # Fix EXIF orientation
        img, was_rotated = self._fix_orientation(img)
        metadata["orientation_corrected"] = was_rotated

        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if too large (preserve aspect ratio)
        img = self._resize_if_needed(img)

        # Enhance for OCR
        img = self._enhance_for_ocr(img)
        metadata["denoised"] = True

        metadata["final_width"] = img.width
        metadata["final_height"] = img.height

        img_array = np.array(img)
        logger.info("image_normalize_complete", final_size=f"{img.width}x{img.height}", orientation_corrected=metadata["orientation_corrected"])
        return img_array, metadata

    def _fix_orientation(self, img: Image.Image) -> tuple[Image.Image, bool]:
        try:
            exif = img.getexif()
            if not exif:
                return img, False

            orientation_tag = 274  # EXIF orientation tag
            if orientation_tag not in exif:
                return img, False

            orientation = exif[orientation_tag]
            rotations = {
                3: 180,
                6: 270,
                8: 90,
            }

            if orientation in rotations:
                img = img.rotate(rotations[orientation], expand=True)
                return img, True

        except (AttributeError, KeyError):
            pass

        return img, False

    def _resize_if_needed(self, img: Image.Image) -> Image.Image:
        if img.width > self.MAX_DIMENSION or img.height > self.MAX_DIMENSION:
            ratio = min(self.MAX_DIMENSION / img.width, self.MAX_DIMENSION / img.height)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        return img

    def _enhance_for_ocr(self, img: Image.Image) -> Image.Image:
        # Sharpen slightly
        img = img.filter(ImageFilter.SHARPEN)

        # Increase contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.2)

        # Slight brightness adjustment
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(1.05)

        return img

    def is_blank_page(self, img_array: np.ndarray, threshold: float = 0.98) -> bool:
        if len(img_array.shape) == 3:
            gray = np.mean(img_array, axis=2)
        else:
            gray = img_array.astype(float)

        white_ratio = np.mean(gray > 240) 
        return white_ratio > threshold

    def enhance_aggressive(self, img_array: np.ndarray) -> np.ndarray:
        """Aggressive preprocessing for low-confidence OCR retry: binarize + high contrast."""
        img = Image.fromarray(img_array)

        # Convert to grayscale for Otsu-style binarization
        gray = ImageOps.grayscale(img)

        # Auto-contrast to maximize dynamic range
        gray = ImageOps.autocontrast(gray, cutoff=1)

        # Binarize using adaptive threshold (Otsu approximation via quantize)
        threshold = 128
        binary = gray.point(lambda p: 255 if p > threshold else 0, mode="1")

        # Convert back to RGB for PaddleOCR
        result = binary.convert("RGB")

        # Light sharpen
        result = result.filter(ImageFilter.SHARPEN)

        return np.array(result)
