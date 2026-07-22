# Tasks: Payer Prior Authorization Evidence Assistant

**Input**: Design documents from `/specs/002-payer-prior-auth/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions
- Tasks involving Python implementation MUST include explicit type hints and any required Streamlit or LangChain integration work

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project environment setup and initialization

- [x] T001 Update dependencies in `requirements.txt` to include `langchain-openai`, `pypdf`, `faiss-cpu`, and `python-dotenv`
- [x] T002 [P] Configure API keys and settings in `.env` file

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core state and helper models required for all agents

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Implement structured SessionState class in `state/session_state.py` including routing queues and metadata fields
- [x] T004 [P] Implement document reader and chunking utilities in `utils/pdf_utils.py` using `pypdf`
- [x] T005 [P] Implement RAG vector store wrapper in `utils/vector_store.py` for indexing and search

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Intake Case Creation & Completeness (Priority: P1) 🎯 MVP

**Goal**: Ingest prior authorization requests and determine if the submission is complete

**Independent Test**: Enter demographics and CPT code, check that the status updates to "Ready for Evidence Review" and missing metadata is correctly identified.

### Implementation for User Story 1

- [x] T006 [US1] Implement Intake Agent in `agents/intake_agent.py` to parse clinical text and classify request type/urgency
- [x] T007 [US1] Create the document ingestion and upload UI tab in `app.py`
- [x] T008 [US1] Add intake metadata validation logic and error logging in `app.py`

**Checkpoint**: User Story 1 is functional. New cases can be created, validated, and listed on the dashboard.

---

## Phase 4: User Story 2 - RAG-based Evidence Retrieval & Policy Mapping (Priority: P1)

**Goal**: Retrieve relevant policy guidelines from policy documents and display them with source citations

**Independent Test**: Run a Lumbar MRI Spine case and confirm that guideline excerpts are retrieved and printed with page citations.

### Implementation for User Story 2

- [x] T009 [US2] Implement Evidence Agent in `agents/evidence_agent.py` to query the vector index and retrieve relevant guidelines
- [x] T010 [US2] Integrate the retrieved evidence list view into the Nurse Review tab in `app.py`
- [x] T011 [P] [US2] Update tests in `tests/test_pipeline.py` to verify RAG query results and citations

**Checkpoint**: User Story 2 is functional. Policy evidence is automatically retrieved and linked to case reviews.

---

## Phase 5: User Story 3 - Policy Gap Analysis & Checklist Generation (Priority: P2)

**Goal**: Compare clinical notes against guidelines and render a criteria compliance checklist

**Independent Test**: Submit a case without PT documentation and verify the checklist flags "6 weeks conservative therapy" as Absent.

### Implementation for User Story 3

- [x] T012 [US3] Implement Gap Agent in `agents/gap_agent.py` to extract checklist items and identify criteria compliance using ChatOpenAI
- [x] T013 [US3] Create checklist visual cards and gap reasoning UI blocks in the Nurse Review tab in `app.py`
- [x] T014 [P] [US3] Add unit test in `tests/test_pipeline.py` verifying gap analysis status and missing criteria extraction

**Checkpoint**: User Story 3 is functional. Gaps are extracted and displayed as a clear criteria checklist.

---

## Phase 6: User Story 4 - Summary & Communication Drafts (Priority: P2)

**Goal**: Automatically compile markdown clinical briefs and provider communications

**Independent Test**: Verify that a case generates a formatted markdown brief and a template requesting missing information.

### Implementation for User Story 4

- [x] T015 [US4] Implement Summary Agent in `agents/summary_agent.py` to compose briefs and neutral communications using ChatOpenAI
- [x] T016 [US4] Add editable clinical brief and provider letter text components in the Nurse/Director tabs of `app.py`
- [x] T017 [P] [US4] Add integration test in `tests/test_pipeline.py` verifying summary formats match the gap status

**Checkpoint**: User Story 4 is functional. Case summaries and draft communications are automatically generated.

---

## Phase 7: User Story 5 - Queue Routing & Audit Trail (Priority: P3)

**Goal**: Route cases to appropriate user queues and compile compliance audit trails

**Independent Test**: Verify the Auditor queue lists agent step details and a valid SHA-256 compliance hash.

### Implementation for User Story 5

- [x] T018 [US5] Implement Audit Agent in `agents/audit_agent.py` to finalize case runs and calculate verification hashes
- [x] T019 [US5] Implement tabs for Intake, Nurse, Director, Auditor, Manager queues with custom layouts in `app.py`
- [x] T020 [P] [US5] Add verification tests in `tests/test_pipeline.py` checking audit path logs and compliance hashing

**Checkpoint**: User Story 5 is functional. Multiple roles can process cases across their respective queues.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Aesthetic improvement, code cleanliness, and validation

- [x] T021 Apply sleek stylesheet rules, fonts, and dark glassmorphic cards in `app.py`
- [x] T022 Run all tests using `pytest` and verify success
- [x] T023 Run manual verification scenarios per `quickstart.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion. Blocks all user stories.
- **User Stories (Phases 3-7)**: Depend on Foundational completion. Can be worked on sequentially or in parallel.
- **Polish (Phase 8)**: Depends on all User Stories being complete.

### Parallel Opportunities

- All Setup tasks (`T001`-`T002`) can run in parallel.
- Foundational helper tasks (`T004`-`T005`) can run in parallel.
- Unit tests (`T011`, `T014`, `T017`, `T020`) can be written in parallel with dashboard UI tasks.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup (`T001`-`T002`) and Foundation (`T003`-`T005`).
2. Implement Intake Agent and Case Creation UI (`T006`-`T008`).
3. Verify case ingestion works end-to-end before implementing retrieval.

### Incremental Delivery

1. Ingest Case (US1) -> Foundational.
2. Retrieve Guidelines (US2) -> Evidence viewable.
3. Reason Gaps (US3) -> Checklist viewable.
4. Auto-summarize (US4) -> Briefs ready.
5. Compliance Routing (US5) -> Queues active.
