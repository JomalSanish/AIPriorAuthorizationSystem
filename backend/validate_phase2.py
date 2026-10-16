import asyncio
from app.services.minio import minio_service
from app.services.document import document_service
from app.services.ocr import ocr_service
from app.core.gpu_guard import gpu_guard, GpuPriority

async def main():
    print("Testing Phase 2 Services...")
    
    # 1. MinIO
    print("Connecting to MinIO...")
    minio_service.ensure_bucket("pa-test-bucket")
    print("MinIO: OK")

    # 2. Document Service & OCR Service Initialization
    print("Testing Document Service...")
    sample_txt = b"Hello, world!"
    res = await document_service.process_document(sample_txt, "test.txt", "text/plain")
    assert "Hello, world!" in res.full_text
    print("Document Text Parsing: OK")

    # 3. GPU Guard
    print("Testing GPU Guard...")
    async with gpu_guard.acquire_or_fallback(GpuPriority.OCR, timeout=1.0) as acquired:
        assert acquired is True
    print("GPU Guard: OK")

    print("Phase 2 Initialization & Basics: OK")

if __name__ == "__main__":
    asyncio.run(main())
