# Tasks: Persistent Hybrid Policy Document Search

**Input**: Design documents from `/specs/005-hybrid-policy-search/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions
- Tasks involving Python implementation MUST include explicit type hints.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Initialize indices storage directories `data/indices/` and ensure they are untracked by Git via `.gitignore`
- [ ] T002 Verify project dependencies (`faiss-cpu`, `langchain-community`, `pypdf`, `rank_bm25`) are importable inside the virtual environment

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core utilities and interfaces that MUST be complete before user stories can run

- [ ] T003 [P] Extend `utils/vector_store.py` with initial placeholder type declarations for policy indices and load methods
- [ ] T004 Create `scripts/verify_hybrid_search.py` stub to test CLI execution structure

---

## Phase 3: User Story 1 - Policy Document Ingestion & Persistent Indexing (Priority: P1) 🎯 MVP

**Goal**: Ingest PDF guidelines and save their searchable index persistently to disk.

**Independent Test**: Run ingestion script and inspect `data/indices/policies_faiss/` and `data/indices/policies_bm25.pkl` folders for output files.

### Implementation for User Story 1

- [ ] T005 [P] [US1] Create the ingestion utility script in `utils/ingest_policies.py` using `pypdf` to extract text pages and split them using `RecursiveCharacterTextSplitter`.
- [ ] T006 [US1] Implement persistent saving code in `utils/ingest_policies.py` using `FAISS.save_local` and pickling the list of documents for BM25.
- [ ] T007 [US1] Run a test run of `python utils/ingest_policies.py` and confirm files are saved in `data/indices/`.

---

## Phase 4: User Story 2 - Hybrid Semantic and Keyword Policy Retrieval (Priority: P1)

**Goal**: Query persistent FAISS and BM25 indices and combine results using RRF/Weighted Scoring. Integrate this into the agent pipeline.

**Independent Test**: Verify CPT search and fuzzy query search return matching documents using the verification CLI.

### Implementation for User Story 2

- [ ] T008 [P] [US2] Implement the `HybridPolicyRetriever` in `utils/vector_store.py` to retrieve documents from both the persistent FAISS vector index and BM25 index and blend their scores.
- [ ] T009 [US2] Implement CPT code priority routing: if a query matches an exact CPT code in metadata, return it directly.
- [ ] T010 [US2] Implement the verification CLI script `scripts/verify_hybrid_search.py` using the `HybridPolicyRetriever` and verify queries work.
- [ ] T011 [US2] Refactor `agents/evidence_agent.py` to replace mock JSON policies lookup with the hybrid policy lookup against the persistent index.
- [ ] T012 [US2] Refactor `agents/gap_agent.py` and `app.py` as needed to map session state attributes of the resolved policy documents.

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup, testing, and validations

- [ ] T013 Update type hints across all modified Python files (`utils/vector_store.py`, `agents/evidence_agent.py`, etc.) and ensure they pass.
- [ ] T014 Run validation scenarios in `specs/005-hybrid-policy-search/quickstart.md`
- [ ] T015 Run the complete pytest test suite `pytest tests/test_pipeline.py` and resolve any failing tests.
