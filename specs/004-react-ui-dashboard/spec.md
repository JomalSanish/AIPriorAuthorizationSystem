# Feature Specification: React UI Prior Auth Evidence Dashboard

**Feature Branch**: `004-react-ui-dashboard`

**Created**: 2026-07-13

**Status**: Draft

**Input**: User description: "i want to chnge the ui to react which keeping all the logic the same. use the same functions while keeping the backend same change from streamlit to react based on this prompt"

## Constitution Alignment

- This feature migrates the user-facing web interface from a Streamlit application to a React-based application (Vite or Next.js App Router with Tailwind CSS, Lucide React, and standard state hooks).
- Upon implementation, this React-based dashboard will supersede the project's "Streamlit-First Human-in-the-Loop UI" principle (Core Principle II and associated technical constraints).
- The solution MUST maintain the same backend multi-agent logic, functions, and LangChain orchestration without modifying the backend logic interfaces.
- The solution MUST adhere to strict type safety (Python type hints on the backend, TypeScript/TypeScript-equivalent prop-types or explicit JavaScript data models on the frontend).
- Local evidence sources and in-memory session state MUST remain the defaults.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Document Ingestion & Demographics Capture (Priority: P1)

As a prior authorization reviewer, I want to upload a patient document and trigger the automated intake agent, so that patient identifiers and provider credentials are automatically extracted and verified.

**Why this priority**: Core entry point. Reviewers must be able to upload clinical records to initiate the verification pipeline.

**Independent Test**: Can be fully tested by dragging and dropping a clinical note file (PDF/TXT) and checking that demographic badges populate Column 1.

**Acceptance Scenarios**:

1. **Given** the user is on the dashboard in Step 1 (Ingestion active), **When** they drag and drop a PDF/TXT file, **Then** an inline progress bar demonstrates upload status.
2. **Given** the file upload is complete, **When** they fill the manual override form (`Member ID`, `First/Last Name`, `CPT Code`, `ICD-10 Code`) and click `[ Run Agentic Analysis Pipeline ]`, **Then** the Active Case Demographics card is dynamically populated and the wizard stepper advances to Step 2.

---

### User Story 2 - Policy Criteria Split Verification (Priority: P1)

As a prior authorization reviewer, I want to inspect each policy criterion and view the corresponding clinical note citation side-by-side, so that I can audit the AI's evidence assessment.

**Why this priority**: Most critical workflow value. The primary purpose of this dashboard is to review evidence matching.

**Independent Test**: Can be tested by clicking an accordion checklist item in Column 2 and verifying that the vertical split view displays matching highlighted clinical text on the left and raw policy rule on the right.

**Acceptance Scenarios**:

1. **Given** the wizard stepper is at Step 2, **When** the Gap Checklist renders, **Then** each item is displayed in an accordion card with color-coded status badges: `PRESENT` (green), `ABSENT` (red), `UNCLEAR` (yellow).
2. **Given** a checklist item is clicked, **When** the accordion expands, **Then** the `Step-by-Step Reasoning` text block is displayed showing the agent's Chain-of-Thought, and the column splits 50/50 vertically to show patient clinical note text with highlighted matching passages on the left and raw mock policy criteria text on the right.

---

### User Story 3 - Action Triage & Compliance Logging (Priority: P2)

As a prior authorization reviewer, I want to read the clinical narrative, review the outreach letter, and route the case with full compliance tracking, so that the workflow advances to its next state.

**Why this priority**: Essential to close the loop and record the audit trail for compliance.

**Independent Test**: Can be tested by clicking "Proceed to Route", editing the outreach draft, clicking a router button, and checking that a new entry appears in the bottom drawer compliance trail table.

**Acceptance Scenarios**:

1. **Given** the user clicks "Proceed to Route", **When** Step 3 is activated, **Then** Column 3 is unblurred, and the Case Summary and Editable Communication Draft are displayed.
2. **Given** the draft letter is populated, **When** policy criteria are marked `ABSENT` or `UNCLEAR`, **Then** the communication textarea automatically includes the specific list of missing documents/evidence.
3. **Given** the user clicks any decision router button (`Route to Nurse Review Queue`, `Request More Info / Reject`, `Escalate to Medical Director`), **When** the workflow state updates, **Then** a new row is appended to the read-only table in the collapsible bottom Compliance Trail drawer showing the action timestamp, action description, responsible agent, and SHA-256 compliance hash.

---

### Edge Cases

- **Missing Evidence Passages**: When a criterion is marked `ABSENT`, no matching citation passage exists. The left panel of the vertical split view MUST display a friendly message: "No matching passage found in clinical notes for this criteria."
- **Backend API Disconnection**: If the React frontend fails to connect to backend agent endpoints, the UI MUST display a visible error toast or header alert with a retry button to run the agent pipeline again without loss of local inputs.
- **State Loss on Refresh**: To prevent losing work, the React application should save draft UI state in standard state hooks mapped synchronously to the backend session state, so that reload retrieves the latest state.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The UI layout MUST use a three-column split: Column 1 (left 25% width), Column 2 (center 45% width), and Column 3 (right 30% width).
- **FR-002**: The header MUST display a progress stepper reflecting the `currentStep` state (1 = 'ingestion', 2 = 'analysis', 3 = 'triage').
- **FR-003**: When `currentStep` is 1 (Ingestion), Column 2 and Column 3 MUST have a light opacity overlay (disabled appearance).
- **FR-004**: Column 1 MUST contain a drag-and-drop file boundary box for PDF/TXT uploads, displaying an inline ingestion progress bar.
- **FR-005**: Column 1 MUST include manual override form inputs for `Member ID`, `First/Last Name`, `CPT Code`, and `ICD-10 Code`.
- **FR-006**: Clicking `[ Run Agentic Analysis Pipeline ]` in Column 1 MUST trigger the backend intake and policy gap agents, update demographics, shift `currentStep` to 2, and activate Column 2.
- **FR-007**: Column 2 MUST render criteria checklist items as expandable accordions with color-coded badges: `PRESENT` (🟢 green), `ABSENT` (🔴 red), and `UNCLEAR` (🟡 yellow).
- **FR-008**: Expanding a criteria accordion card MUST reveal the `Step-by-Step Reasoning` text block and split Column 2 vertically (50/50 split view) showing matching patient clinical note text with highlighted matching passages on the left, and raw policy criteria criteria from `mock_policies.json` on the right.
- **FR-009**: Confirming policy inspection by clicking "Proceed to Route" MUST advance `currentStep` to 3, unblurring Column 3.
- **FR-010**: Column 3 MUST render an AI-generated clinical narrative brief inside a scrollable markdown container and a styled outreach text area.
- **FR-011**: If any checklist criteria are marked `ABSENT` or `UNCLEAR`, the communication text area MUST automatically list the precise missing documents/evidence, allowing the reviewer to edit the text natively.
- **FR-012**: Column 3 MUST provide three workflow action buttons executing workflow updates: `[ Route to Nurse Review Queue ]` (Primary Green), `[ Request More Info / Reject ]` (Outline Red), and `[ Escalate to Medical Director ]` (Solid Amber).
- **FR-013**: The bottom of the UI MUST feature a collapsible compliance drawer that renders a table displaying: Timestamp, Action Taken, Agent Responsible, and SHA-256 compliance hash.
- **FR-014**: The React frontend MUST interact synchronously with the Python backend agent endpoints for intake, RAG analysis, outreach generation, and workflow state updates.

### Key Entities

- **UI Session State**: The central React state container orchestrating wizard step (`currentStep`), uploaded document metadata, demographic data, selected criterion, outreach letter edits, and compliance history.
- **Patient Demographics**: Structured extraction record including patient badge (name, DOB, member ID), provider details (NPI, specialist), and clinical metadata (CPT & ICD-10 codes).
- **Policy Criterion Accordion**: A single validation record representing criteria matching state, including raw criteria string, match status badge (PRESENT, ABSENT, UNCLEAR), agent reasoning trail, and matching text coordinates in the patient notes.
- **Compliance Log Entry**: Representation of transactional operations, consisting of a timestamp, operation description, responsible entity, and audit checksum (SHA-256 hash).

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Reviewers can complete the entire prior authorization ingestion, policy check, and routing verification in a single dashboard session without losing context.
- **SC-002**: The UI responds instantaneously (< 100ms visual response time) to user interactions, such as checklist expansion, column splitting, and step transitions.
- **SC-003**: 100% of the active case demographics, policy checklist details, and triage options correspond accurately to the synchronized backend agent outputs.
- **SC-004**: The React application builds successfully and serves the static dashboard interface without console runtime errors.

## Assumptions

- **A-001**: The existing backend logic (agents, files, mock policy data) remains functional and is wrapped in API endpoints.
- **A-002**: Modern desktop browsers (Chrome, Edge, Safari) are the target client environments; mobile layout optimization is out of scope.
- **A-003**: In-memory session state is sufficient for active dashboard state tracking; persistent database storage is out of scope for this UI transition.
