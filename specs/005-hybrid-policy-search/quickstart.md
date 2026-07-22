# Quickstart & Verification Guide: Persistent Hybrid Policy Document Search

This guide outlines how to verify the persistent hybrid policy search feature once implemented.

## Prerequisites

1. Ensure the virtual environment is active:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
2. Set the `OPENAI_API_KEY` environment variable in your `.env` file.

---

## Scenario 1: Index Building and Ingestion

Verify that policy guidelines PDFs can be successfully processed and stored as persistent indexes.

### Steps
1. Run the policy ingestion utility:
   ```powershell
   python utils/ingest_policies.py
   ```
2. Verify that the following files and directories are created under the `data/` directory:
   - `data/indices/policies_faiss/index.faiss`
   - `data/indices/policies_faiss/index.pkl`
   - `data/indices/policies_bm25.pkl`

---

## Scenario 2: Hybrid Search Verification

Verify that looking up a policy works for both exact CPT codes and conceptual semantic queries.

### Steps
1. Run a quick verification test script:
   ```powershell
   python scripts/verify_hybrid_search.py --query "96372"
   ```
   **Expected Outcome:** Returns the top matching documents from the Adalimumab drug policy PDF.
   
2. Run a query with no explicit CPT code, but clear semantic terms:
   ```powershell
   python scripts/verify_hybrid_search.py --query "joint space narrowing total knee"
   ```
   **Expected Outcome:** Resolves to the Total Knee Arthroplasty section of the guidelines PDF, demonstrating semantic retrieval.

---

## Scenario 3: End-to-End Pipeline Integration Test

Verify that running the prior authorization agents uses the persistent hybrid index.

### Steps
1. Execute the pytest test suite:
   ```powershell
   pytest tests/test_pipeline.py
   ```
2. Ensure all tests complete successfully.
