# Tasks: Prior Authorization Evidence Assistant

**Input**: Design documents from /specs/001-prior-authorization-evidence-assistant/

**Prerequisites**: plan.md, spec.md, research.md, data-model.md

## Phase 1: Setup

- [X] T001 Create the Python project structure for the Streamlit app and agent modules
- [X] T002 Create requirements.txt with Streamlit, LangChain, LangChain Core, Pydantic, PyPDF, and pytest
- [X] T003 [P] Create the initial package files for agents, state, and utils

## Phase 2: Foundational

- [X] T004 Implement the shared SessionState dataclass and typed helper models in state/session_state.py
- [X] T005 Implement PDF extraction utilities in utils/pdf_utils.py
- [X] T006 Implement text normalization and matching helpers in utils/text_utils.py
- [X] T007 Create the application entry point in app.py with Streamlit layout scaffolding

## Phase 3: User Story 1 - Intake and Classification

**Goal**: Parse incoming PA requests and classify them into request type and urgency.

**Independent Test**: A sample request can be submitted and the UI shows a classification result.

### Implementation

- [X] T008 Implement the Intake & Classification agent in agents/intake_agent.py
- [X] T009 Wire the intake agent into the main pipeline in app.py
- [X] T010 Add a basic test for classification behavior in tests/test_pipeline.py

## Phase 4: User Story 2 - Evidence Retrieval

**Goal**: Retrieve relevant policy evidence from the local PDF for the request.

**Independent Test**: A sample request returns retrieved policy passages and citations.

### Implementation

- [X] T011 Implement the Evidence Retrieval agent in agents/evidence_agent.py
- [X] T012 Connect the evidence agent to the shared SessionState and pipeline flow
- [X] T013 Add a test covering evidence retrieval from the PDF in tests/test_pipeline.py

## Phase 5: User Story 3 - Gap Analysis and Summary

**Goal**: Assess missing information and draft reviewer-facing output.

**Independent Test**: The app produces gap analysis and a reviewer summary for a sample request.

### Implementation

- [X] T014 Implement the Policy Reasoning & Gap agent in agents/gap_agent.py
- [X] T015 Implement the Reviewer Summary & Communication agent in agents/summary_agent.py
- [X] T016 Wire the gap and summary agents into the pipeline and update the UI content
- [X] T017 Add a test for gap analysis and summary generation in tests/test_pipeline.py

## Phase 6: User Story 4 - Audit and UI Completion

**Goal**: Finalize the workflow state and present the result in the Streamlit dashboard.

**Independent Test**: The UI shows the audit trail, final status, and generated artifacts after running the pipeline.

### Implementation

- [X] T018 Implement the Workflow Audit & Readiness agent in agents/audit_agent.py
- [X] T019 Render classification, evidence, gaps, summary, and status in the Streamlit UI
- [X] T020 Add a final end-to-end test for the pipeline and UI state wiring in tests/test_pipeline.py

## Phase 7: Polish

- [X] T021 Refine the UI copy and formatting for the prototype experience
- [X] T022 Run the app locally and verify the sample workflow end to end
