import asyncio
import sys
import os
import mimetypes

from app.services.document import document_service
from app.services.minio import minio_service

async def main():
    if len(sys.argv) < 2:
        print("Usage: python manual_test_phase2.py <path_to_file>")
        sys.exit(1)

    filepath = sys.argv[1]
    filename = os.path.basename(filepath)
    
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    # Guess MIME type
    mime_type, _ = mimetypes.guess_type(filepath)
    if not mime_type:
        # Fallback for common types
        if filename.endswith(".pdf"): mime_type = "application/pdf"
        elif filename.endswith(".docx"): mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif filename.endswith(".txt") or filename.endswith(".md"): mime_type = "text/plain"
        elif filename.endswith(".png"): mime_type = "image/png"
        elif filename.endswith(".jpg") or filename.endswith(".jpeg"): mime_type = "image/jpeg"
        else: mime_type = "application/octet-stream"

    print(f"--- Testing Document Processing ---")
    print(f"File: {filename} (MIME: {mime_type})")
    
    with open(filepath, "rb") as f:
        file_bytes = f.read()

    print("\n1. Parsing & OCR...")
    result = await document_service.process_document(file_bytes, filename, mime_type)
    
    print(f"  - SHA256 Hash: {result.sha256_hash}")
    print(f"  - OCR Status: {result.ocr_status}")
    print(f"  - Total Pages Parsed: {len(result.pages)}")
    print(f"  - Total Extracted Text Length: {len(result.full_text)} characters")
    
    print("\n--- Extracted Text Preview (First 500 chars) ---")
    print(result.full_text[:500] + ("..." if len(result.full_text) > 500 else ""))
    print("--------------------------------------------------")

    print("\n2. Testing MinIO Storage...")
    bucket = "pa-manual-test-bucket"
    object_key = f"test/{filename}"
    
    print(f"  - Ensuring bucket '{bucket}' exists...")
    minio_service.ensure_bucket(bucket)
    
    print(f"  - Uploading file as '{object_key}'...")
    minio_service.upload_file(bucket, object_key, file_bytes, mime_type)
    print("  - Upload successful!")
    
    print(f"  - Verifying download...")
    downloaded_bytes = minio_service.download_file(bucket, object_key)
    if len(downloaded_bytes) == len(file_bytes):
        print("  - Download verified (sizes match).")
    else:
        print("  - WARNING: Download size mismatch!")

    # Cleanup
    print("  - Cleaning up object...")
    minio_service.delete_file(bucket, object_key)
    print("Done!")

if __name__ == "__main__":
    asyncio.run(main())
