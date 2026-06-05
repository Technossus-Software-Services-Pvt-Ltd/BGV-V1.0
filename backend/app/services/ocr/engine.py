import os
import time
import asyncio
import json
import threading
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

# Fix OpenMP duplicate library crash on Windows (PaddleOCR + NumPy both load libiomp5md.dll)
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
# Disable OneDNN/MKL-DNN to avoid fused_conv2d operator registry bug in PaddlePaddle 3.x
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_use_mkl"] = "0"
# Use pure-Python protobuf implementation for compatibility between paddlepaddle 2.x pb2 files and protobuf 4+
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger("ocr.engine")

# Thread-safe lazy-loaded PaddleOCR instance (singleton for memory efficiency)
_paddle_ocr_instance = None
_paddle_ocr_lock = threading.Lock()

# Dedicated thread pool for OCR to avoid starving the shared executor
_ocr_executor = ThreadPoolExecutor(
    max_workers=settings.max_concurrent_ocr,
    thread_name_prefix="ocr",
)


def _get_paddle_ocr():
    global _paddle_ocr_instance
    if _paddle_ocr_instance is None:
        with _paddle_ocr_lock:
            if _paddle_ocr_instance is None:  # Double-check locking
                from paddleocr import PaddleOCR
                _paddle_ocr_instance = PaddleOCR(
                    use_angle_cls=True,
                    lang="en",
                    use_gpu=False,
                    show_log=False,
                    enable_mkldnn=False,
                    ir_optim=False,
                    cpu_threads=2,
                    det_db_thresh=0.3,
                    det_db_box_thresh=0.5,
                    rec_batch_num=6,
                )
    return _paddle_ocr_instance


class OCREngineResult:
    def __init__(
        self,
        text: str,
        confidence: float,
        word_count: int,
        raw_output: list,
        processing_duration_ms: int,
        language_detected: Optional[str] = None,
        orientation_angle: float = 0.0,
        error: Optional[str] = None,
    ):
        self.text = text
        self.confidence = confidence
        self.word_count = word_count
        self.raw_output = raw_output
        self.processing_duration_ms = processing_duration_ms
        self.language_detected = language_detected
        self.orientation_angle = orientation_angle
        self.error = error

    @property
    def is_successful(self) -> bool:
        return self.error is None and len(self.text.strip()) > 0


class PaddleOCREngine:
    """PaddleOCR-based text extraction engine optimized for CPU."""

    MIN_CONFIDENCE_THRESHOLD = 0.3

    def _parse_ocr_results(self, results: list, start_time: float) -> OCREngineResult:
        """Parse raw PaddleOCR results into an OCREngineResult."""
        if not results or not results[0]:
            duration_ms = int((time.time() - start_time) * 1000)
            return OCREngineResult(
                text="",
                confidence=0.0,
                word_count=0,
                raw_output=[],
                processing_duration_ms=duration_ms,
            )

        extracted_lines = []
        confidences = []
        raw_data = []

        for line in results[0]:
            if line and len(line) >= 2:
                bbox = line[0]
                text_info = line[1]
                text = text_info[0]
                confidence = text_info[1]

                if confidence >= self.MIN_CONFIDENCE_THRESHOLD:
                    extracted_lines.append(text)
                    confidences.append(confidence)
                    raw_data.append({
                        "bbox": [[float(p[0]), float(p[1])] for p in bbox],
                        "text": text,
                        "confidence": float(confidence),
                    })

        full_text = "\n".join(extracted_lines)
        avg_confidence = float(np.mean(confidences)) if confidences else 0.0
        word_count = len(full_text.split()) if full_text else 0
        duration_ms = int((time.time() - start_time) * 1000)

        return OCREngineResult(
            text=full_text,
            confidence=avg_confidence,
            word_count=word_count,
            raw_output=raw_data,
            processing_duration_ms=duration_ms,
            language_detected="en",
        )

    def process(self, image_array: np.ndarray) -> OCREngineResult:
        start_time = time.time()
        logger.info("ocr_start", image_shape=str(image_array.shape))

        try:
            ocr = _get_paddle_ocr()
            results = ocr.ocr(image_array, cls=True)
            result = self._parse_ocr_results(results, start_time)

            logger.info(
                "ocr_complete",
                word_count=result.word_count,
                confidence=f"{result.confidence:.2f}",
                duration_ms=result.processing_duration_ms,
            )
            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("ocr_processing_failed", error=str(e), duration_ms=duration_ms)
            return OCREngineResult(
                text="",
                confidence=0.0,
                word_count=0,
                raw_output=[],
                processing_duration_ms=duration_ms,
                error=str(e),
            )

    def process_from_path(self, image_path: Path) -> OCREngineResult:
        start_time = time.time()

        try:
            ocr = _get_paddle_ocr()
            results = ocr.ocr(str(image_path), cls=True)
            return self._parse_ocr_results(results, start_time)

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error("ocr_processing_failed", error=str(e), path=str(image_path))
            return OCREngineResult(
                text="",
                confidence=0.0,
                word_count=0,
                raw_output=[],
                processing_duration_ms=duration_ms,
                error=str(e),
            )

    # Use the module-level dedicated OCR executor instead of a per-instance pool
    async def process_async(self, image_array: np.ndarray) -> OCREngineResult:
        """Run OCR in a dedicated thread pool to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_ocr_executor, self.process, image_array)

    async def process_from_path_async(self, image_path: Path) -> OCREngineResult:
        """Run path-based OCR in a dedicated thread pool to avoid blocking the event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_ocr_executor, self.process_from_path, image_path)
