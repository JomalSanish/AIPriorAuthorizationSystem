# OCR Pipeline Specification

## Document Parsers (T019, T020, T021)
- **PDF**: Uses `PyMuPDF`. Rasterizes pages without text layer to 300 DPI images for OCR.
- **DOCX**: Uses `python-docx`.
- **TXT/MD**: Direct decode with utf-8 fallback.

## Image Preprocessing (T022)
- Sequential OpenCV CPU-only pipeline applied *before* OCR.
- Steps: Grayscale → Deskew → Denoise → Adaptive binarization → Contrast normalization (CLAHE).

## EasyOCR Integration (T023, T024, FR-046, FR-047)
- Processes images of PDF pages and uploaded images (JPEG, PNG, TIFF).
- **GPU Guard**: Acquires GPU lock with `OCR` (lowest) priority.
- **CPU Fallback**: If GPU lock acquisition exceeds `OCR_CPU_FALLBACK_TIMEOUT_SECONDS`, falls back to `gpu=False`.
- Handles extraction failures (0-length text) by flagging for manual review.
