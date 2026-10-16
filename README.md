# Prior Authorization Evidence Assistant

A local, human-in-the-loop AI application that assists payer operations teams in reviewing prior-authorization requests against clinical policies.

The system processes policy and case documents, retrieves relevant evidence using hybrid RAG, reasons over each policy requirement, and produces a nurse-facing evidence summary and gap checklist.

> **Important:** The AI system does not make the final accept/reject decision. A human Nurse Reviewer retains decision authority.

---

## Features

- Policy document ingestion and versioning
- Case creation with multiple documents
- PDF, DOCX, TXT/Markdown and scanned-document processing
- OCR fallback for image-based documents
- Five-agent AI processing pipeline
- Hybrid dense + sparse retrieval
- Reciprocal Rank Fusion (RRF)
- Evidence classification: Present / Absent / Unclear
- Evidence citations and confidence scores
- Nurse review workspace
- Case locking to prevent concurrent review
- SLA tracking
- Admin policy and user management
- JWT authentication and role-based access
- Append-oriented audit trail
- Local LLM inference through Ollama
- PostgreSQL, Qdrant and MinIO persistence
- GPU contention protection / degraded CPU fallback
- Offline RAG evaluation support

---

## Architecture

```text
                         ┌─────────────────────┐
                         │     React + Vite     │
                         │      Frontend        │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │       FastAPI       │
                         │       Backend       │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Workflow Agent    │
                         │    LLM Planner      │
                         └──────────┬──────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             ▼                      ▼                      ▼
       Intake Agent          Retrieval Agent         Reasoning Agent
       Parse / Index         Hybrid RAG + RRF       Present/Absent/
                                                    Unclear + confidence
             │                      │                      │
             └──────────────────────┼──────────────────────┘
                                    ▼
                             Summary Agent
                                    │
                                    ▼
                           Nurse Review Queue
                                    │
                                    ▼
                         Human Final Decision
```

---

## Five-Agent Pipeline

### 1. Workflow Agent

The Workflow Agent acts as the bounded planner/orchestrator.

Responsibilities:

- coordinate the other agents;
- choose the next allowed action;
- record planner decisions;
- re-run retrieval when reasoning confidence is insufficient;
- enforce a per-case turn budget;
- guarantee that processing terminates in the Nurse Review queue.

It cannot approve or reject a case.

### 2. Intake Agent

Responsibilities:

- parse policy and case documents;
- perform OCR when required;
- extract relevant metadata;
- chunk documents;
- create embeddings;
- index documents into the retrieval layer.

### 3. Retrieval Agent

Responsibilities:

- construct requirement-specific retrieval queries;
- perform dense semantic search;
- perform sparse keyword search;
- fuse the result sets with RRF;
- apply case/policy metadata filters;
- return grounded evidence chunks.

### 4. Reasoning Agent

For each policy requirement, the Reasoning Agent evaluates the retrieved evidence and produces:

```text
Present
Absent
Unclear
```

along with:

- confidence;
- evidence citation;
- supporting text;
- reasoning output.

Low-confidence results can trigger bounded re-retrieval through the Workflow Agent.

### 5. Summary Agent

Produces the nurse-facing output:

- evidence summary;
- requirement-by-requirement findings;
- gap checklist;
- citations;
- confidence information.

The Summary Agent does not make a final medical/coverage decision.

---

## Data Architecture

```text
                    ┌───────────────┐
                    │  PostgreSQL   │
                    │ users/cases/  │
                    │ policies/audit│
                    └───────┬───────┘
                            │
       ┌────────────────────┼─────────────────────┐
       ▼                    ▼                     ▼
   ┌────────┐          ┌────────┐           ┌────────┐
   │ Qdrant │          │ MinIO  │           │Ollama  │
   │ vectors│          │ files  │           │  LLM   │
   └────────┘          └────────┘           └────────┘
```

### PostgreSQL

Stores structured application data including:

- users;
- policies;
- policy requirements;
- cases;
- case documents;
- policy documents;
- nurse decisions;
- case locks;
- audit records.

### Qdrant

Stores searchable document representations for:

- policy chunks;
- case-document chunks;
- case-profile information.

Hybrid retrieval combines dense and sparse representations.

### MinIO

Stores source documents independently from the relational database.

Object keys follow case/policy scoped conventions so documents can be recovered without embedding raw files in PostgreSQL.

### Ollama

Provides local LLM inference.

The current configuration uses:

```text
llama3.2:3b
```

Ollama runs natively on the host rather than as part of the Docker Compose stack.

---

## Retrieval Architecture

The system intentionally does not rely on dense vector similarity alone.

```text
Requirement
    │
    ├───────────────► Dense Retrieval
    │                     │
    │                     ▼
    │                Semantic matches
    │
    └───────────────► Sparse Retrieval
                          │
                          ▼
                    Exact keywords /
                    identifiers
                          │
             ┌────────────┴────────────┐
             ▼                         ▼
        Ranked dense               Ranked sparse
             │                         │
             └───────────┬─────────────┘
                         ▼
                    RRF Fusion
                         │
                         ▼
                 Top Evidence Chunks
                         │
                         ▼
                  Reasoning Agent
```

### Why hybrid retrieval?

Prior-authorization documents contain both:

- semantic clinical concepts;
- exact identifiers and phrases.

For example, semantic retrieval can connect related clinical language, while sparse retrieval can preserve exact matches for codes, named procedures, medications, durations, and other policy-specific terminology.

---

## Document Processing

Supported document categories include:

- PDF
- DOCX
- TXT
- Markdown
- JPEG
- PNG
- TIFF
- scanned PDFs

The pipeline first attempts normal text extraction.

OCR is used as a fallback when the extracted text is insufficient.

The OCR pipeline uses:

- OpenCV preprocessing;
- EasyOCR;
- GPU-aware execution;
- CPU fallback when GPU access is unavailable or constrained.

---

## Human-in-the-Loop Design

The application explicitly separates AI assistance from final decision authority.

```text
AI Pipeline
    │
    ▼
Evidence Summary
    │
    ▼
Gap Checklist
    │
    ▼
Nurse Review
    │
    ├── Inspect AI evidence
    ├── Inspect original documents
    ├── Verify findings
    │
    ▼
Accept / Reject
```

The AI pipeline ends at:

```text
Pending Nurse Review
```

It never emits a final accept/reject decision.

---

## Roles and Permissions

| Capability | Intake | Nurse | Admin |
|---|:---:|:---:|:---:|
| Create case | ✓ | — | ✓ |
| Upload case documents | ✓ | — | ✓ |
| Read case | ✓ | ✓ | ✓ |
| Lock case | — | ✓ | ✓ |
| Make final decision | — | ✓ | ✓* |
| View history | — | ✓ | ✓ |
| Manage policies | — | — | ✓ |
| Manage users | — | — | ✓ |
| View audit information | — | — | ✓ |

`*` Administrative intervention is governed by the project's verification and audit rules.

---

## Security and Governance

The design includes:

- JWT access and refresh tokens;
- bcrypt password hashing;
- role-scoped API dependencies;
- protected frontend routes;
- secrets abstraction;
- audit logging;
- append-only audit-log invariant;
- restricted administrative operations;
- local inference;
- no external model/API dependency in the runtime inference path.

Development environments should use synthetic data only.

---

## GPU-Aware Design

The target design assumes a constrained single-GPU environment.

The system therefore treats GPU memory as a shared resource between:

- LLM inference;
- OCR;
- embedding workloads where applicable.

A GPU contention guard limits concurrent GPU-heavy work.

If GPU access is unavailable, supported workloads can fall back to CPU execution rather than preventing the application from processing cases.

### Current Compose configuration

The current `docker-compose.yml` uses the **CPU** TEI image:

```text
ghcr.io/huggingface/text-embeddings-inference:cpu-1.9
```

This is deliberate: it leaves GPU capacity available for Ollama and OCR.

---

## Project Structure

```text
prior-auth-evidence-assistant/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── workflow.py
│   │   │   ├── intake.py
│   │   │   ├── retrieval.py
│   │   │   ├── reasoning.py
│   │   │   └── summary.py
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   └── services/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── validation scripts
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── context/
│   │   ├── hooks/
│   │   └── services/
│   ├── package.json
│   └── vite.config.ts
│
├── docker/
│   ├── docker-compose.yml
│   └── .env.example
│
├── specs/
│   └── 001-pa-evidence-assistant/
│       ├── spec.md
│       ├── plan.md
│       ├── research.md
│       ├── data-model.md
│       ├── quickstart.md
│       ├── tasks.md
│       ├── checklists/
│       └── contracts/
│
├── PA_Assistant_SpecKit_Prompts.md
└── .specify/
```

---

## Specification Documents

The implementation is backed by a complete Spec-Kit feature package:

| Document | Purpose |
|---|---|
| `spec.md` | Functional requirements and user stories |
| `research.md` | Technology decisions and alternatives |
| `plan.md` | Architecture and implementation plan |
| `data-model.md` | Data entities and relationships |
| `quickstart.md` | Local development setup |
| `tasks.md` | Dependency-ordered implementation tasks |
| `agent-spec.md` | Agent contracts and guardrails |
| `api-spec.md` | REST API contracts |
| `rag-pipeline-spec.md` | Retrieval architecture |
| `rag-evaluation-spec.md` | RAG evaluation strategy |
| `ocr-pipeline-spec.md` | OCR and fallback behaviour |
| `security-compliance.md` | Security and RBAC |
| `deployment-spec.md` | Runtime/deployment architecture |
| `ui-spec.md` | Frontend behaviour |

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js
- Docker Desktop
- Ollama
- `llama3.2:3b`

### Infrastructure

```bash
cd docker
cp .env.example .env
docker compose up -d
```

### Backend

```bash
cd ../backend

python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -e .

alembic upgrade head

uvicorn app.main:app --reload
```

OCR support:

```bash
pip install -e ".[ocr]"
```

Evaluation dependencies:

```bash
pip install -e ".[eval]"
```

### Frontend

```bash
cd ../frontend
npm install
npm run dev
```

### Ollama

```bash
ollama pull llama3.2:3b
ollama list
```

---

## Development Workflow

The project follows Spec-Driven Development:

```text
Constitution
     ↓
Specification
     ↓
Research
     ↓
Plan
     ↓
Tasks
     ↓
Implementation
     ↓
Validation / Analysis
```

The project also uses phase-specific validation scripts in the backend for implementation checkpoints.

---

## Design Goals

The application is designed around:

- **Grounded AI** rather than free-form generation;
- **Human oversight** rather than autonomous clinical/coverage decisions;
- **Hybrid retrieval** rather than vector-only search;
- **Local inference** rather than sending sensitive case documents to hosted LLM APIs;
- **Traceability** rather than opaque recommendations;
- **Bounded agent behaviour** rather than unrestricted agent loops.

---

## Disclaimer

This project is an engineering/portfolio implementation of an AI-assisted prior-authorization workflow. It is not a substitute for clinical judgement, payer policy governance, legal review, or production compliance certification.
