# Implementation Plan: Persistent Hybrid Policy Document Search

**Branch**: `005-hybrid-policy-search` | **Date**: 2026-07-18 | **Spec**: [spec.md](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/specs/005-hybrid-policy-search/spec.md)

## Summary
Implement a persistent hybrid search (FAISS dense vector + BM25 sparse keyword) to index clinical policy PDFs and query them dynamically during prior authorization reviews. This replaces/augments the hardcoded JSON policy lookup with a production-grade, file-based index retriever.

## Technical Context

- **Language/Version**: Python 3.11+
- **Primary Dependencies**: `faiss-cpu`, `langchain`, `langchain-community`, `langchain-openai`, `pypdf`, `rank_bm25`
- **Storage**: Persistent local files (`data/indices/policies_faiss/` and `data/indices/policies_bm25.pkl`)
- **Testing**: `pytest tests/test_pipeline.py`
- **Target Platform**: Desktop Streamlit/FastAPI Application
- **Project Type**: Web service backend / agent pipeline

## Constitution Check

- The implementation MUST use Python and a Streamlit-based UI for any user-facing workflow. **[PASSED]**
- The implementation MUST use LangChain-based multi-agent routing when multi-agent orchestration is required. **[PASSED]**
- All Python files MUST include explicit type hints. **[PASSED]**
- The prototype MUST rely on the available local policy PDF and in-memory state unless persistence is explicitly introduced. **[PASSED - Persistence is explicitly requested for this feature]**

## Project Structure

### Documentation (this feature)
```text
specs/005-hybrid-policy-search/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Technology choices and research
├── data-model.md        # Data models and structures
└── quickstart.md        # Validation scenarios
```

### Source Code changes
```text
utils/
├── ingest_policies.py   # [NEW] Policy PDF ingestion script
├── vector_store.py      # [MODIFY] Added persistent FAISS and hybrid search helpers
agents/
├── evidence_agent.py    # [MODIFY] Integrate hybrid search for policy retrieval
scripts/
├── verify_hybrid_search.py # [NEW] Testing utility for hybrid queries
```

---

## Proposed Changes

### Ingestion Component

#### [NEW] [ingest_policies.py](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/utils/ingest_policies.py)
Create a script to load PDFs from `data/guidelines/`, chunk them, generate embeddings, and serialize both FAISS and BM25 indices to disk.

### Vector Store Helper

#### [MODIFY] [vector_store.py](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/utils/vector_store.py)
Extend the module with:
- `load_persistent_policy_store()`: Load indices from disk.
- `HybridPolicyRetriever` class or helper function: Execute BM25 and FAISS queries, score, and rank them using Weighted Fusion.

### Agent Logic

#### [MODIFY] [evidence_agent.py](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/agents/evidence_agent.py)
Integrate the persistent hybrid retriever. Instead of direct JSON CPT checking, retrieve context segments from the persistent policy index.

### Verification CLI

#### [NEW] [verify_hybrid_search.py](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/scripts/verify_hybrid_search.py)
A CLI script to run isolated hybrid search queries and display matching score segments.

---

## Verification Plan

### Automated Tests
- Run `pytest tests/test_pipeline.py` to ensure zero regressions in intake/evidence/gap agents.

### Manual Verification
- Ingest policy PDFs using `python utils/ingest_policies.py`.
- Query exact CPT codes and verify that correct passages are retrieved.
- Query semantic synonyms (e.g. "radiology joint replacement") and check returned context.
