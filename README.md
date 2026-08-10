# Jomal — Spec-Driven AI Engineering Projects

This repository contains two AI/GenAI projects developed using a **Spec-Driven Development (SDD)** workflow with **Spec-Kit**.

The projects focus on two different evidence-retrieval problems:

1. **Prior Authorization Evidence Assistant** — an on-premise healthcare application that analyses prior-authorization case documents against policy requirements and assists human nurse reviewers.
2. **Oncology Evidence Retrieval** — a scientific evidence platform designed to retrieve, validate, rank, trace, and summarise oncology research evidence with strong provenance and reproducibility guarantees.

Both projects emphasise explicit specifications, architecture decisions, agent boundaries, auditability, retrieval quality, and human oversight.

---

## Repository Structure

```text
jomal/
├── Oncology-Evidence-Retrieval/
│   ├── oncology-evidence-platform-speckit-playbook.md
│   └── .specify/
│
└── prior-auth-evidence-assistant/
    ├── backend/
    ├── frontend/
    ├── docker/
    ├── specs/
    ├── PA_Assistant_SpecKit_Prompts.md
    └── .specify/
```

### Projects at a glance

| Project | Domain | Main Architecture | Current Focus |
|---|---|---|---|
| [Prior Authorization Evidence Assistant](./prior-auth-evidence-assistant/prior-auth-evidence-assistant-README.md) | Healthcare / Payer Operations | FastAPI + React + 5-agent RAG pipeline | Implemented application |
| [Oncology Evidence Retrieval](./Oncology-Evidence-Retrieval/README.md) | Biomedical Research | Multi-agent evidence retrieval + provenance platform | Spec-Kit architecture/playbook |

---

# 1. Prior Authorization Evidence Assistant

A local, human-in-the-loop AI assistant for analysing prior-authorization requests.

The system ingests policy and case documents, retrieves evidence using hybrid search, evaluates evidence against policy requirements, and produces a nurse-facing summary. **The AI does not approve or reject a case.** The final decision remains with a human Nurse Reviewer.

### Core architecture

```text
                         ┌──────────────────────┐
                         │      React / Vite    │
                         │      Frontend        │
                         └──────────┬───────────┘
                                    │ REST / HTTP
                                    ▼
                         ┌──────────────────────┐
                         │      FastAPI         │
                         │      Backend         │
                         └──────────┬───────────┘
                                    │
                          ┌─────────┴─────────┐
                          │   Workflow Agent  │
                          │   LLM Planner     │
                          └─────────┬─────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             ▼                      ▼                      ▼
      Intake Agent          Retrieval Agent         Reasoning Agent
      Parse / Index          Hybrid RAG + RRF       Evidence Verdicts
             │                      │                      │
             └──────────────────────┼──────────────────────┘
                                    ▼
                            Summary Agent
                                    │
                                    ▼
                           Nurse Review Queue
                                    │
                                    ▼
                         Human Accept / Reject
```

### Technology stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy, Alembic
- **Frontend:** React, TypeScript, Vite, React Router, Axios
- **LLM:** Ollama with `llama3.2:3b`
- **Embeddings:** `BAAI/bge-small-en-v1.5`
- **Vector database:** Qdrant
- **Sparse retrieval:** FastEmbed / BM25-style sparse representations
- **Fusion:** Reciprocal Rank Fusion (RRF)
- **Database:** PostgreSQL 16
- **Object storage:** MinIO
- **Document processing:** PyMuPDF, python-docx
- **OCR:** EasyOCR + OpenCV when OCR fallback is required
- **Scheduling:** APScheduler
- **Evaluation:** Ragas / LangChain wrappers
- **Infrastructure:** Docker Compose for PostgreSQL, Qdrant, TEI, and MinIO
- **LLM runtime:** Ollama runs natively on the host

### Key engineering decisions

- Five-agent architecture with a dedicated Workflow Agent.
- Hybrid dense + sparse retrieval rather than dense-only search.
- RRF for retrieval fusion.
- Policy versioning so historical cases remain tied to the policy version used for processing.
- Strict role-based access control for Intake, Nurse, and Admin users.
- Human-only final decisions.
- Append-oriented audit logging of AI and human actions.
- Local inference and storage to minimise data egress.
- GPU contention protection and CPU fallback for degraded hardware conditions.
- OCR is used as a fallback when normal document extraction is insufficient.
- A bounded Workflow Agent turn budget guarantees pipeline termination.
- Admin changes that affect verification trigger re-verification rather than silently modifying an existing conclusion.

### Main workflow

```text
Policy Upload
     │
     ▼
Document Parsing / OCR
     │
     ▼
Policy Requirement Extraction
     │
     ▼
Hybrid Indexing
     │
     └──────────────► PostgreSQL / Qdrant / MinIO

Case Creation
     │
     ▼
Case Document Parsing / OCR
     │
     ▼
Metadata Extraction
     │
     ▼
Workflow Agent
     │
     ├──► Intake Agent
     ├──► Retrieval Agent
     ├──► Reasoning Agent
     └──► Summary Agent
              │
              ▼
       Evidence Summary
       Gap Checklist
              │
              ▼
       Nurse Review
              │
              ▼
     Human Final Decision
```

### RAG pipeline

For each policy requirement:

1. Build a requirement-specific search query.
2. Run dense semantic retrieval.
3. Run sparse/keyword retrieval.
4. Fuse results with RRF.
5. Apply metadata and case/policy filtering.
6. Pass grounded evidence to the Reasoning Agent.
7. Classify evidence as **Present, Absent, or Unclear** with confidence and citation.
8. Allow the Workflow Agent to perform bounded re-retrieval when confidence is insufficient.
9. Produce the nurse-facing evidence summary and gap checklist.

The system is designed so that retrieval evidence remains traceable to the underlying document.

### Roles

| Role | Responsibilities |
|---|---|
| **Intake** | Create cases, upload documents, select policies, view permitted case information |
| **Nurse** | Review evidence, inspect documents, lock cases, make the final decision |
| **Admin** | Manage policies/users, oversee cases, inspect audit information, perform authorised interventions |

### Repository documentation

The complete Spec-Kit design is maintained under:

```text
specs/001-pa-evidence-assistant/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── tasks.md
└── contracts/
    ├── agent-spec.md
    ├── api-spec.md
    ├── deployment-spec.md
    ├── ocr-pipeline-spec.md
    ├── rag-evaluation-spec.md
    ├── rag-pipeline-spec.md
    ├── security-compliance.md
    └── ui-spec.md
```

The project also contains the Spec-Kit implementation prompt history in `PA_Assistant_SpecKit_Prompts.md`.

---

## Running the Prior Authorization Assistant

### Prerequisites

- Windows/Linux/macOS development environment
- Python 3.11+
- Node.js
- Docker Desktop / Docker Engine
- Ollama
- `llama3.2:3b`
- Sufficient resources for PostgreSQL, Qdrant, MinIO, embeddings, and local LLM inference

### 1. Start infrastructure

```bash
cd prior-auth-evidence-assistant/docker
cp .env.example .env
docker compose up -d
```

The current Compose stack provides:

- PostgreSQL
- Qdrant
- Text Embeddings Inference
- MinIO

Ollama is intentionally run outside Docker.

### 2. Start the backend

```bash
cd ../backend

python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -e .

alembic upgrade head

uvicorn app.main:app --reload
```

For OCR dependencies:

```bash
pip install -e ".[ocr]"
```

### 3. Start the frontend

```bash
cd ../frontend
npm install
npm run dev
```

### 4. Start Ollama

Ensure the required model is available locally:

```bash
ollama pull llama3.2:3b
ollama list
```

The application expects Ollama to be available on its local API.

> **Hardware note:** the design targets a constrained single-GPU environment. The current Docker Compose configuration deliberately uses the CPU TEI image so the GPU remains available for Ollama and OCR. This differs from the earlier design option that considered CUDA-based TEI.

---

# 2. Oncology Evidence Retrieval

The Oncology Evidence Retrieval project applies Spec-Driven Development to a more research-oriented evidence platform.

Its goal is to create a provenance-first scientific evidence system in which researchers can search oncology literature and clinical evidence while retaining:

- source provenance,
- validation state,
- evidence lineage,
- deterministic weighting,
- reproducible conclusions,
- citation traceability,
- human review authority.

The current project directory primarily contains the **Spec-Kit playbook and specification workflow**, rather than a completed production implementation.

### Planned architecture

```text
                 Researcher Query
                       │
                       ▼
              State Classifier Agent
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
 NOT_YET_INVESTIGATED  ...    EVIDENCE_AVAILABLE
          │
          ▼
    Ingestion Agent
          │
     ┌────┼──────────────┐
     ▼    ▼              ▼
  PubMed APIs      Clinical Trials    Internal Sources
     │
     ▼
 Provenance Agent
     │
     ├── Validation
     ├── Data sensitivity
     └── Metadata completeness
     │
     ▼
 ┌────────────── Evidence Layer ──────────────┐
 │ PostgreSQL │ Neo4j │ Qdrant │ MinIO       │
 └────────────────────────────────────────────┘
                       │
                       ▼
               Retrieval Agent
                       │
                       ▼
             Reasoning / Weighting
                       │
                       ▼
              Summary / Citation
                       │
                       ▼
                Human Review
```

### Core principles

The playbook establishes eleven architectural/process principles, including:

1. **Provenance first** — incomplete evidence is not searchable or surfaced as valid evidence.
2. **Four-state resolution** — every query must resolve to one of:
   - `NOT_YET_INVESTIGATED`
   - `CONFIRMED_ABSENT`
   - `UNKNOWN`
   - `EVIDENCE_AVAILABLE`
3. **Deterministic weighting** — weights come from a versioned rubric rather than an LLM's subjective judgement.
4. **Weight-dimension disambiguation** — ambiguous percentage/weight requests require explicit clarification.
5. **Component-level data preservation** — details such as hazard ratios, confidence intervals, treatment arms, and biomarker information remain accessible.
6. **Traceable claims** — generated assertions must resolve to source evidence.
7. **Human review authority** — agents cannot accept, reject, or override evidence validity.
8. **Agent guardrails** — the planner uses a whitelist of actions and a bounded turn budget.
9. **Reproducibility** — rubric and state-resolution logic are versioned.
10. **Data-sensitivity gating** — public and internal/proprietary information are routed appropriately.
11. **ADR-driven architecture** — significant technical decisions are recorded before implementation.

### Planned technology components

- **PostgreSQL** — structured evidence metadata and versioned results
- **Neo4j** — evidence and publication lineage
- **Qdrant** — hybrid dense + sparse retrieval
- **MinIO** — immutable raw source payloads and documents
- **PubMed / NCBI E-utilities** — initial literature ingestion source
- **ClinicalTrials.gov API v2** — planned additional evidence source
- **Biomedical embeddings** — domain-tuned models such as PubMedBERT/BioBERT-based embeddings
- **Table-aware document parsing** — for extracting structured clinical/statistical information
- **Local/hosted LLM routing** — determined by data sensitivity
- **Spec-Kit** — specification, planning, task generation, and analysis workflow

### Evidence ingestion

The planned PubMed workflow is:

```text
Research Topic
     │
     ▼
PubMed esearch
     │
     ▼
PMID set
     │
     ▼
PubMed efetch
     │
     ▼
XML parsing
     │
     ▼
Provenance Validation
     │
     ├── Incomplete → UNKNOWN / flagged
     │
     └── Valid
           │
           ├── PostgreSQL metadata
           ├── Neo4j lineage
           ├── Qdrant embeddings
           └── MinIO raw payload
```

The ingestion design explicitly considers NCBI rate limits, API-key usage, pagination, and the History Server for queries that exceed a single-result window.

### Hybrid retrieval

Retrieval combines:

- dense semantic similarity,
- sparse/keyword matching,
- graph-based lineage information.

This is important for oncology because queries may contain both semantic concepts and exact identifiers such as:

- mutation nomenclature,
- drug names,
- trial identifiers,
- biomarkers,
- gene variants.

The platform is designed to avoid relying on semantic similarity alone.

### Four-state query resolution

A key design feature is that "no search results" is not treated as a sufficient conclusion.

```text
                 Query
                   │
                   ▼
           State Classifier
                   │
       ┌───────────┼────────────┐
       ▼           ▼            ▼
 Not Investigated  Unknown   Investigated
       │                         │
       ▼                         ▼
 Live Ingestion              Retrieval
       │                         │
       └──────────────┬──────────┘
                      ▼
              Final evidence state
```

This separates:

- "we have never investigated this topic",
- "we investigated but the available records are unreliable/unknown",
- "we investigated and found no matching evidence",
- "relevant evidence is available".

### Deterministic evidence weighting

The playbook proposes a versioned weighting rubric. The starting evidence-tier coefficients specified in the implementation prompts are:

| Evidence tier | Starting weight |
|---|---:|
| Phase III trial | 50% |
| Meta-analysis | 25% |
| Phase II trial | 20% |
| Case report | 3% |
| Expert opinion | 2% |

These values are intended to be implemented through a documented, versioned rubric rather than dynamically chosen by an LLM. The project plan also requires statistical significance, sample size, recency, regulatory status, and study design to be represented in the weighting logic.

> These are **design-stage coefficients in the Spec-Kit playbook**, not a claim that they constitute a clinically validated scientific standard.

### Spec-Kit workflow

Each phase follows:

```text
/specify
    │
    ▼
/plan
    │
    ▼
/tasks
    │
    ▼
Implementation
    │
    ▼
/analyze
```

The playbook explicitly requires `/speckit.analyze` after every phase to detect architectural or specification drift early.

---

# Spec-Driven Development

These projects demonstrate an SDD workflow where implementation is driven by explicit specifications instead of being designed entirely inside source code.

Typical artefacts include:

```text
Constitution
    │
    ▼
Specification
    │
    ▼
Research / Decisions
    │
    ▼
Implementation Plan
    │
    ▼
Tasks
    │
    ▼
Implementation
    │
    ▼
Analysis / Validation
```

This approach is particularly useful for AI systems because it makes important behaviour explicit:

- agent responsibilities,
- retrieval contracts,
- data models,
- security rules,
- failure modes,
- model boundaries,
- audit requirements,
- human approval points,
- evaluation criteria.

---

# Engineering Themes Demonstrated

Across the two projects, the repository demonstrates experience with:

- Generative AI application architecture
- Agentic workflows
- Retrieval-Augmented Generation (RAG)
- Hybrid dense + sparse retrieval
- Reciprocal Rank Fusion (RRF)
- Vector databases
- Document ingestion and OCR
- Local LLM deployment
- GPU-aware inference
- Provenance and citation tracking
- Role-based access control
- Human-in-the-loop AI
- Audit logging
- Policy/version management
- API-driven ingestion
- Structured evidence modelling
- Spec-Driven Development
- Architecture Decision Records
- Docker-based infrastructure
- FastAPI and React/TypeScript

---

# Project Status

| Project | Status |
|---|---|
| Prior Authorization Evidence Assistant | Active implementation / validation |
| Oncology Evidence Retrieval | Architecture and Spec-Kit playbook stage |

The documentation intentionally distinguishes **implemented behaviour** from **planned/specification-stage behaviour** so the repository does not overstate project maturity.

---

## Author

**Jomal Sanish**

Computer Science Engineering

This repository is maintained as a technical portfolio demonstrating practical software engineering, AI/RAG architecture, and Spec-Driven Development.
