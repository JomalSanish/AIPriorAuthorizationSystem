"""
Document parsing and processing service.
Supports PDF, DOCX, TXT/MD, and Image files.
Integrates OCR for scanned pages and calculates SHA256 hashes.
"""

from __future__ import annotations

import hashlib
import io
import logging
from dataclasses import dataclass
from typing import Optional

import pymupdf as fitz
import docx

from app.services.ocr import ocr_service

logger = logging.getLogger("pa.services.document")


@dataclass
class PageResult:
    page_number: int
    text: str
    needs_ocr: bool
    image_bytes: Optional[bytes] = None


@dataclass
class DocumentResult:
    full_text: str
    pages: list[PageResult]
    ocr_status: str  # "not_needed", "completed", "failed"
    sha256_hash: str


class DocumentService:
    def parse_pdf(self, file_bytes: bytes) -> list[PageResult]:
        """
        Extract text and rasterize pages needing OCR from PDF.
        """
        results = []
        doc = fitz.open(stream=file_bytes, filetype="pdf")

        for i in range(len(doc)):
            page = doc[i]
            text = page.get_text().strip()

            needs_ocr = False
            image_bytes = None

            # If empty or almost empty, flag for OCR and rasterize
            if len(text) < 10:
                needs_ocr = True
                # Rasterize at 300 DPI
                zoom = 300 / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                image_bytes = pix.tobytes("png")

            results.append(
                PageResult(
                    page_number=i + 1,
                    text=text,
                    needs_ocr=needs_ocr,
                    image_bytes=image_bytes,
                )
            )

        return results

    def parse_docx(self, file_bytes: bytes) -> str:
        """
        Extract text from DOCX file.
        """
        doc = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    def parse_text(self, file_bytes: bytes, encoding: str = "utf-8") -> str:
        """
        Extract text from TXT or Markdown file.
        """
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            # Simple fallback
            return file_bytes.decode("latin-1", errors="replace")

    async def process_document(
        self, file_bytes: bytes, filename: str, file_type: str
    ) -> DocumentResult:
        """
        Unified entrypoint: parse based on file_type, run OCR if needed, hash file.
        """
        # Calculate SHA256
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()

        pages: list[PageResult] = []
        full_text = ""
        ocr_status = "not_needed"

        mime = file_type.lower()
        if "pdf" in mime:
            pages = self.parse_pdf(file_bytes)

            # Check if any page needs OCR
            if any(p.needs_ocr for p in pages):
                ocr_status = "completed"
                try:
                    # Run OCR
                    ocr_texts = await ocr_service.ocr_pdf_pages(pages)
                    for idx, p in enumerate(pages):
                        if p.needs_ocr:
                            p.text = ocr_texts[idx]
                except Exception as e:
                    logger.error(f"OCR failed for {filename}: {e}")
                    ocr_status = "failed"

            full_text = "\n\n".join(p.text for p in pages if p.text)

        elif "wordprocessingml.document" in mime or "docx" in mime:
            full_text = self.parse_docx(file_bytes)
            pages.append(PageResult(1, full_text, False))

        elif mime.startswith("text/") or mime in ["md", "txt"]:
            full_text = self.parse_text(file_bytes)
            pages.append(PageResult(1, full_text, False))

        elif mime.startswith("image/"):
            # Image direct parsing
            pages.append(PageResult(1, "", True, file_bytes))
            try:
                ocr_text = await ocr_service.ocr_image(file_bytes)
                pages[0].text = ocr_text
                full_text = ocr_text
                ocr_status = "completed"
            except Exception as e:
                logger.error(f"OCR failed for image {filename}: {e}")
                ocr_status = "failed"

        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        # Post-validation (FR-013a)
        if len(full_text.strip()) == 0:
            logger.warning(f"No text extracted from document {filename}")
            if ocr_status == "not_needed":
                # If we thought we didn't need OCR but still got nothing, flag as failed
                ocr_status = "failed"

        return DocumentResult(
            full_text=full_text,
            pages=pages,
            ocr_status=ocr_status,
            sha256_hash=sha256_hash,
        )


document_service = DocumentService()
