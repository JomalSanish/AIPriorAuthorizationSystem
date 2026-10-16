# Deployment Specification

## Application Configuration (T004)
- Uses `Pydantic BaseSettings` with `.env` and `SecretsProvider`.
- Key settings: `DATABASE_URL`, `MINIO_ENDPOINT`, `QDRANT_URL`, `TEI_URL`, `OLLAMA_URL`, `GPU_PRIORITY_POLICY`, `VRAM_BUDGET_MB`.

## Container Stack (T015)
- Docker Compose includes:
  - PostgreSQL (relational data, audit logs)
  - MinIO (S3-compatible raw document storage)
  - Qdrant (vector store)
  - TEI (Text Embeddings Inference, CUDA image)
- **Host Native Services**: Backend (FastAPI), Frontend (Vite), and Ollama run natively on the host (Windows) to manage GPU resources easily.

## Startup Sequence (T091)
- FastAPI Lifespan handler enforces a strict boot order:
  1. Load Settings
  2. Health-check Postgres, Qdrant, TEI, MinIO (retries built-in)
  3. Health-check Ollama (`llama3.2:3b`)
  4. Run Alembic migrations
  5. Ensure MinIO buckets and Qdrant collections exist
  6. Start APScheduler (lock auto-release)
- System refuses to boot if dependencies are unavailable.

## Data Locality Enforcement (T092, Constitution P2)
- `backend/scripts/check_locality.py` — static scan of all backend and frontend source files for prohibited patterns: hosted-API URLs (`api.openai.com`, `api.anthropic.com`, etc.), hosted-API environment variable references (`OPENAI_API_KEY`, etc.), and hosted-API SDK imports (`import openai`, etc.).
- Makes no network calls itself — pure static/grep-based analysis.
- Exit code 1 with file:line references on any violation; intended as a CI step or pre-commit hook.
- This is the enforcement mechanism backing the "zero public API egress" claim made elsewhere in this document and in `security-compliance.md`.

## Startup Documentation (T093)
- `docker/README.md` — full step-by-step setup guide: prerequisites, `docker compose up -d`, expected `docker compose ps` health output, backend/frontend setup commands, seed-admin-user step, and an explicit callout that the one-time `ollama pull llama3.2:3b` step requires internet access (the only step in the entire setup that does).