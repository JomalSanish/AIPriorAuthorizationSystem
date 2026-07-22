# Tasks: React UI Prior Auth Dashboard

**Input**: Design documents from `/specs/004-react-ui-dashboard/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/api-spec.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Frontend project initialization and file structure setup

- [x] T001 Initialize React SPA folder structure in frontend/ src/ components/ and services/
- [x] T002 Initialize Vite React JavaScript project configuration in frontend/package.json
- [x] T003 Configure Tailwind CSS and Lucide icons in frontend/tailwind.config.js and frontend/src/index.css
- [x] T004 Configure local API proxy redirect rule in frontend/vite.config.js

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish local API server to expose existing multi-agent backend pipelines

**⚠️ CRITICAL**: No user story implementation can begin until these endpoints are verified

- [x] T005 Create FastAPI application instance in api.py with CORS middleware support
- [x] T006 Implement serializable Pydantic model schemas matching state/session_state.py attributes in api.py
- [x] T007 Implement GET /api/cases endpoint in api.py returning mock loaded sessions from app.py

---

## Phase 3: User Story 1 - Ingestion & Demographics (Priority: P1) 🎯 MVP

**Goal**: Ingest patient clinical records (PDF/TXT) and extract clinical/demographic details

**Independent Test**: Drag and drop notes, submit override, verify demographic cards populate, stepper advances to step 2.

- [x] T008 [P] [US1] Create API endpoint POST /api/cases/ingest in api.py supporting file uploads and custom demographics inputs
- [x] T009 [US1] Integrate POST /api/cases/ingest with IntakeAgent and EvidenceAgent run loops in api.py
- [x] T010 [P] [US1] Create file drag-and-drop zone with inline upload progress bar in frontend/src/components/IngestionPanel.jsx
- [x] T011 [US1] Create Patient Identity & Billing Provider card view in frontend/src/components/DemographicsCard.jsx
- [x] T012 [US1] Bind demographics manual overrides and Run Agentic Pipeline action button to ingest endpoint in frontend/src/components/IngestionPanel.jsx
- [x] T013 [US1] Verify User Story 1 end-to-end: uploading a mock case moves stepper to Step 2 and populates demographics context

---

## Phase 4: User Story 2 - Policy Criteria Split Verification (Priority: P1)

**Goal**: Verify retrieved policy criteria against clinical documents side-by-side

**Independent Test**: Expand checklist accordions, view step-by-step reasoning, check yellow-highlighted patient notes vs criteria.

- [x] T014 [P] [US2] Create API endpoint POST /api/cases/gap-analysis in api.py executing GapAgent to fetch matched checklist criteria
- [x] T015 [P] [US2] Create Side-by-Side vertical split view layout in frontend/src/components/SplitView.jsx
- [x] T016 [US2] Create expandable Checklist Accordions rendering status badges (PRESENT/ABSENT/UNCLEAR) and LLM reasoning in frontend/src/components/PolicyChecklist.jsx
- [x] T017 [US2] Implement soft-yellow text segment highlighting using citation coordinates in frontend/src/components/SplitView.jsx
- [x] T018 [US2] Bind checklist item click handler to toggle vertical split view displaying active passage highlight in frontend/src/components/PolicyChecklist.jsx
- [x] T019 [US2] Verify User Story 2 end-to-end: checklist accordion selection coordinates vertical split-view text highlights

---

## Phase 5: User Story 3 - Action Triage & Compliance Ledger (Priority: P2)

**Goal**: Complete final clinical audit brief review, edit correspondence, route decisions, and sign audit trails

**Independent Test**: Proceed to step 3, modify letter draft, submit decision, view compliance row details in bottom ledger.

- [x] T020 [P] [US3] Create API endpoint POST /api/cases/summarize in api.py running SummaryAgent and AuditAgent
- [x] T021 [P] [US3] Create API endpoint POST /api/cases/triage in api.py updating case status, routing queue, and appending audit log strings
- [x] T022 [US3] Implement Case Summary markdown layout and styled editable outreach correspondence textarea in frontend/src/components/TriagePanel.jsx
- [x] T023 [US3] Implement auto-append list of missing records when criteria status is ABSENT or UNCLEAR in frontend/src/components/TriagePanel.jsx
- [x] T024 [US3] Implement triage routing buttons (Nurse Review Queue, Request More Info, Medical Director Escalate) in frontend/src/components/TriagePanel.jsx
- [x] T025 [US3] Implement collapsible Bottom Compliance Trail drawer rendering log timeline table in frontend/src/components/ComplianceDrawer.jsx
- [x] T026 [US3] Verify User Story 3 end-to-end: submitting triage appends timestamped row with SHA-256 hash signatures to the compliance ledger drawer

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end testing, visual styling refinements, and codebase cleanup

- [x] T027 [P] Implement automated FastAPI backend integration test cases in tests/test_api.py
- [x] T028 Implement step focus overlays and disable animations in frontend/src/App.jsx
- [x] T029 Refine modern dark styling elements, transitions, and hover micro-animations in frontend/src/index.css
- [x] T030 Validate full workflow checklist against quickstart.md validation instructions
