# Feature Specification: Payer Prior Authorization Evidence Assistant

**Feature Branch**: `[002-payer-prior-auth]`

**Created**: 2026-07-08

**Status**: Draft

**Input**: User description: "Spec-Driven Development of a Healthcare Payer Prior Authorization Evidence Assistant using RAG and Agentic AI..."

## Constitution Alignment

- The solution MUST use Python and a Streamlit UI whenever a user-facing workflow is required.
- The solution MUST use LangChain-based multi-agent routing when a multi-agent architecture is part of the feature.
- All Python files MUST include explicit type hints.
- Prototype work MUST use the available local evidence source and in-memory state unless persistence is explicitly requested.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Intake Case Creation & Completeness (Priority: P1)

As an Intake Associate, I want to create a new prior authorization case and ingest/upload provider-submitted documents, so that the system can validate completeness and identify any missing required fields.

**Why this priority**: Crucial first step of the workflow. Without case ingestion and initial completeness checks, downstream agents cannot process the request.

**Independent Test**: Can be fully tested by entering member/provider IDs, a CPT code, and clicking "Run AI Pipeline" to verify that the case is initialized and completeness status is evaluated.

**Acceptance Scenarios**:

1. **Given** a new case ingestion request with missing clinical notes, **When** the Intake Agent runs, **Then** the case status is set to "Incomplete" and the missing fields are listed in the metadata.
2. **Given** a request with all required fields (member ID, provider ID, clinical text), **When** the Intake Agent runs, **Then** the case is marked "Complete" and ready for evidence retrieval.

---

### User Story 2 - RAG-based Evidence Retrieval & Policy Mapping (Priority: P1)

As a Nurse Reviewer, I want to view retrieved policy evidence with clear citations, so that I can see the exact guidelines supporting or contradicting the prior authorization request.

**Why this priority**: Core value of the RAG assistant. Reviewers need source-attributed evidence to make informed medical necessity determinations.

**Independent Test**: Can be tested by running a case and checking the left-column evidence section to verify that the policy excerpts matched from the PDF are rendered with correct document names and citation tags.

**Acceptance Scenarios**:

1. **Given** a prior authorization request for a specific procedure (e.g., MRI Lumbar Spine), **When** the Evidence Retrieval Agent runs, **Then** it retrieves matches from the local policy PDF, ranking them by relevance score, and displays them with a citation link/source name.

---

### User Story 3 - Policy Gap Analysis & Checklist Generation (Priority: P2)

As a Nurse Reviewer or Medical Director, I want to see a clear checklist comparing case facts to medical policy criteria, so that I know exactly which requirements are met and which are missing.

**Why this priority**: Streamlines the audit process and guides the reviewer on whether further information is needed from the provider.

**Independent Test**: Can be tested by running a case with missing conservative therapy evidence and checking if a checklist shows "6 weeks therapy" as "Missing/Absent".

**Acceptance Scenarios**:

1. **Given** a case where the policy requires prior conservative therapy but the clinical notes do not document it, **When** the Policy Reasoning Agent runs, **Then** it populates the gap analysis status as "PENDING" and lists the missing conservative therapy in the checklist.

---

### User Story 4 - Summary & Communication Drafts (Priority: P2)

As a Nurse Reviewer or Provider Relations User, I want the system to generate a concise summary and a neutral communication letter draft, so that I can copy or edit the text to request missing documents or summarize the case for escalating.

**Why this priority**: Saves operational time by automating draft communications and clinical briefs.

**Independent Test**: Can be verified by reviewing the right-column summary and draft letter text areas after pipeline execution.

**Acceptance Scenarios**:

1. **Given** a gap analysis status of "PENDING" due to missing documents, **When** the Summary & Communication Agent runs, **Then** it drafts a neutral provider letter requesting the specific missing clinical information.

---

### User Story 5 - Queue Routing & Audit Trail (Priority: P3)

As an Operations Manager or Compliance Auditor, I want the system to route cases to the correct queue and provide a chronological, hashed audit trail of all agent actions, so that the workflow is transparent and compliant.

**Why this priority**: Essential for administrative oversight, routing efficiency, and meeting compliance/auditability requirements.

**Independent Test**: Can be tested by verifying that the compliance hash is generated at the end of the run and the audit trail lists all five agents with their actions and timestamps.

**Acceptance Scenarios**:

1. **Given** a case with incomplete evidence, **When** the Workflow Agent runs, **Then** it routes the case to the "Nurse Review Queue" and records the decision, timestamp, and confidence score in the audit log.

---

### Edge Cases

- **No Policy Matches Found**: If a rare procedure has no matching text in the policy document, the Evidence Agent must return a clear fallback message and route the case to manual review rather than failing or returning irrelevant passages.
- **Contradictory Clinical Notes**: If the case contains conflicting clinical details (e.g., one note says "failed conservative therapy", another says "no therapy attempted"), the Gap Agent must flag the case as "Ambiguous Evidence" and escalate it immediately for human clinical review.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The system MUST support document upload (PDF, TXT) and form-based metadata capture (Member ID, Provider ID, CPT/HCPCS, ICD-10) in the Streamlit UI.
- **FR-002**: The Intake Agent MUST parse the case data to extract key metadata and classify the service type (Imaging, Surgery, Drug, DME, Behavioral Health, Specialty Referral).
- **FR-003**: The Intake Agent MUST perform a completeness check, setting the status to "Incomplete" and identifying missing fields if required elements are missing.
- **FR-004**: The RAG Agent MUST index, chunk, and embed the local policy guidelines and ingested case documents for retrieval.
- **FR-005**: The RAG Agent MUST perform hybrid or semantic search over the policy database using the case context, returning exact matching passages and citation details.
- **FR-006**: The RAG Agent MUST avoid unsupported answers or hallucinations by restricting its answers strictly to retrieved context.
- **FR-007**: The system MUST integrate an external LLM provider (supporting Gemini or OpenAI via a local `.env` configuration file).
- **FR-008**: The Policy Reasoning Agent MUST translate policy requirements into a structured checklist (Present, Absent, Unclear) and flag gaps.
- **FR-009**: The Policy Reasoning Agent MUST not automate approval/denial decisions, acting strictly as an evidence preparer.
- **FR-010**: The Summary Agent MUST generate a formatted Markdown summary and a draft letter to the provider based on the case status (Approval, Request Info, or Denial).
- **FR-011**: The Workflow Agent MUST route the case to the appropriate queue (Intake, Nurse Review, Medical Director Review) based on the completeness and gap status.
- **FR-012**: The dashboard MUST provide a unified view with a common tab for uploading documents & patient info, followed by distinct tabs for role-specific queues (Intake, Nurse, Director, Auditor, Manager) for manual triage and approval.
- **FR-013**: The Audit Agent MUST record a tamper-evident audit trail including timestamps, agent actions, model details, confidence scores, and a final compliance hash.
- **FR-014**: The system MUST parse uploaded PDFs using `pypdf` library.

### Key Entities

- **PriorAuthCase**: Represents a single prior authorization request. Attributes: `case_id`, `member_id`, `provider_id`, `cpt_code`, `icd_code`, `status` (Created, Incomplete, Ready for Evidence Review, Under Review, Completed), `service_type`.
- **PolicyEvidence**: Represents matching passages from the policy guidelines. Attributes: `source_document`, `text_segment`, `citation_reference`, `relevance_score`.
- **GapChecklist**: The checklist of requirements for the requested procedure. Attributes: `criteria_list`, `missing_items`, `escalation_reason`.
- **AuditLogEntry**: Timestamped action log for compliance. Attributes: `timestamp`, `agent_name`, `action_taken`, `payload_hash`.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Reviewers can run the entire 5-agent pipeline and see the complete analysis results on the dashboard in under 5 seconds.
- **SC-002**: 100% of generated case summaries and draft communications contain direct source document citations (citations to page or section).
- **SC-003**: The Intake Agent correctly identifies 95% of incomplete case submissions by checking metadata and missing clinical notes.
- **SC-004**: The system generates a valid compliance SHA-256 hash for every completed review to ensure compliance traceability.

## Assumptions

- **Local PDF Availability**: The primary policy guidelines document is available at `data/guidelines/prior-authorization-and-step-therapy-guidelines.pdf`.
- **In-Memory State**: The application will maintain session state in-memory during user interaction; permanent database persistence (e.g., PostgreSQL/SQLite) is out of scope for the initial prototype.
- **Mocked External APIs**: Integrations with production payer systems or actual faxes will be simulated or mocked.
