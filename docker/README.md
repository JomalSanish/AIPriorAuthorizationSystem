# Prior Authorization Evidence Assistant — Startup Guide

> **Data-locality notice**: All inference (LLM, embeddings, OCR) and storage
> (vector DB, object store, relational DB) runs entirely on-premises.
> No patient data or derived text leaves this machine at runtime.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker Desktop | ≥ 4.x | Engine + Compose v2 (`docker compose`) |
| Python | 3.11+ | 3.12 recommended |
| Node.js | 18+ | 20 LTS recommended |
| Ollama | latest | Native install on host — **not** in Docker |
| CUDA drivers | 12.x | GPU inference (Ollama, EasyOCR, TEI) |

---

## Step 0: One-time model download

> **⚠️ Requires internet — this is the only step that touches an external server.**
> Run this once on the host before the first boot. After this, the system
> operates fully offline.

```sh
ollama pull llama3.2:3b
```

Verify the model is available:

```sh
ollama list
# Expected output (name may include a quantization suffix):
# NAME               ID            SIZE    MODIFIED
# llama3.2:3b        ...           2.0 GB  ...
```

---

## Step 1: Start Docker services

```sh
cd docker/
cp .env.example .env          # Edit credentials before first run
docker compose up -d
```

Expected `docker compose ps` output (all services `healthy`):

```
NAME         IMAGE                    STATUS          PORTS
postgres     postgres:16-alpine       Up (healthy)    0.0.0.0:5432->5432/tcp
qdrant       qdrant/qdrant:latest     Up (healthy)    0.0.0.0:6333-6334->6333-6334/tcp
tei          ghcr.io/hugging...       Up (healthy)    0.0.0.0:8080->80/tcp
minio        minio/minio:latest       Up (healthy)    0.0.0.0:9000-9001->9000-9001/tcp
```

> TEI (Text-Embeddings-Inference) loads `BAAI/bge-small-en-v1.5` into GPU
> memory on first start — allow 1–2 minutes for `(healthy)` to appear.

---

## Step 2: Wait for health checks

Poll until all four Docker services report `healthy`:

```sh
watch -n 5 docker compose ps
```

Or check with a single command:

```sh
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

---

## Step 3: Install backend dependencies

```sh
cd backend/
pip install -e ".[dev]"      # or: pip install -r requirements.txt
```

---

## Step 4: Apply database migrations

```sh
cd backend/
alembic upgrade head
```

Expected output ends with `Running upgrade ... -> <revision>, initial_schema`.

---

## Step 5: Start the backend

```sh
cd backend/
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The startup log will show each boot step:

```
INFO  pa.main — startup step=2 action=infrastructure_health_checks
INFO  pa.healthcheck — health_check service=postgres ok=True detail=OK
INFO  pa.healthcheck — health_check service=qdrant ok=True detail=OK
INFO  pa.healthcheck — health_check service=tei ok=True detail=OK
INFO  pa.healthcheck — health_check service=minio ok=True detail=OK
INFO  pa.healthcheck — health_check service=ollama ok=True detail=OK — llama3.2:3b present
INFO  pa.main — startup step=3 action=alembic_migrations
INFO  pa.main — startup alembic=migrations status=current
INFO  pa.main — startup step=4 action=ensure_minio_buckets
INFO  pa.main — startup minio bucket=pa-case-documents status=ready
INFO  pa.main — startup minio bucket=pa-policy-documents status=ready
INFO  pa.main — startup step=5 action=ensure_qdrant_collection
INFO  pa.main — startup qdrant collection=pa_documents status=ready
INFO  pa.main — startup step=6 action=start_apscheduler
INFO  pa.main — startup step=7 status=READY services=postgres,qdrant,tei,minio,ollama version=0.1.0
INFO  uvicorn.server — Application startup complete.
```

> **If any service fails after 3 retries**, the process exits with code 1 and
> logs which service was unreachable. Fix the failing service and restart.

---

## Step 6: Start the frontend

```sh
cd frontend/
npm install
npm run dev
```

The Vite dev server starts at `http://localhost:5173`.

---

## Step 7: Verify all health checks

```sh
curl -s http://localhost:8000/api/health | python -m json.tool
```

Expected response (`status: "ok"` means all services are healthy):

```json
{
  "status": "ok",
  "services": {
    "postgres": { "ok": true,  "detail": "OK" },
    "qdrant":   { "ok": true,  "detail": "OK" },
    "tei":      { "ok": true,  "detail": "OK" },
    "minio":    { "ok": true,  "detail": "OK" },
    "ollama":   { "ok": true,  "detail": "OK — llama3.2:3b present" }
  }
}
```

---

## Step 8: Seed an admin user

The system ships with no users. Create the first admin account via a
management command or the FastAPI interactive docs:

```sh
# Option A: via the /docs Swagger UI
# Navigate to http://localhost:8000/docs
# POST /api/admin/users — requires an existing admin token (bootstrap only)

# Option B: seed script (if provided in backend/scripts/)
python backend/scripts/seed_admin.py
```

---

## Troubleshooting

### TEI stays `starting` for > 5 minutes

TEI downloads `BAAI/bge-small-en-v1.5` from HuggingFace Hub on first start.
This is a one-time Docker layer build. Subsequent starts are fast.

Check progress:

```sh
docker compose logs tei --follow
```

### Ollama check fails: model not found

```
Ollama check: Model 'llama3.2:3b' not found. Run: ollama pull llama3.2:3b
```

Run `ollama pull llama3.2:3b` and restart the backend.

### Postgres check fails: connection refused

Ensure the Docker stack is running (`docker compose ps`) and the `DATABASE_URL`
in `docker/.env` matches the Postgres service credentials.

### Backend exits immediately with "FATAL"

A required service did not become healthy in 3 × 5 s = 15 s. Check:

```sh
docker compose ps        # Are all services "Up (healthy)"?
docker compose logs      # Look for error messages
```

---

## Data-Locality Enforcement

Run the static analysis gate before committing or in CI to ensure no public
API reference has been introduced:

```sh
python backend/scripts/check_locality.py
# Exit 0 = clean, Exit 1 = violations found (details printed)
```

This script scans all `.py`, `.ts`, `.tsx`, `.js`, `.jsx` files for:
- Prohibited URL substrings (OpenAI, Anthropic, Cohere, Google AI, etc.)
- Prohibited env-var names (`OPENAI_API_KEY`, etc.)
- Prohibited Python import statements (`import openai`, `from anthropic import`, etc.)

**Add it to your pre-commit hooks** (`.pre-commit-config.yaml`) or CI pipeline:

```yaml
# .github/workflows/ci.yml (excerpt)
- name: Data locality enforcement
  run: python backend/scripts/check_locality.py
```

---

## VRAM Budget Reference

| Component | Approx. VRAM | Notes |
|---|---|---|
| Ollama `llama3.2:3b` (Q4) | ~2.2 GB | Loaded on first LLM call |
| TEI `bge-small-en-v1.5` | ~0.3 GB | Loaded at container start |
| EasyOCR recognition model | ~0.5 GB | Loaded on first OCR call |
| **Total worst-case** | **~3.0 GB** | Within 6 GB budget |

The GPU contention guard (`backend/app/core/gpu_guard.py`) ensures Ollama,
TEI, and EasyOCR never run concurrently. OCR falls back to CPU if the GPU is
busy or unavailable.

---

## Service URLs (default dev)

| Service | URL | Purpose |
|---|---|---|
| Backend API | http://localhost:8000 | FastAPI + REST endpoints |
| API Docs | http://localhost:8000/docs | Swagger UI |
| Health probe | http://localhost:8000/api/health | Service status |
| Frontend | http://localhost:5173 | Vite dev server |
| MinIO console | http://localhost:9001 | Object storage admin |
| Qdrant UI | http://localhost:6333/dashboard | Vector DB admin |
| Ollama | http://localhost:11434 | Local LLM (native host) |
| TEI | http://localhost:8080 | Text-Embeddings-Inference |
