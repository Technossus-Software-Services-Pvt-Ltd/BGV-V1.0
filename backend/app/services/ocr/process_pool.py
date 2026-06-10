"""Process pool OCR worker for true CPU parallelism.

PaddleOCR is CPU-bound. Python's GIL limits ThreadPoolExecutor to one
CPU core at a time. This module uses ProcessPoolExecutor so each worker
process runs OCR on its own core with its own PaddleOCR model instance.
"""

import os
import time
import asyncio
import numpy as np
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("ocr.process_pool")

# Module-level pool — initialized lazily via startup()
_process_pool: Optional[ProcessPoolExecutor] = None


def _ocr_worker_init():
    """Initializer run once per worker process. Sets environment and loads PaddleOCR."""
    os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    os.environ["FLAGS_use_mkldnn"] = "0"
    os.environ["FLAGS_use_mkl"] = "0"
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"


def _run_ocr_in_process(image_array: np.ndarray) -> dict:
    """Run OCR inside a worker process. Returns a serializable dict."""
    # Import here because each process needs its own PaddleOCR instance
    from paddleocr import PaddleOCR

    # Use a process-local global to avoid re-loading the model on every call
    global _process_local_ocr
    if "_process_local_ocr" not in globals() or _process_local_ocr is None:
        _process_local_ocr = PaddleOCR(
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

    start_time = time.time()
    min_confidence = 0.3

    try:
        results = _process_local_ocr.ocr(image_array, cls=True)

        if not results or not results[0]:
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "text": "",
                "confidence": 0.0,
                "word_count": 0,
                "raw_output": [],
                "processing_duration_ms": duration_ms,
                "language_detected": None,
                "orientation_angle": 0.0,
                "error": None,
            }

        extracted_lines = []
        confidences = []
        raw_data = []

        for line in results[0]:
            if line and len(line) >= 2:
                bbox = line[0]
                text_info = line[1]
                text = text_info[0]
                confidence = text_info[1]

                if confidence >= min_confidence:
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

        return {
            "text": full_text,
            "confidence": avg_confidence,
            "word_count": word_count,
            "raw_output": raw_data[:50],  # Limit stored raw data
            "processing_duration_ms": duration_ms,
            "language_detected": "en",
            "orientation_angle": 0.0,
            "error": None,
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "text": "",
            "confidence": 0.0,
            "word_count": 0,
            "raw_output": [],
            "processing_duration_ms": duration_ms,
            "language_detected": None,
            "orientation_angle": 0.0,
            "error": str(e),
        }


# Process-local OCR instance (set inside worker processes)
_process_local_ocr = None


class OCRProcessPool:
    """Manages a ProcessPoolExecutor for CPU-parallel OCR."""

    def __init__(self):
        self._pool: Optional[ProcessPoolExecutor] = None

    @property
    def is_running(self) -> bool:
        return self._pool is not None

    def startup(self) -> None:
        """Initialize the process pool. Call during app lifespan startup."""
        if self._pool is not None:
            return

        workers = settings.ocr_process_workers
        logger.info("ocr_process_pool_starting", workers=workers)

        self._pool = ProcessPoolExecutor(
            max_workers=workers,
            initializer=_ocr_worker_init,
        )
        logger.info("ocr_process_pool_started", workers=workers)

    def shutdown(self) -> None:
        """Shutdown the process pool. Call during app lifespan shutdown."""
        if self._pool is None:
            return
        logger.info("ocr_process_pool_shutting_down")
        self._pool.shutdown(wait=True, cancel_futures=True)
        self._pool = None
        logger.info("ocr_process_pool_stopped")

    async def process_async(self, image_array: np.ndarray) -> dict:
        """Submit OCR work to the process pool and await the result.

        Returns a dict with keys: text, confidence, word_count, raw_output,
        processing_duration_ms, language_detected, orientation_angle, error.
        """
        if self._pool is None:
            raise RuntimeError("OCR process pool not started. Call startup() first.")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            self._pool, _run_ocr_in_process, image_array
        )
        return result


# Module-level singleton
ocr_process_pool = OCRProcessPool()
