# Feature Specification: Unified Prior Auth Flow & Mock Policy Ground Truth

**Feature Branch**: `[003-unified-prior-auth-flow]`

**Created**: 2026-07-09

**Status**: Draft

**Input**: User description: "I am building a Spec-Driven 'Healthcare Payer Prior Authorization Evidence Assistant' using RAG and a 5-Agent Architecture... Objective: 1. A Mock Policy JSON Database (ground truth). 2. A Streamlined UI/UX Architecture (unified, linear, single-pane workflow)... look at the current implementation and create a spec list to add these or fix."

## Constitution Alignment

- The solution MUST use Python and a Streamlit UI whenever a user-facing workflow is required.
- The solution MUST use LangChain-based multi-agent routing when a multi-agent architecture is part of the feature.
- All Python files MUST include explicit type hints.
- Prototype work MUST use the available local evidence source and in-memory state unless persistence is explicitly requested.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Single-Pane Ingestion & Submission (Priority: P1)

As an Intake Coordinator, I want to use a unified drag-and-drop ingestion interface with direct clinical form inputs, so that I can submit provider prior authorization payloads and launch the agentic analysis pipeline in a single screen.

**Why this priority**: Core entry point. Replacing multi-role tabs with a single unified ingestion pane ensures high operational efficiency and immediate processing.

**Independent Test**: Can be tested by filling out CPT 72148, uploading a clinical note, and clicking "Run AI Pipeline" on the dashboard. The dashboard must immediately display the active case data without reloading tabs.

**Acceptance Scenarios**:

1. **Given** a new provider request, **When** the coordinator drags a clinical note PDF and clicks "Run AI Pipeline", **Then** the system extracts patient details and initializes the case in-memory.
2. **Given** an incomplete submission with missing Member ID, **When** the pipeline runs, **Then** the system flags the missing ID as absent in the dashboard's status panel.

---

### User Story 2 - Side-by-Side RAG Guideline Verification (Priority: P1)

As a Nurse Reviewer, I want to view the extracted clinical documentation side-by-side with the retrieved ground truth medical policies, so that I can instantly verify source-attributed prerequisites.

**Why this priority**: Critical to the human-in-the-loop evidence workflow. Side-by-side mapping allows immediate comparison without hopping between external tools or tabs.

**Independent Test**: Can be tested by running the pipeline for CPT 27447 (Knee Replacement) and checking that the "RAG Verification Panel" has a left-hand column displaying extracted clinical parameters and a right-hand column displaying retrieved medical criteria from the Mock Policy JSON.

**Acceptance Scenarios**:

1. **Given** a successful RAG search, **When** the verification panel renders, **Then** the policy prerequisites (e.g., Kellgren-Lawrence radiographic grading) are displayed next to the matching clinical sentences extracted from the provider's notes.

---

### User Story 3 - Interactive Gap Analysis & HITL Action Triage (Priority: P1)

As a Nurse Reviewer, I want to inspect a dynamic gap analysis checklist and review the pre-populated provider response draft before routing the case, so that I can proceed, request missing documents, or escalate.

**Why this priority**: The key operational decision panel. Enables the clinician to edit correspondence and finalize routing in a single-pane flow.

**Independent Test**: Can be verified by executing a case that lacks physical therapy notes, confirming that the checklist flags "Conservative Physical Therapy" as "Absent", pre-populates an editable letter requesting the missing PT notes, and exposes three routing buttons.

**Acceptance Scenarios**:

1. **Given** a gap checklist containing "Absent" criteria, **When** the Nurse Reviewer views the action panel, **Then** the communication editor pre-populates a neutral letter listing the specific missing criteria.
2. **Given** a case with clinical ambiguities, **When** the Nurse Reviewer clicks "Escalate to Medical Director", **Then** the case is routed to the Medical Director queue and logged in the audit trail.

---

### User Story 4 - Ground Truth Policy Database Verification (Priority: P2)

As a Payer Operations Administrator, I want the system to reference a mock policy JSON file rather than static local PDFs, so that prior authorization guidelines for Lumbar MRI, Adalimumab, and Knee Replacement are easily updated and structured.

**Why this priority**: Improves reliability of the RAG and Gap agents by substituting unstructured PDF parsing with structured schema matching.

**Independent Test**: Can be verified by updating a prerequisite in the mock JSON file and confirming that subsequent pipeline runs immediately reflect the new prerequisite in the checklist and extracted gaps.

**Acceptance Scenarios**:

1. **Given** a JSON file with 3 mock policies, **When** the RAG Agent receives CPT 96372 (Adalimumab), **Then** it retrieves the structured criteria (Rheumatologist sign-off, trial of 2 DMARDs) from the JSON file.

---

### Edge Cases

- **Unregistered CPT Codes**: If a submission contains a CPT code not present in the Mock Policy JSON, the RAG Agent must return a friendly error and route the case to manual intake review.
- **Malformed Provider JSON**: If the uploaded JSON payload fails schema validation, the Intake Agent must flag it as an ingestion error without crashing the dashboard.
- **Contradictory Clinical Text**: If the notes mention both "patient completed 6 weeks of PT" and "no physical therapy attempted," the Gap Agent must label the status of that item as `UNCLEAR` and pre-populate an explanation in the communication draft.

## Requirements _(mandatory)_

### Functional Requirements

#### 1. Mock Policy & Case Data Specification
- **FR-001**: The system MUST read prior authorization ground truth policies from a structured file: `data/mock_policies.json`.
- **FR-002**: The `data/mock_policies.json` database MUST define rules for at least 3 distinct clinical cases:
  1. **Lumbar Spine MRI** (CPT: 72148): Requires CPT 72148, ICD-10 M54.5, clinical notes confirming low back pain radiating down the leg, and proof of >= 6 weeks of conservative physical therapy or drug trial (NSAIDs).
  2. **Specialty Drug - Adalimumab** (CPT: 96372 / HCPCS: J0135): Requires moderate-to-severe Rheumatoid Arthritis or Plaque Psoriasis, prescription by a Rheumatologist or Dermatologist, and trial/failure of at least 2 conventional DMARDs (e.g. methotrexate, sulfasalazine) for at least 3 months each.
  3. **Total Knee Arthroplasty** (CPT: 27447): Requires ICD-10 M17.11 (advanced osteoarthritis), radiology report confirming Kellgren-Lawrence Grade 3 or 4, joint pain score (WOMAC/KOOS) confirming severe functional limitation, and >= 12 weeks of non-surgical conservative therapy notes.
- **FR-003**: The system MUST support a structured Provider Submission payload schema for automated API ingestion containing:
  - `submission_id`, `patient_info` (member_id, first_name, last_name, date_of_birth), `provider_info` (provider_id, name, specialty), `clinical_metadata` (cpt_code, icd_code, requested_service, requested_date), and `documents` array (each with `document_type`, `filename`, and `extracted_text`).

#### 2. Agent Logic Refactoring
- **FR-004**: The Intake Agent MUST parse the Provider Submission JSON payload (or form inputs) and extract the patient data, CPT, and ICD-10 code.
- **FR-005**: The Evidence (RAG) Agent MUST use Semantic Vector Search rather than basic string matching to evaluate clinical notes against policy prerequisites. The agent must embed both the policy criteria and the chunks of the provider's clinical notes to calculate cosine similarity scores, ensuring that synonymous phrasing (e.g., "tried methotrexate" vs "DMARD trial") is successfully matched. It MUST employ a vector store (e.g., in-memory FAISS) and standard embeddings (e.g. OpenAIEmbeddings) to retrieve matching note passages.
- **FR-006**: The Policy Gap Agent MUST evaluate each clinical prerequisite and required document independently in an isolated manner, executing a strict step-by-step Chain-of-Thought reasoning process *before* resolving its status:
  - `PRESENT`: The requirement is explicitly stated in the clinical evidence text.
  - `ABSENT`: The requirement is neither mentioned nor implied anywhere in the clinical notes. (e.g. if the note has no mention of "conservative therapy", the status must be resolved as `ABSENT`).
  - `UNCLEAR`: Contradictory notes exist, or a trial/treatment is mentioned but lacks required details like duration or specific dates.
- **FR-006a**: The Gap Agent MUST NOT use hardcoded criteria or fallback to the first index of the policy database. It MUST dynamically accept the exact `clinical_prerequisites` array and `required_documents` array that were successfully retrieved by the Evidence/RAG Agent for the specific CPT code.
- **FR-007**: The Summary Agent MUST generate a neutral communication letter pre-populated with text requesting details for any checklist item marked `ABSENT` or `UNCLEAR`.

#### 3. Streamlined UI Architecture & Flow
- **FR-008**: The Streamlit UI MUST use a "Progressive Stepper with a Persistent Context Sidebar" architecture:
  - **Persistent Context Sidebar**: On case initiation or document upload, locks the core case metadata, patient demographics, CPT/ICD-10, and a text expander of the complete uploaded clinical notes in the sidebar. This sidebar MUST be visible throughout all steps.
  - **Progressive Stepper**: The main area renders step-specific panels controlled by `st.session_state.current_step` (initialized to 1).
    - **Step 1 (Ingestion & Upload)**: Displays the file uploader and manual data entry forms.
    - **Step 2 (RAG Verification & Gap Analysis)**: Displays the side-by-side extracted data vs policy text panel, and the Gap Analysis Checklist.
    - **Step 3 (Actionable Decision Dashboard & Summary)**: Displays the clinical summary brief, editable draft letter area, final routing buttons, and the audit telemetry logs.
- **FR-009**: The UI step transitions MUST follow these logic constraints:
  - Step 1 $\rightarrow$ Step 2: Triggered by "Run AI Evidence Pipeline". Executes the Intake & Evidence Agents, sets `current_step = 2`, and refreshes UI.
  - Step 2 $\rightarrow$ Step 3: Triggered by "Generate Summary & Route". Executes the Gap & Summary Agents, sets `current_step = 3`, and refreshes UI.
  - Step 3 $\rightarrow$ Step 2: Triggered by "Back to Evidence". Returns to Step 2 by setting `current_step = 2` to review checklist items.
  - Triage Decisions: Clicking `[Proceed/Route to Nurse]`, `[Reject/Request Missing Docs]`, or `[Escalate to Medical Director]` executes the Audit Agent, updates case status, saves correspondence, and updates queues.

### Key Entities

- **MockPolicy**: Ground truth policy record. Attributes: `cpt_code`, `service_name`, `specialty_requirement`, `clinical_prerequisites` (list of rules), `required_documents` (list of document types).
- **ProviderSubmission**: Input JSON structure. Attributes: `submission_id`, `patient_info` (dict), `provider_info` (dict), `clinical_metadata` (dict), `documents` (list).
- **GapChecklist**: Evaluated checklist. Attributes: `criteria` (string), `status` (PRESENT/ABSENT/UNCLEAR), `evidence_text` (excerpt), `citation` (source file/page), `rationale` (text).

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: 100% of pipeline executions display the ingestion metadata, RAG verification text, and gap analysis checklist in a single vertical page scroll without tab navigation.
- **SC-002**: The RAG Agent correctly retrieves relevant clinical rules from `data/mock_policies.json` for 100% of cases using CPT codes 72148, 96372, and 27447.
- **SC-003**: The Gap Agent flags missing documents with 100% accuracy matching the defined mock policy requirements.
- **SC-004**: The draft communication text area in the dashboard pre-populates with specific missing document names when checklist items are marked `ABSENT`.

## Assumptions

- **JSON Fallback**: If `data/mock_policies.json` is missing or corrupted, the system will fall back to using default hardcoded dict objects for the three standard cases to prevent runtime crashes.
- **In-Memory Store**: Cases and review queue state are stored in Streamlit's `st.session_state` and are persistent only within the user session.
