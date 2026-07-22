# Specification: Prior Authorization Evidence Assistant

## Clarifications
- The prototype will use only the local policy PDF at data/guidelines/prior-authorization-and-step-therapy-guidelines.pdf as its evidence source.
- Session state will remain in memory only for the current run; no persistence is required in this prototype.
- The UI will not include action buttons; it will display and update a review status based on the pipeline outcome.

## 1. Core Architecture & State Management
Build a multi-agent pipeline in Python. Use a central `SessionState` dataclass to pass payloads between agents:
- `request_id`: String (UUID)
- `patient_data`: Dict (demographics, clinical notes)
- `classification`: Dict (type: DRUG|IMAGING|SURGERY, urgency: ROUTINE|URGENT)
- `evidence`: List (retrieved chunks, source citations)
- `gap_analysis`: Dict (status: APPROVED|DENIED|PENDING, missing_info: List)
- `artifacts`: Dict (summary, communication_draft)
- `audit_trail`: List of Strings (timestamped logs of agent actions)

## 2. Agent Definitions

### 2.1 Intake & Classification Agent
- **Input:** Raw JSON request payload.
- **Logic:** Parse clinical text. Route to DRUG, IMAGING, or SURGERY. Flag as URGENT if keywords like "stat", "acute", or "life-threatening" are detected.
- **Output:** Populates `classification` and logs to `audit_trail`.

### 2.2 Evidence Retrieval (RAG) Agent
- **Input:** `classification` and `patient_data`.
- **Logic:** Initialize a lightweight retrieval flow over the available policy PDF content. Extract and rank relevant passages from the provided PDF based on the requested procedure/drug.
- **Output:** Populates `evidence` with matched policy text and document IDs.

### 2.3 Policy Reasoning & Gap Agent
- **Input:** `evidence` and `patient_data`.
- **Logic:** Compare clinical notes against policy criteria using an LLM prompt. Identify if prerequisite steps (e.g., prior therapies) are met.
- **Output:** Populates `gap_analysis`. If criteria are missing, set status to PENDING and list `missing_info`.

### 2.4 Reviewer Summary & Communication Agent
- **Input:** `gap_analysis`.
- **Logic:** Draft a concise Markdown summary for the medical reviewer. Generate a template letter to the provider (Approval, Denial, or Request for Information) based on the gap analysis status.
- **Output:** Populates `artifacts`.

### 2.5 Workflow Audit & Readiness Agent
- **Input:** Full `SessionState`.
- **Logic:** Verify all fields are populated. Generate a final compliance hash and timestamp.
- **Output:** Finalized package ready for UI rendering.

## 3. User Interface (Python UI)
Implement a single-page dashboard using Streamlit to serve as the Human-in-the-Loop (HITL) control center.

- **Sidebar (Input):**
  - Text area for pasting raw PA request data.
  - "Run AI Pipeline" execution button.
- **Main Layout (Split View):**
  - **Left Column (Evidence & Diagnostics):**
    - Expandable metrics for Classification, Retrieved Policy Evidence, and Identified Gaps.
    - Live feed of the `audit_trail`.
  - **Right Column (Review & Status):**
    - Rendered Markdown of the Reviewer Summary.
    - Editable text area containing the Draft Provider Communication.
    - Status display that updates to `APPROVED`, `REJECTED`, or `REQUEST MORE INFO` based on the pipeline outcome.