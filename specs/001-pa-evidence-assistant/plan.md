# Implementation Plan: Prior Authorization Evidence Assistant

**Branch**: `001-pa-evidence-assistant` | **Date**: 2026-08-08 | **Spec**: [spec.md](file:///c:/Users/Jomal/Projects/SDD-Learning/jomal/prior-auth-evidence-assistant/specs/001-pa-evidence-assistant/spec.md)

**Input**: Feature specification from `/specs/001-pa-evidence-assistant/spec.md`

## Summary

Build a complete on-prem payer-side web application that assists payer operations staff with prior authorization requests. The system uses a five-agent LLM-driven pipeline (Workflow, Intake, Retrieval, Reasoning, Summary) to analyze case documents against policy requirements, producing evidence summaries and gap checklists for Nurse Reviewers. The system never makes accept/reject decisions — that authority belongs exclusively to human Nurse Reviewers. All inference runs locally with zero external data egress. Three roles (Intake, Nurse, Admin) are strictly separated via JWT/OAuth2 authentication with role-scoped API access.

## Technical Context

**Language/Version**: Python 3.11+ (backend), TypeScript 5.x (frontend)

**Primary Dependencies**:
- Backend: FastAPI, SQLAlchemy (async), Alembic, Pydantic v2, httpx, PyMuPDF, python-docx, OpenCV (opencv-python-headless), EasyOCR, APScheduler, passlib[bcrypt], python-jose[cryptography], qdrant-client, fastembed, boto3 (S3-compatible MinIO access)
- Frontend: React 18+, TypeScript, Vite, React Router, Axios
- Infrastructure: Ollama (llama3.2:3b), PostgreSQL 16, Qdrant, HuggingFace Text-Embeddings-Inference (BAAI/bge-small-en-v1.5), MinIO
- Evaluation: Ragas, LangChain (wrappers only)

**Storage**: PostgreSQL (relational), Qdrant (vector), MinIO (object/documents)

**Testing**: pytest (backend), Vitest + React Testing Library (frontend), Ragas (offline RAG evaluation)

**Target Platform**: Windows host (native backend/frontend/Ollama) + Docker (PostgreSQL, Qdrant, TEI, MinIO)

**Project Type**: Web application (FastAPI backend + React/TypeScript frontend)

**Performance Goals**: Pipeline completion <5 min for standard cases (<20 pages); Nurse review <10 min; NLP search <3s response

**Constraints**: Single GPU (6GB VRAM budget); single-instance architecture; zero external egress; synthetic data only in dev/test

**Scale/Scope**: Single-instance deployment; 3 user roles; 5 agents; 9 design specification documents

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Pre-Phase 0 | Post-Phase 1 |
|---|-----------|-------------|--------------|
| P1 | Human-in-the-Loop Only | ✅ PASS | ✅ PASS — No accept/reject action in agent action set; `finalize_to_nurse_review` is the only terminal action; data model has no auto-decision field |
| P2 | Confidentiality & Data Locality | ✅ PASS | ✅ PASS — All inference local; MinIO on-prem; no external API in any contract; `FR-043c` browser-side prohibition documented in UI spec |
| P3 | Hybrid Retrieval Mandatory | ✅ PASS | ✅ PASS — RAG pipeline spec mandates dense+sparse+RRF on every retrieval path including NLP search |
| P4 | Grounded, Cited, Auditable | ✅ PASS | ✅ PASS — Citation schema carries doc_id + page + section; audit_log table is append-only with full field set |
| P5 | Five-Agent Runtime | ✅ PASS | ✅ PASS — Agent spec defines all 5 agents, whitelist action set, turn budget, guardrails |
| P6 | Hardware-Aware GPU Sharing | ✅ PASS | ✅ PASS — GPU contention guard with configurable timeout and CPU fallback documented in OCR pipeline spec |
| P7 | Role-Strict Access | ✅ PASS | ✅ PASS — RBAC matrix in security spec; API spec tags every endpoint with required role(s) |
| P8 | Verification Integrity | ✅ PASS | ✅ PASS — Admin edit triggers status → `re_verification_required`, unlock, re-queue in data model and API spec |
| P9 | Secrets Abstraction Day One | ✅ PASS | ✅ PASS — `SecretsProvider` interface in security spec; settings module backed by env vars with swap-ready backend |
| P10 | Spec-Driven Development | ✅ PASS | ✅ PASS — All 9 design specs produced before implementation; `/speckit-analyze` checkpoint documented |

**Gate result**: All 10 principles pass both pre- and post-Phase 1 checks. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/001-pa-evidence-assistant/
├── plan.md                  # This file
├── research.md              # Phase 0 output
├── data-model.md            # Phase 1 output
├── quickstart.md            # Phase 1 output
├── contracts/
│   ├── api-spec.md          # REST API contracts
│   ├── agent-spec.md        # Agent input/output contracts
│   ├── rag-pipeline-spec.md # RAG pipeline contracts
│   ├── rag-evaluation-spec.md # Offline RAG evaluation
│   ├── ocr-pipeline-spec.md # OCR pipeline contracts
│   ├── ui-spec.md           # UI screen specifications
│   ├── security-compliance.md # RBAC, secrets, audit
│   └── deployment-spec.md   # Docker + native setup
└── tasks.md                 # Phase 2 output (via /speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings / secrets abstraction
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── workflow.py      # Workflow Agent (LLM planner)
│   │   ├── intake.py        # Intake Agent (parse/embed)
│   │   ├── retrieval.py     # Retrieval Agent (hybrid search)
│   │   ├── reasoning.py     # Reasoning Agent (classify)
│   │   └── summary.py       # Summary Agent (generate)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── auth.py          # Login, token refresh
│   │   ├── cases.py         # Case CRUD + search
│   │   ├── policies.py      # Policy management
│   │   ├── nurse_review.py  # Lock, decide, history
│   │   ├── admin.py         # Admin oversight, user mgmt
│   │   └── deps.py          # Auth dependencies, role checks
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py      # JWT, password hashing
│   │   ├── gpu_guard.py     # GPU contention semaphore
│   │   └── secrets.py       # Secrets provider abstraction
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py      # Async engine, session
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   └── migrations/      # Alembic migrations
│   └── services/
│       ├── __init__.py
│       ├── ocr.py           # OCR pipeline + preprocessing
│       ├── document.py      # Document parsing (PDF/DOCX/TXT)
│       ├── embedding.py     # TEI client + fastembed sparse
│       ├── qdrant.py        # Qdrant collection management
│       ├── minio.py         # MinIO S3 client
│       ├── ollama.py        # Ollama LLM client
│       └── scheduler.py     # APScheduler (lock release)
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluation/          # Ragas offline evaluation harness
├── alembic.ini
├── requirements.txt
└── pyproject.toml

frontend/
├── src/
│   ├── components/
│   │   ├── Sidebar.tsx
│   │   ├── SearchBar.tsx
│   │   ├── CaseCard.tsx
│   │   ├── DocumentViewer.tsx
│   │   ├── EvidenceSummary.tsx
│   │   └── GapChecklist.tsx
│   ├── pages/
│   │   ├── Login.tsx
│   │   ├── CaseManagement.tsx
│   │   ├── NewCase.tsx
│   │   ├── NurseReview.tsx
│   │   ├── CaseDetail.tsx
│   │   ├── AdminDashboard.tsx
│   │   └── PolicyManagement.tsx
│   ├── services/
│   │   ├── api.ts           # Axios instance + interceptors
│   │   └── auth.ts          # Token management
│   ├── hooks/
│   ├── types/
│   ├── App.tsx
│   └── main.tsx
├── tests/
├── index.html
├── vite.config.ts
├── tsconfig.json
└── package.json

docker/
├── docker-compose.yml       # PostgreSQL, Qdrant, TEI, MinIO
└── .env.example
```

**Structure Decision**: Web application layout with `backend/` (FastAPI) and `frontend/` (React/Vite) at repo root. Infrastructure services in `docker/`. Design specifications in `specs/001-pa-evidence-assistant/contracts/`. This matches the existing skeleton directories already present in the repo.

## Complexity Tracking

> No constitution violations to justify. All design decisions align with the 10 principles.
