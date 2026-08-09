"""
OCR and Image Preprocessing Service.
Uses OpenCV for preprocessing and EasyOCR for text extraction.
Integrates with GpuGuard to prevent VRAM contention.
"""

from __future__ import annotations

import logging
from typing import Optional, Any

import cv2
import numpy as np
import easyocr

from app.core.gpu_guard import gpu_guard, GpuPriority
from app.config import get_settings

logger = logging.getLogger("pa.services.ocr")


class OcrService:
    def __init__(self):
        self._settings = get_settings()
        self._reader: Optional[easyocr.Reader] = None
        self._fallback_reader: Optional[easyocr.Reader] = None

    def _get_reader(self, use_gpu: bool = True) -> easyocr.Reader:
        """Lazy-initialize the EasyOCR reader."""
        if use_gpu:
            if self._reader is None:
                logger.info("Initializing EasyOCR Reader (GPU)")
                self._reader = easyocr.Reader(["en"], gpu=True)
            return self._reader
        else:
            if self._fallback_reader is None:
                logger.info("Initializing EasyOCR Reader (CPU fallback)")
                # FR-046a, FR-047: degraded mode on CPU
                self._fallback_reader = easyocr.Reader(["en"], gpu=False)
            return self._fallback_reader

    def preprocess_image(self, image_bytes: bytes) -> np.ndarray:
        """
        Preprocess image for OCR using OpenCV.
        Pipeline: Grayscale -> Deskew -> Denoise -> CLAHE -> Adaptive Threshold.
        """
        # 1. Decode
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Failed to decode image bytes")

        # 2. Grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 3. Deskew
        # Find all non-zero points
        coords = np.column_stack(np.where(gray > 0))
        if len(coords) > 0:
            angle = cv2.minAreaRect(coords)[-1]
            # OpenCV minAreaRect returns angle in range [-90, 0)
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle

            if abs(angle) > 0.5:
                (h, w) = gray.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                gray = cv2.warpAffine(
                    gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
                )

        # 4. Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=30)

        # 5. Contrast normalization (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrasted = clahe.apply(denoised)

        # 6. Adaptive binarization/thresholding
        binarized = cv2.adaptiveThreshold(
            contrasted, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        return binarized

    async def ocr_image(self, image_bytes: bytes) -> str:
        """
        Preprocess image and extract text via EasyOCR, with GPU guard contention management.
        """
        try:
            processed_img = self.preprocess_image(image_bytes)
        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return ""

        # Acquire GPU guard
        timeout = self._settings.OCR_CPU_FALLBACK_TIMEOUT_SECONDS
        acquired = await gpu_guard.acquire(GpuPriority.OCR, timeout)

        try:
            reader = self._get_reader(use_gpu=acquired)
            # Extract text
            results = reader.readtext(processed_img, detail=0, paragraph=True)
            text = "\n".join(results)
            return text
        except Exception as e:
            logger.error(f"OCR text extraction failed: {e}")
            return ""
        finally:
            if acquired:
                gpu_guard.release()

    async def ocr_pdf_pages(self, pages: list[Any]) -> list[str]:
        """
        Given a list of PageResult objects, runs OCR on those flagged `needs_ocr`.
        """
        results = []
        for p in pages:
            if getattr(p, "needs_ocr", False) and getattr(p, "image_bytes", None):
                text = await self.ocr_image(p.image_bytes)
                results.append(text)
            else:
                results.append(getattr(p, "text", ""))
        return results


ocr_service = OcrService()
