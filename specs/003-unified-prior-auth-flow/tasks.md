# Tasks: Unified Prior Auth Flow & Mock Policy Ground Truth

**Input**: Design documents from `/specs/003-unified-prior-auth-flow/`

**Prerequisites**: [plan.md](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/specs/003-unified-prior-auth-flow/plan.md) (required), [spec.md](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/specs/003-unified-prior-auth-flow/spec.md) (required), [research.md](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/specs/003-unified-prior-auth-flow/research.md), [data-model.md](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/specs/003-unified-prior-auth-flow/data-model.md)

**Tests**: Tests are generated to verify compliance and correctness of the multi-agent pipeline and verification UI flow.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions
- Tasks involving Python implementation MUST include explicit type hints and any required Streamlit or LangChain integration work

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Initialize the project folders and configurations in the workspace root
- [x] T002 Ensure dependencies are listed in `requirements.txt`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Create the policy ground-truth JSON file at `data/mock_policies.json`
- [x] T004 Define schemas and state tracking fields in `state/session_state.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Single-Pane Ingestion & Submission (Priority: P1) 🎯 MVP

**Goal**: Support provider prior authorization document upload and data ingestion using structured JSON extraction.

**Independent Test**: Execute intake parsing via the IntakeAgent test script and verify that member_id, provider_id, CPT, and ICD-10 are correctly extracted.

### Implementation for User Story 1

- [x] T005 [P] [US1] Create the provider submission input models and demographics structures in `agents/intake_agent.py`
- [x] T006 [US1] Refactor `agents/intake_agent.py` to parse provider JSON payloads and extract patient fields using LangChain structured output extraction
- [x] T007 [US1] Implement the top-level Ingestion & Upload Zone UI component in `app.py` with file upload and form fields

**Checkpoint**: User Story 1 is functional. Documents can be uploaded, parsed, and metadata is populated.

---

## Phase 4: User Story 2 - Side-by-Side RAG Guideline Verification (Priority: P1)

**Goal**: Retrieve mock policies from JSON by CPT and match them against clinical notes side-by-side.

**Independent Test**: Execute evidence retrieval for a given CPT code and verify that matching policy rules are retrieved from the JSON file and paired with notes context.

### Implementation for User Story 2

- [x] T008 [US2] Refactor `agents/evidence_agent.py` to lookup the CPT code guidelines from `data/mock_policies.json`
- [x] T009 [US2] Update `agents/evidence_agent.py` to load notes text and run similarity retrieval using in-memory FAISS/Chroma store
- [x] T010 [US2] Build the Side-by-Side RAG Verification UI panel in `app.py` displaying clinical data and policy texts side-by-side

**Checkpoint**: User Story 2 is functional. Retrieved guidelines and extracted evidence are displayed side-by-side.

---

## Phase 5: User Story 3 - Interactive Gap Analysis & HITL Action Triage (Priority: P1)

**Goal**: Analyze evidence against policy rules, flag gaps in a checklist, pre-populate correspondence, and support routing overrides.

**Independent Test**: Complete a workflow run, verify that the checklist statuses (PRESENT, ABSENT, UNCLEAR) are visible, the letter template edits are persistent, and routing queue actions update the audit trail.

### Implementation for User Story 3

- [x] T011 [US3] Refactor `agents/gap_agent.py` to evaluate evidence against policy rules using LangChain structured parsing
- [x] T012 [US3] Update `agents/summary_agent.py` to generate the clinical brief and pre-populate an editable provider correspondence draft based on checklist statuses
- [x] T013 [US3] Build the Gap Analysis Checklist UI panel in `app.py` with colored status badges
- [x] T014 [US3] Build the Human-in-the-Loop Decision Dashboard UI in `app.py` with communication text area and routing buttons
- [x] T015 [US3] Implement the AuditAgent compliance logging and audit panel in `agents/audit_agent.py` and `app.py`

**Checkpoint**: User Story 3 is functional. The full triage workflow operates in a single-pane vertical scroll interface.

---

## Phase 6: User Story 4 - Ground Truth Policy Database Verification (Priority: P2)

**Goal**: Verify that all 3 mock cases are correctly matched and evaluated.

**Independent Test**: Run integration tests for the three test cases (MRI, Adalimumab, Knee Replacement) to verify policy retrieval and gap output correctness.

### Implementation for User Story 4

- [x] T016 [P] [US4] Formulate clinical mock data for Knee Replacement, Adalimumab, and MRI cases in `data/sample_requests/`
- [x] T017 [US4] Write unit and integration tests in `tests/test_pipeline.py` verifying policy retrieval and checklist output correctness for each case

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Cleanup, testing, and final packaging of the single-pane app.

- [x] T018 Run the python test suite via `pytest tests/` to confirm all tests pass
- [x] T019 Perform manual end-to-end verification of the Streamlit app at `app.py`
- [x] T020 Run `quickstart.md` validation checklist and document success

---

## Phase 8: Progressive Stepper UI Refactoring

**Purpose**: Refactor the Streamlit dashboard layout to use progressive steps with a persistent sidebar.

- [x] T021 [US1] Create sidebar panel displays for case details, patient demographics, and full note expander in `app.py`
- [x] T022 [US1] Implement conditional step routing controls using `st.session_state.current_step` in `app.py`
- [x] T023 [US1] Build Step 1 (Ingestion & Upload) view in `app.py`, calling Intake agent and advancing `current_step = 2` on submission
- [x] T024 [US2] Build Step 2 (Verification & Gap Checklist) view in `app.py`, calling Gap & Summary agents and advancing `current_step = 3` on route
- [x] T025 [US3] Build Step 3 (HITL Dashboard & Audit Logs) view in `app.py`, with back button and horizontal routing buttons
- [x] T026 Verify the refactored UI stepper flow by running the pytest suite and manual Streamlit checks

---

## Phase 9: Policy Gap Agent Hallucination Fix

**Purpose**: Refactor `gap_agent.py` to ensure step-by-step reasoning, isolated requirement evaluations, and strict status determinations.

- [x] T027 [US3] Refactor the Pydantic models in `agents/gap_agent.py` to support step-by-step reasoning fields (`thought_process` or similar)
- [x] T028 [US3] Refactor the system prompt in `agents/gap_agent.py` to enforce independent Chain-of-Thought evaluations per rule and strict status assignments
- [x] T029 [US3] Update fallback logic in `agents/gap_agent.py` to ensure strict status matching for local keyword logic
- [x] T030 Add/update test cases in `tests/test_pipeline.py` specifically asserting `ABSENT` status for missing conservative therapy details

---

## Phase 10: Dynamic Policy Criteria Passing Fix

**Purpose**: Fix Gap Agent criteria resolution to dynamically process the prerequisites and required documents retrieved by the Evidence Agent for the specific CPT code.

- [x] T031 [US2] Update `agents/evidence_agent.py` to correctly assign the retrieved policy clinical prerequisites and required documents to specific keys in the session state object
- [x] T032 [US3] Refactor `agents/gap_agent.py` to read the dynamic criteria list from the session state object instead of using a static list or hardcoded fallback
- [x] T033 [US4] Add a `pytest` case that passes CPT 43644 through both agents sequentially to assert that the resulting checklist evaluates the BMI and psychological clearance rules, NOT the physical therapy rules

---

## Phase 11: Semantic Vector Search RAG Upgrade

**Purpose**: Upgrade Evidence Agent retrieval capabilities using Recursive text chunking, OpenAI embeddings, and FAISS indexing.

- [x] T034 [US2] Verify or append `faiss-cpu` and `tiktoken` dependencies in `requirements.txt`
- [x] T035 [US2] Refactor `agents/evidence_agent.py` to chunk notes using `RecursiveCharacterTextSplitter` and index them in FAISS using `OpenAIEmbeddings(model="text-embedding-3-small")`
- [x] T036 [US2] Update retrieval loop in `agents/evidence_agent.py` to search FAISS and filter matches based on score relevance thresholds
- [x] T037 [US2] Save matches and citations to `state.evidence` (mapped to `st.session_state` in the UI) for consumption by the Gap Agent
- [x] T038 Verify semantic RAG execution and score filtering by running pytest suite and manual Streamlit checks

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies.
- **Foundational (Phase 2)**: Depends on Phase 1. Blocks all subsequent implementation.
- **User Stories (Phase 3+)**: All depend on Phase 2.
- **Polish (Phase 7)**: Depends on all user stories being completed.

---

## Implementation Strategy

### MVP First (User Story 1 & 2)

1. Complete setup and ground-truth JSON schema in `data/mock_policies.json`.
2. Implement Intake and Evidence Agents.
3. Build the top half of the dashboard (Ingestion & side-by-side RAG panel).
4. Verify extraction works correctly.
