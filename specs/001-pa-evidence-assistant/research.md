# Research: Prior Authorization Evidence Assistant

**Phase**: 0 — Outline & Research  
**Date**: 2026-08-08  
**Status**: Complete — all technical decisions resolved by user specification

## Overview

The user-provided specification and technical architecture description resolve all technology choices, deployment topology, data-layer design, agent architecture, and GPU resource management. No "NEEDS CLARIFICATION" items remain. This document records each decision, its rationale, and alternatives considered.

---

## Decision Log

### 1. LLM Runtime

- **Decision**: Ollama serving llama3.2:3b, running natively on the host
- **Rationale**: Native execution avoids Docker GPU passthrough complexity on Windows; llama3.2:3b fits within a 6GB VRAM budget with room for concurrent workloads when gated by the concurrency guard
- **Alternatives Considered**:
  - vLLM (heavier, requires Linux; overkill for single-model single-instance)
  - llama.cpp server (viable but Ollama provides a more ergonomic API and model management)
  - Larger models (7B+) — rejected due to 6GB VRAM constraint

### 2. Embedding Service

- **Decision**: HuggingFace Text-Embeddings-Inference (TEI) serving BAAI/bge-small-en-v1.5 (384-dim), running in a Docker container with the CUDA image
- **Rationale**: TEI is a production-grade embedding server with batching, health checks, and OpenAI-compatible API. Containerized because it doesn't need host filesystem access. bge-small-en-v1.5 is a strong performer at its size, well within the VRAM budget
- **Alternatives Considered**:
  - sentence-transformers in-process (no batching, no health endpoint, loads model into app process memory)
  - Larger models (bge-large, e5-large) — rejected for VRAM budget
  - API-based embeddings (OpenAI, Cohere) — rejected for data-locality principle

### 3. Sparse Encoding for Hybrid Search

- **Decision**: Qdrant-native BM25-style sparse encoding via fastembed, stored alongside dense vectors in the same Qdrant collection
- **Rationale**: fastembed provides SPLADE/BM25-style sparse vectors that Qdrant natively supports. Eliminates the need for a separate Elasticsearch/OpenSearch deployment. Single collection with both vector types simplifies query logic and point management
- **Alternatives Considered**:
  - Elasticsearch for keyword search (separate infrastructure, cross-store query complexity)
  - PostgreSQL full-text search (good for exact matches but weaker for learned sparse representations)
  - SPLADE model via TEI (not yet supported in TEI's stable branch)

### 4. Vector Store

- **Decision**: Qdrant, single collection (`pa_documents`), three doc_type payloads (`policy_chunk`, `case_document_chunk`, `case_profile`)
- **Rationale**: Single collection with payload-based filtering is simpler to manage than multiple collections. Qdrant supports named vectors (dense + sparse) per point natively. Hybrid search with RRF fusion is a first-class Qdrant feature via `query` API with `prefetch` + `fusion`
- **Alternatives Considered**:
  - Weaviate (heavier, more opinionated schema, hybrid search requires different wiring)
  - Milvus (overkill for single-instance, more complex deployment)
  - pgvector (lacks native sparse vector support, no built-in RRF fusion)

### 5. Object Storage

- **Decision**: MinIO (S3-compatible, self-hosted), Docker container
- **Rationale**: S3-compatible API via boto3; bucket-per-environment with `{case_id}/{document_id}.{ext}` key convention; avoids raw filesystem management (path escaping, backup, concurrent access). Lightweight — no GPU, modest CPU/RAM
- **Alternatives Considered**:
  - Raw filesystem (operational awkwardness: path management, no versioning, backup complexity)
  - PostgreSQL large objects (BLOBs degrade backup/restore performance)

### 6. Relational Database

- **Decision**: PostgreSQL 16, Docker container
- **Rationale**: Proven ACID-compliant store for relational data. Supports async via asyncpg. The audit_log append-only pattern is enforced at the application layer — no Postgres-level trigger/rule needed for v1, but the table design makes adding a trigger straightforward later
- **Alternatives Considered**:
  - SQLite (insufficient for concurrent access from async workers)
  - MySQL (less feature-rich for JSON columns and window functions used in audit queries)

### 7. OCR Engine

- **Decision**: EasyOCR running natively on the host with GPU, gated by the in-process concurrency guard
- **Rationale**: EasyOCR supports GPU acceleration, multiple languages, and has a simple Python API. Native execution avoids Docker GPU passthrough. The preprocessing pipeline (OpenCV: grayscale, deskew, denoise, adaptive binarization, contrast normalization) runs CPU-only and measurably improves accuracy on low-quality scans
- **Alternatives Considered**:
  - Tesseract (lower accuracy on handwritten/faxed content without extensive training)
  - PaddleOCR (strong accuracy but more complex installation on Windows)
  - Cloud OCR (Google Vision, AWS Textract) — rejected for data-locality

### 8. Document Parsing

- **Decision**: PyMuPDF (PDF), python-docx (DOCX), direct read (TXT/MD)
- **Rationale**: PyMuPDF extracts native text layers and can rasterize pages for OCR fallback. python-docx handles .docx natively. Both are well-maintained, pure-Python (or C-extension) libraries with no external service dependency
- **Alternatives Considered**:
  - Apache Tika (Java dependency, server process, overkill for 4 format types)
  - pdfplumber (slower than PyMuPDF, less control over rasterization)

### 9. GPU Contention Guard

- **Decision**: In-process asyncio.Semaphore with LLM priority, configurable CPU-fallback timeout (default 10s)
- **Rationale**: All GPU-consuming workloads (LLM, OCR, embedding) run in the same Python process or are called via HTTP from it. An asyncio.Semaphore gates concurrent GPU access. LLM calls acquire with high priority; OCR/embedding calls queue behind with a timeout, falling back to CPU if the timeout expires
- **Alternatives Considered**:
  - OS-level GPU process scheduling (complex, less portable)
  - Separate GPU queues (Redis/Celery — rejected, adds infrastructure complexity)
  - No guard (OOM risk on a 6GB card with concurrent LLM + OCR)

### 10. Authentication

- **Decision**: Self-hosted JWT (short-lived access + refresh tokens), OAuth2 password flow, bcrypt/passlib
- **Rationale**: No external IdP dependency. FastAPI's built-in OAuth2PasswordBearer integrates cleanly. Three roles (intake, nurse, admin) enforced via a role-checking dependency on every route. Token scopes are role-enumerated per FR-003a
- **Alternatives Considered**:
  - Keycloak (full IdP, overkill for 3 roles, adds a container)
  - Auth0/Okta (external service, violates data-locality)
  - Session-based auth (less suitable for API-first architecture)

### 11. Frontend Framework

- **Decision**: React 18+ with TypeScript, Vite build tool, running natively on the host
- **Rationale**: React + TypeScript is the standard for complex SPAs. Vite provides fast HMR for development. Running natively avoids Docker complexity and provides instant feedback during UI development
- **Alternatives Considered**:
  - Next.js (SSR overkill for an internal tool; adds Node server complexity)
  - Vue/Svelte (viable but less ecosystem depth for enterprise tooling)
  - Angular (heavier, more ceremony for this scope)

### 12. Task Scheduling (Lock Release)

- **Decision**: In-process APScheduler (BackgroundScheduler) for the 24-hour lock auto-release job
- **Rationale**: Simple, no additional infrastructure. Runs on an interval (every 5 minutes), queries for expired locks, releases them, writes audit entries. Suitable for single-instance deployment
- **Alternatives Considered**:
  - Celery Beat (requires Redis/RabbitMQ — explicitly excluded from the Docker footprint)
  - PostgreSQL pg_cron (ties scheduling logic to the database layer)
  - OS-level cron (less observable, harder to audit-log from)

### 13. Offline RAG Evaluation

- **Decision**: Ragas with LangchainLLMWrapper/LangchainEmbeddingsWrapper pointed at local models
- **Rationale**: Ragas provides Context Precision, Context Recall, and Faithfulness metrics out of the box. Wrapping local models (Ollama for judge LLM, TEI for judge embeddings) maintains data-locality. The harness is dev-time only, never wired into the live pipeline
- **Alternatives Considered**:
  - Manual evaluation (doesn't scale, not repeatable)
  - DeepEval (viable but less mature metric set for RAG-specific evaluation)
  - Custom metrics (fragile, not standardized)
- **Known Risk**: Small local judge models may fail to produce structured output Ragas expects, surfacing as NaN scores. Must validate early on a handful of samples before using as a regression gate.

### 14. Retrieval Fusion Strategy

- **Decision**: Reciprocal Rank Fusion (RRF) combining dense and sparse retrieval results. No reranking step in v1
- **Rationale**: RRF is parameter-free (only k=60 constant), doesn't require training a reranker, and provides strong baseline fusion quality. Qdrant supports RRF natively in its `query` API. A reranking step can be added in v2 if retrieval quality needs improvement
- **Alternatives Considered**:
  - Cross-encoder reranking (adds latency, requires another model in the VRAM budget)
  - Weighted linear combination (requires tuning weights per query type)
  - Dense-only (misses exact identifiers — violates P3)

---

## Unresolved Items

None. All technical decisions are resolved by the user specification and this research phase.
