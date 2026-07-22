# Implementation Plan: Payer Prior Authorization Evidence Assistant

**Branch**: `002-payer-prior-auth` | **Date**: 2026-07-08 | **Spec**: [spec.md](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/specs/002-payer-prior-auth/spec.md)

## Summary

The project is to build a healthcare payer prior authorization triage assistant using a 5-agent LangChain workflow, RAG vector retrieval, and an interactive multi-tab Streamlit dashboard. The assistant helps reviewers retrieve policy evidence, identify criteria gaps, and route tasks without making automated final approval decisions.

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: `streamlit`, `langchain`, `langchain-openai`, `pypdf`, `faiss-cpu` or in-memory vector similarity helper, `python-dotenv`, `pytest`

**Storage**: In-memory FAISS/Chroma vector database (populated from uploaded PDFs and the local guideline PDF) and in-memory session state.

**Testing**: `pytest` for validation and unit/pipeline tests.

**Target Platform**: Python environment / Streamlit Web Interface.

**Project Type**: Web Application / Multi-agent system.

**Performance Goals**: Complete pipeline execution in under 5 seconds (excluding API call network latency).

**Constraints**: Must run with standard OpenAI API key configured via `.env` file or direct UI input; must adhere to strict type safety.

**Scale/Scope**: 5 specialized agents, 6 dashboard views (Common Upload + 5 User Queue Tabs).

## Constitution Check

- **Streamlit UI**: YES (Dashboard is built using Streamlit with tab navigation for roles).
- **LangChain multi-agent routing**: YES (Uses LangChain for prompt templating and LLM orchestration).
- **Type hints**: YES (Explicit type hints across all Python modules).
- **Local evidence/in-memory state**: YES (Uses the local guidelines PDF at `data/guidelines/prior-authorization-and-step-therapy-guidelines.pdf` and in-memory Streamlit state).

## Project Structure

### Documentation (this feature)

```text
specs/002-payer-prior-auth/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── checklists/
    └── requirements.md  # Spec checklist
```

### Source Code (repository root)

```text
agents/
├── __init__.py
├── intake_agent.py       # Entity extraction and service classification
├── evidence_agent.py     # Vector RAG search on policies/case documents
├── gap_agent.py          # Checklist-based gap detection using LLM
├── summary_agent.py      # Markdown summary & communication draft generator
└── audit_agent.py        # Telemetry verification and compliance hashing

state/
├── __init__.py
└── session_state.py      # Typed datastructure for Central State payload

utils/
├── __init__.py
├── pdf_utils.py          # PDF reading and chunking (using pypdf)
└── vector_store.py       # Lightweight in-memory RAG vector index wrapper

tests/
├── __init__.py
└── test_pipeline.py      # Complete agent integration & RAG correctness tests

app.py                    # Streamlit human-in-the-loop dashboard
requirements.txt          # Python dependencies
.env                      # Environment configurations (OpenAI API key)
```

**Structure Decision**: Option 1: Single project (default). The application maintains the existing root layout with enhanced module features.

## Complexity Tracking

*No Constitution violations detected.*
