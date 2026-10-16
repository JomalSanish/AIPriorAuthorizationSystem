# Feature Specification: Prior Authorization Evidence Assistant

**Feature Short Name**: `pa-evidence-assistant`

**Created**: 2026-08-08

**Status**: Draft

**Input**: User description: "Build the Prior Authorization Evidence Assistant — an on-prem payer-side web application that helps payer operations staff process prior authorization requests without the system itself ever making the accept/reject decision."

## Clarifications

### Session 2026-08-08

- Q: How should the Reasoning Agent compute the single confidence score shown to the Nurse for each policy-requirement verdict? → A: Weighted combination of retrieval relevance score and LLM self-reported confidence (default `0.4 × retrieval_score + 0.6 × llm_confidence`), with weights configurable per deployment. Both component scores are also logged individually in the audit trail.
- Q: What should happen to a document — and to its parent case — when OCR produces zero extractable text? → A: The document is flagged "Extraction Failed." The case can still be submitted, but if every document on the case yields zero text, the Intake user sees a warning and must explicitly confirm submission. The pipeline proceeds with whatever (possibly zero) text is available, and the Summary Agent flags "No extractable content" to the Nurse.
- Q: Should the Nurse be able to distinguish "Unclear" from "Absent" in the evidence summary, and what operational meaning does each carry? → A: Distinct classifications. "Absent" means no relevant evidence was found in any case document. "Unclear" means evidence was found but is ambiguous, contradictory, or insufficient to confirm the requirement. Both are shown separately in the gap checklist with different visual indicators. "Unclear" items include the ambiguous citation so the Nurse can judge for themselves.
- Q: What event starts the SLA clock for a case, and does it pause while a Nurse has the case locked? → A: The SLA clock starts when the Intake user submits the case and runs continuously (wall-clock) until a Nurse records Accept/Reject. It never pauses — not during pipeline processing, not during lock, not during re-verification. This matches regulatory turnaround-time expectations.
- Q: Can an Intake user edit or resubmit a case after creation, and what happens to an in-flight pipeline? → A: Once submitted, a case is immutable to the Intake user. If an error is discovered, corrections go through Admin intervention, which cancels and restarts the pipeline if still in-flight, or triggers re-verification if already decided. This avoids pipeline race conditions and keeps the Intake role simple.

### Session 2026-08-08 (Checklist Follow-up)

Resolutions closing the role, data-locality, audit, and hardware-budget gaps identified in the
requirements-quality checklist (`checklists/governance.md`, CHK001–CHK048):

- Q: Does an Intake user's Case Management view (and its NLP search) show only cases they personally created, or all cases system-wide? → A: All cases. Case Management is a shared operational section (used by both Intake and Admin), and Intake staff routinely need to check status or follow up on cases they didn't personally create. Intake cannot lock, decide, or access Nurse Review / Admin-only functions (policy management, nurse management, audit trail) — visibility scope and action scope are separate concerns.
- Q: Can Admin view a Nurse's personal History (decided cases), or is that Nurse-only? → A: Admin can view any Nurse's History as a read-only extension of the per-Nurse workload view (FR-033). A Nurse can view only their own History.
- Q: Which roles can access the full case audit trail? → A: Admin only. A Nurse's visibility into case history is limited to their own personal decision History (FR-029); Intake has no audit trail access of any kind.
- Q: Which UI section surfaces a case that enters the "Error" state (LLM unavailable during pipeline)? → A: The Nurse Review queue, visible to Nurse and Admin, flagged "Error / Manual Review Required." No separate UI section is introduced for this case — a Nurse can still lock the case and review the underlying documents manually even though no AI evidence summary exists.
- Q: What happens if the GPU becomes entirely unavailable (driver crash, hardware fault), not just contended? → A: The LLM, OCR, and embedding workloads all fall back to CPU execution rather than halting case processing. This degraded mode is flagged in the operational log; case processing continues but may take substantially longer. The system MUST NOT stop accepting or processing cases solely because the GPU is unavailable.
- Q: Should the system define a VRAM budget rather than just "don't assume too much headroom"? → A: Yes. The target VRAM budget is set to the smallest GPU in the deployment fleet (e.g. 6GB), and the LLM, OCR, and embedding services collectively MUST be configured not to exceed that budget under concurrent use, enforced via the GPU-contention guard rather than left as an informal expectation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Admin Uploads and Names a Policy Document (Priority: P1)

An Admin user uploads a policy document (PDF, DOCX, TXT, or MD) and assigns it a human-readable Policy Name. The system parses the document, builds hybrid index entries for it, and extracts the definitive list of required evidence items for that policy (e.g. "6 weeks conservative therapy," "neurological symptom documentation"). The policy then appears by name in the policy-selection dropdown used during case creation.

**Why this priority**: Policies are the foundation of every case. Without at least one policy ingested, no case can be created or processed. This is the bootstrapping step for the entire application.

**Independent Test**: Upload a single synthetic policy PDF, assign it a name, and verify the policy appears in the dropdown and that its extracted evidence requirements are listed correctly.

**Acceptance Scenarios**:

1. **Given** an authenticated Admin on the Policy Management page, **When** the Admin uploads a valid PDF and enters "Lumbar MRI Policy" as the Policy Name, **Then** the system displays a confirmation with the policy name, a system-generated policy ID (not shown to the Admin as input), and a list of extracted required evidence items.
2. **Given** an uploaded policy named "Lumbar MRI Policy", **When** any Intake user opens the case-creation form, **Then** "Lumbar MRI Policy" appears in the policy dropdown by name (not by system ID).
3. **Given** an Admin uploading a policy document, **When** the document is a scanned PDF (image-only), **Then** the system falls back to OCR, extracts text, and still completes indexing and evidence-item extraction.
4. **Given** any non-Admin user, **When** they attempt to access the Policy Management page or its endpoints, **Then** the system denies access.

---

### User Story 2 — Intake User Creates a New PA Case (Priority: P1)

An Intake user starts a new case, uploads one or more case documents (PDF, DOCX, TXT, MD, or scanned images/faxes), and selects the governing policy from a dropdown populated by policy name. The system auto-extracts what it can from the uploaded documents (member ID, provider ID, CPT/HCPCS code, ICD-10 code, service type) and pre-fills the case form. The Intake user reviews, corrects if needed, and submits. Upon submission, the automated pipeline begins.

**Why this priority**: Case creation is the primary entry point for the operational workflow. Without it, no cases exist for nurses to review or for the pipeline to process.

**Independent Test**: Upload a synthetic case document against an existing policy, verify the form is pre-filled with extracted fields, correct one field, submit, and confirm the case appears in the case queue with status "Processing."

**Acceptance Scenarios**:

1. **Given** an authenticated Intake user on the New Case page with at least one policy available, **When** the user uploads a case document and selects a policy, **Then** the system auto-extracts member ID, provider ID, CPT/HCPCS code, ICD-10 code, and service type and pre-fills the form.
2. **Given** a pre-filled case form, **When** the Intake user corrects the member ID and submits, **Then** the case is created with the corrected member ID and the automated pipeline begins processing.
3. **Given** a case document that is a scanned image (JPEG, PNG, TIFF) or a scanned PDF, **When** the Intake user uploads it, **Then** the system runs OCR and still extracts and pre-fills available fields.
4. **Given** a case with multiple uploaded documents, **When** the Intake user submits, **Then** all documents are associated with the case and indexed.
5. **Given** any non-Intake user, **When** they attempt to access the New Case page or its endpoints, **Then** the system denies access.

---

### User Story 3 — Automated Pipeline Processes a Submitted Case (Priority: P1)

After case submission, the Workflow Agent (an LLM-driven planner) orchestrates the processing pipeline. It plans and executes agent calls — typically Intake Agent (embed and index case documents), Retrieval Agent (hybrid RRF-fused search matching case evidence to each policy requirement), Reasoning Agent (classifies each requirement as Present / Absent / Unclear with citation and confidence), and Summary Agent (produces a nurse-facing evidence summary and gap checklist). The planner may adapt the sequence (e.g. re-running Retrieval after low-confidence Reasoning). Every planner decision and agent step is audit-logged. A bounded turn budget guarantees termination. The case is always placed in the Nurse Review queue at the end.

**Why this priority**: The pipeline is the core intelligence of the system. Without it, cases would have no evidence summary, no gap analysis, and nurses would have no AI assistance.

**Independent Test**: Submit a synthetic case against a known policy, wait for pipeline completion, and verify: (a) an evidence summary exists, (b) each policy requirement has a Present/Absent/Unclear classification with citation, (c) the case status is "Pending Nurse Review," and (d) the audit trail contains all planner decisions and agent steps.

**Acceptance Scenarios**:

1. **Given** a newly submitted case, **When** the Workflow Agent begins processing, **Then** each planner decision (chosen action + reasoning) is written to the audit trail before execution.
2. **Given** a case where the Reasoning Agent returns a low-confidence verdict for a requirement, **When** the Workflow Agent replans, **Then** it may re-invoke the Retrieval Agent with a refined query before re-running Reasoning, and this adaptation is audit-logged.
3. **Given** a case that exceeds the per-case turn budget (e.g. 10 planner turns), **When** the budget is exhausted, **Then** the system deterministically finalizes the case into the Nurse Review queue with whatever results are available.
4. **Given** any pipeline path, **When** the pipeline completes, **Then** the Summary Agent has produced output and the case status is "Pending Nurse Review" — the pipeline never emits an accept or reject decision.

---

### User Story 4 — Nurse Reviews and Decides on a Case (Priority: P1)

A Nurse user sees the Nurse Review queue listing cases by heading and metadata only (Case ID, service type, submitted date, SLA clock). The SLA clock starts at case submission and runs continuously (wall-clock) until a Nurse records a decision — it never pauses. The Nurse locks a case to themselves. Once locked, no other nurse can open it. After locking, the Nurse can inspect the AI evidence summary and gap checklist, and/or the underlying documents directly. The Nurse then records an Accept or Reject decision with a mandatory comment. The case appears in the Nurse's personal History view.

**Why this priority**: The Nurse decision is the sole mechanism by which a case reaches a final outcome. This is the human-in-the-loop guarantee.

**Independent Test**: As a Nurse, view the queue, verify only metadata is visible, lock a case, verify evidence summary and documents become accessible, submit an Accept decision with a comment, and verify it appears in the History view.

**Acceptance Scenarios**:

1. **Given** a Nurse viewing the Nurse Review queue, **When** the queue loads, **Then** each case row shows only Case ID, service type, submitted date, and SLA clock — no summary, evidence, or document content is visible.
2. **Given** a Nurse selecting a case from the queue, **When** the Nurse clicks "Lock Case," **Then** the case is locked to that Nurse and no other Nurse can open or lock it.
3. **Given** a locked case, **When** the Nurse views the case detail, **Then** the AI evidence summary, gap checklist, and underlying documents are now accessible.
4. **Given** a Nurse reviewing a locked case, **When** the Nurse submits an "Accept" decision with a comment, **Then** the case status becomes "Accepted," the decision is attributed to the Nurse with a timestamp, and the case appears in the Nurse's History.
5. **Given** a Nurse reviewing a locked case, **When** the Nurse submits a "Reject" decision with a comment, **Then** the case status becomes "Rejected," with the same attribution and history tracking.
6. **Given** a case locked by Nurse A, **When** 24 hours pass without activity, **Then** the lock is automatically released and the case returns to the available queue.
7. **Given** a case locked by Nurse A, **When** Nurse B attempts to open that case, **Then** the system shows the case is locked by another nurse and denies access.

---

### User Story 5 — Admin Oversees and Intervenes on Cases (Priority: P2)

An Admin can see all cases across all queues, who has each case locked, and each case's verification status. Admin can modify case data (e.g. correct a field, add a document). Any modification to a case after a Nurse decision immediately invalidates that decision: the case returns, unlocked, to the Nurse Review queue, clearly flagged "Re-verification Required."

**Why this priority**: Admin intervention is an important operational safeguard but secondary to the core create → process → review loop. Nurses and Intake users can function without Admin intervention on individual cases.

**Independent Test**: As Admin, view all cases, modify a field on an Accepted case, and verify the case returns to the Nurse Review queue with "Re-verification Required" flag and the original decision is invalidated.

**Acceptance Scenarios**:

1. **Given** an authenticated Admin on the Admin Dashboard, **When** the dashboard loads, **Then** the Admin sees every case across all queues, each case's current status, lock holder (if any), and verification status.
2. **Given** a case with status "Accepted" decided by Nurse A, **When** the Admin modifies any case data, **Then** the case status changes to "Re-verification Required," the case is unlocked, and it is placed back in the Nurse Review queue.
3. **Given** a re-queued case, **When** any Nurse (including or excluding the original) views the queue, **Then** the case is clearly marked "Re-verification Required."
4. **Given** an Admin, **When** the Admin views a specific Nurse's workload, **Then** the Admin sees the Nurse's currently locked cases and a count of decided cases.

---

### User Story 6 — NLP Case Search (Priority: P2)

Across Case Management, Nurse Review, and the Admin Dashboard, users can search in natural language (e.g. "MRI cases" or "cases for provider ABC Health"). A lightweight LLM call translates the free-text query into a structured search request (semantic query string + extracted filters such as CPT/ICD code, provider name, member ID, date range, case status). That structured request executes against the existing hybrid (dense+sparse, RRF-fused) index over case profile data. Results are returned as a list of matching cases, not raw document chunks.

**Why this priority**: Search is critical for productivity at scale but the system is functional without it in early stages — users can browse queues manually.

**Independent Test**: Submit a natural-language query "MRI cases from last week," verify the system returns a case list (not document chunks), and confirm that exact-code queries like "CPT 70553" also return correct results.

**Acceptance Scenarios**:

1. **Given** a user on any section with search, **When** the user types "MRI cases," **Then** the system returns a list of cases whose profiles semantically match "MRI" — not by scanning documents at query time.
2. **Given** a user searching "cases for provider ABC Health," **When** the query is processed, **Then** the LLM extracts "ABC Health" as a provider-name filter, and the search returns cases whose provider field matches.
3. **Given** a user searching "CPT 70553," **When** the query is processed, **Then** the exact CPT code resolves via the keyword/filter path, returning cases with that CPT code.
4. **Given** search results, **When** displayed, **Then** results are case-level entries (Case ID, service type, status, date) — not individual document chunks.

---

### User Story 7 — Full Audit Trail (Priority: P2)

Every agent action, every retrieval, every routing decision, and every human decision (Nurse accept/reject, Admin edit) is logged with actor identity, timestamp, model/version used (for AI steps), and confidence score (for AI steps). The audit trail for any case can be reconstructed into a complete chronological history.

**Why this priority**: Audit is a compliance requirement and a core constitutional principle. While the system can technically function without viewing the audit trail in the UI, it must be captured from the very first action.

**Independent Test**: Process a case end-to-end, then as Admin, view the audit trail for that case and confirm every pipeline step, every planner decision, and the Nurse decision appear with all required fields.

**Acceptance Scenarios**:

1. **Given** a completed case (Accepted or Rejected), **When** an Admin views the audit trail, **Then** every step is listed chronologically: case creation, each planner decision, each agent invocation with model/version, retrieval queries with result counts, Reasoning verdicts with confidence, Summary generation, routing, lock, and the final Nurse decision.
2. **Given** any audit entry, **When** inspected, **Then** it includes: timestamp, actor identity (user or agent name), action type, and (for AI actions) model/version and confidence score.
3. **Given** a case that required re-verification, **When** the audit trail is viewed, **Then** the Admin edit, the automatic re-queue, and the subsequent Nurse re-decision are all visible.

---

### User Story 8 — Authentication and Role-Based Access (Priority: P1)

Three user roles exist: Intake, Nurse, and Admin. Each role is authenticated via JWT/OAuth2 (self-hosted). Each role can only access its own section of the UI and its own API scopes. There is no shared "user" role.

**Why this priority**: Without authentication and role separation, no other user story can enforce its access constraints. This is a foundational cross-cutting concern.

**Independent Test**: Log in as each role type, verify each can only access its designated sections, and confirm that attempting to access another role's section returns an authorization error.

**Acceptance Scenarios**:

1. **Given** an unauthenticated user, **When** they attempt to access any page, **Then** they are redirected to the login page.
2. **Given** a user authenticated as Intake, **When** they attempt to access the Admin Dashboard or Nurse Review queue, **Then** the system denies access.
3. **Given** a user authenticated as Nurse, **When** they attempt to access the Policy Management page or Case Creation page, **Then** the system denies access.
4. **Given** a user authenticated as Admin, **When** they access the Admin Dashboard, **Then** they see all cases, policy management, and nurse account management.
5. **Given** an Admin, **When** they manage Nurse accounts, **Then** they can create, deactivate, and view Nurse user accounts.

---

### Edge Cases

- What happens when a case document is completely unreadable (OCR fails to extract any text)? The document is flagged "Extraction Failed." If other documents on the case produced text, the case proceeds normally and the Nurse sees the failure flag on the affected document. If every document on the case yields zero extractable text, the Intake user sees an explicit warning and MUST confirm submission before the case is created. The pipeline proceeds with whatever (possibly zero) text is available, and the Summary Agent flags "No extractable content" to the Nurse.
- What happens when the Retrieval Agent finds no evidence for any policy requirement? The Reasoning Agent MUST classify every requirement as "Absent" with confidence and the Summary Agent MUST produce a gap checklist with all items listed as unmet. The case still routes to Nurse Review.
- What happens when two Nurses attempt to lock the same case simultaneously? Only one lock succeeds. The second Nurse receives a message that the case is already locked.
- What happens when an Admin modifies a case that is currently locked by a Nurse? The lock is released, the decision (if any) is invalidated, and the case returns to the queue as "Re-verification Required." The Nurse is notified that their lock was released.
- What happens when the LLM is unavailable during pipeline processing? The case is placed into an "Error" state with a descriptive message, and it is routed to a manual review pathway. It MUST NOT silently fail or disappear. It surfaces in the Nurse Review queue (visible to Nurse and Admin) flagged "Error / Manual Review Required" — no separate UI section exists for this case; a Nurse can still lock it and review the underlying documents manually even without an AI evidence summary.
- What happens if the GPU is entirely unavailable, not just contended (driver crash, hardware fault)? The LLM, OCR, and embedding workloads fall back to CPU execution rather than halting case processing; the degraded mode is flagged in the operational log and processing may take substantially longer but MUST still complete.
- What happens when a policy is updated or deleted while cases reference it? Existing cases retain their association with the policy version they were created against. Deleting a policy MUST NOT delete or invalidate existing cases.
- What happens when the turn budget is reached mid-pipeline? The system finalizes with whatever partial results exist, generates a Summary (even if incomplete), and routes to Nurse Review with a flag indicating the pipeline hit its turn budget.
- What happens when an Intake user discovers an error after submitting a case? The Intake user cannot edit a submitted case. They contact an Admin, who can modify the case. If the pipeline is still running, the Admin's modification cancels the in-flight pipeline and restarts it. If a Nurse has already decided, the modification triggers re-verification (FR-032).

## Requirements *(mandatory)*

### Functional Requirements

**Authentication & Authorization**

- **FR-001**: The system MUST authenticate users via self-hosted JWT/OAuth2.
- **FR-001a**: The login page and its authentication endpoints MUST be the only routes accessible without a valid access token; every other route MUST require authentication.
- **FR-001b**: Access tokens MUST be short-lived, backed by a longer-lived refresh token. On mid-session access-token expiry (e.g. during an in-progress Nurse review), the client MUST silently refresh rather than interrupt the user. If the refresh token is also invalid or expired, the user MUST re-authenticate — but a case lock (FR-025/FR-026) is tied to the case and the 24-hour timer, not to the browser session, so a forced re-login MUST NOT itself release the lock or lose in-progress review state.
- **FR-002**: The system MUST enforce exactly three roles: Intake, Nurse, and Admin, with no shared "user" role.
- **FR-003**: Each role MUST be restricted to its own UI sections and API scopes; cross-role access MUST be denied.
- **FR-003a**: API scopes MUST be enumerated per role at the scope-group level: Intake — `case:create`, `case:read` (all cases), `document:upload`, `policy:read` (name list only); Nurse — `case:read` (queue + own locked/decided cases), `case:lock`, `case:decide`, `history:read` (own only); Admin — `case:*`, `policy:*`, `user:manage`, `audit:read`, `history:read` (any nurse). A role's token MUST only carry the scopes listed for it.
- **FR-004**: All credentials and connection strings MUST be accessed through a secrets-management abstraction layer.

**Policy Management (Admin)**

- **FR-005**: An Admin MUST be able to upload a policy document (PDF, DOCX, TXT, MD) and assign it a human-readable Policy Name.
- **FR-006**: The system MUST generate a unique policy ID internally; the Admin MUST NOT be required to enter or see a policy ID during upload.
- **FR-007**: The system MUST parse the uploaded policy document, build hybrid (dense + sparse) index entries, and extract the list of required evidence items for that policy, using the same local LLM as all other inference (see FR-043a) — no separate or external extraction service.
- **FR-008**: Policy Names (not IDs) MUST populate the policy-selection dropdown in case creation.
- **FR-009**: Non-text-extractable policy documents (scanned PDFs) MUST be processed via OCR fallback.
- **FR-009a**: An Admin MUST be able to deactivate (soft-delete) a policy. Deactivation removes it from the case-creation dropdown but MUST NOT delete or invalidate existing cases created against it (see Edge Cases).

**Case Creation (Intake)**

- **FR-010**: An Intake user MUST be able to create a new case by uploading one or more case documents and selecting a governing policy from the policy-name dropdown.
- **FR-011**: The system MUST auto-extract member ID, provider ID, CPT/HCPCS code, ICD-10 code, and service type from uploaded documents and pre-fill the case form, using the same local LLM/local extraction pipeline as all other inference (see FR-043a) — no external extraction service.
- **FR-012**: The Intake user MUST be able to review and correct all auto-extracted fields before final submission.
- **FR-012a**: Once a case is submitted, it MUST be immutable to the Intake user. Post-submission corrections MUST go through Admin intervention. If an Admin modifies a case while the pipeline is still in-flight, the running pipeline MUST be cancelled and restarted from scratch with the updated data. If the case has already been decided, FR-032 (re-verification) applies.
- **FR-013**: The system MUST support PDF, DOCX, TXT, MD, and image formats (JPEG, PNG, TIFF) for case documents, with OCR fallback for non-text-extractable files.
- **FR-013a**: When a document produces zero extractable text (blank scan, corrupted file), the system MUST flag it as "Extraction Failed." If all documents on a case yield zero text, the system MUST display a warning to the Intake user requiring explicit confirmation before submission. The pipeline MUST proceed with whatever text is available, and the Summary Agent MUST flag "No extractable content" to the Nurse.

**Automated Pipeline (Workflow Agent)**

- **FR-014**: The Workflow Agent MUST be an LLM-driven planner that selects actions from a whitelisted set: invoke Intake Agent, invoke Retrieval Agent, invoke Reasoning Agent, invoke Summary Agent, request additional evidence, finalize and route to Nurse Review.
- **FR-015**: Each planner decision (chosen action + reasoning) MUST be written to the audit trail before execution.
- **FR-016**: A per-case turn budget MUST force deterministic finalization into the Nurse Review queue if exceeded.
- **FR-017**: The Workflow Agent MUST never emit an accept or reject decision; it may only route to Nurse Review.
- **FR-018**: Summary Agent output MUST be produced before finalization is permitted.
- **FR-019**: The Intake Agent MUST embed and index new case documents into the hybrid (dense + sparse) index.
- **FR-020**: The Retrieval Agent MUST perform hybrid (dense + sparse) search with Reciprocal Rank Fusion (RRF) to match case evidence to each policy requirement.
- **FR-021**: The Reasoning Agent MUST classify each policy requirement as Present, Absent, or Unclear, with a citation to a specific source document, page/section, and document UUID, and a composite confidence score computed as a configurable weighted combination of the retrieval relevance score and the LLM's self-reported confidence (default weights: `0.4 × retrieval_score + 0.6 × llm_confidence`). Both component scores MUST also be logged individually in the audit trail. Classification semantics: "Absent" means no relevant evidence was found in any case document; "Unclear" means evidence was found but is ambiguous, contradictory, or insufficient to confirm the requirement.
- **FR-022**: The Summary Agent MUST produce a nurse-facing evidence summary and a gap checklist. The gap checklist MUST present "Absent" and "Unclear" requirements as distinct sections with different visual indicators. "Unclear" items MUST include the ambiguous citation so the Nurse can evaluate the evidence directly.

**Nurse Review**

- **FR-023**: The Nurse Review queue MUST display only case heading and metadata (Case ID, service type, submitted date, SLA clock) before a Nurse locks a case.
- **FR-023a**: The SLA clock MUST start when the Intake user submits the case and MUST run continuously (wall-clock time) until a Nurse records Accept/Reject. The clock MUST NOT pause during pipeline processing, during lock, or during re-verification. The SLA deadline is configurable per deployment.
- **FR-024**: A Nurse MUST explicitly lock a case to themselves before accessing evidence summary, AI analysis, or documents.
- **FR-025**: Only one Nurse may hold a lock on a given case at any time.
- **FR-026**: Case locks MUST automatically release after 24 hours of inactivity.
- **FR-027**: After locking, the Nurse MUST be able to view the AI evidence summary, gap checklist, and underlying documents.
- **FR-028**: The Nurse MUST record an explicit Accept or Reject decision with a mandatory comment.
- **FR-029**: Each decided case MUST appear in the deciding Nurse's personal History view.
- **FR-029a**: A Nurse MUST be able to view only their own History. An Admin MAY view any Nurse's History, read-only, as an extension of the per-Nurse workload view (FR-033).

**Admin Oversight & Intervention**

- **FR-030**: The Admin MUST see all cases across all queues, with each case's status, lock holder, and verification status.
- **FR-031**: The Admin MUST be able to modify case data on any case.
- **FR-032**: Any Admin modification to a case after a Nurse decision MUST immediately invalidate that decision, unlock the case, and route it to the Nurse Review queue with a "Re-verification Required" flag.
- **FR-033**: The Admin MUST be able to view per-Nurse workload: currently locked cases and decided-case counts.
- **FR-034**: The Admin MUST be able to manage Nurse accounts (create, deactivate, view).

**NLP Case Search**

- **FR-035**: Users MUST be able to search for cases using natural-language queries from any section that displays case lists.
- **FR-036**: The system MUST translate natural-language queries into structured search requests (semantic query + extracted filters) via a lightweight LLM call.
- **FR-036a**: The query-translation LLM call MUST use the same local LLM instance as all other LLM calls (FR-043) — no external API path — and MUST be subject to the same GPU-contention guard as other LLM calls (FR-046).
- **FR-037**: Structured search requests MUST execute against the existing hybrid (dense + sparse, RRF-fused) index over case profile data.
- **FR-038**: Search results MUST be returned as case-level entries (not raw document chunks).
- **FR-039**: Exact identifiers (CPT/HCPCS codes, ICD-10 codes, Member ID, Provider name) MUST resolve via the keyword/filter path; conceptual terms MUST resolve via the semantic path.
- **FR-039a**: Search results MUST respect each role's existing visibility rules, applied at the retrieval layer after query translation — never bypassable via search phrasing: a Nurse's results show heading/metadata only for cases the Nurse has not locked (same restriction as browsing the queue, FR-023); an Intake user's results include all cases (FR-010 scope); an Admin's results are unrestricted.

**Audit Trail**

- **FR-040**: Every agent action, retrieval, routing decision, and human decision MUST be logged with: timestamp, actor identity, action type, and (for AI actions) model/version and confidence score.
- **FR-040a**: In addition to agent actions and human decisions, the following MUST each generate a distinct auditable entry: case creation; policy upload; policy deactivation (FR-009a); Nurse account creation/deactivation (FR-034); case lock acquisition; case lock auto-release (FR-026); the "Re-verification Required" re-queue event (FR-032); Admin cancellation/restart of an in-flight pipeline (FR-012a); the Intake user's explicit confirmation of an all-documents-failed submission (FR-013a); the Workflow Agent's turn-budget exhaustion event (FR-016); and the pipeline "Error" state transition (LLM unavailable).
- **FR-040b**: Failed authentication attempts MUST be logged (attempted identifier, timestamp, outcome) as a security audit entry, distinct from per-case audit entries.
- **FR-040c**: Denied cross-role access attempts (authorization failures) MUST be logged with actor identity, attempted resource, and timestamp.
- **FR-040d**: Audit entries for human actions (Nurse decision, Admin edit) MUST carry the same structural precision as AI actions — timestamp, actor identity, action type, and the associated comment where one exists — even though model/version and confidence do not apply to human entries.
- **FR-040e**: Audit log entries MUST be append-only; no application code path may update or delete an existing entry.
- **FR-040f**: Secrets-manager credential-access events (FR-004) MUST be logged to a security/operational log — logging that access occurred, never the credential value itself.
- **FR-041**: The audit trail for any case MUST be viewable as a complete chronological history.
- **FR-041a**: The audit trail view MUST be accessible to Admin only. A Nurse's visibility into case history is limited to their own personal decision History (FR-029a); Intake has no audit trail access.
- **FR-042**: Every evidence claim MUST carry a citation to a specific source document, page/section, and a stable document UUID.

**Data Locality & Confidentiality**

- **FR-043**: All inference (OCR, embeddings, LLM generation) MUST run on locally hosted or on-prem infrastructure with zero external egress for document content or PHI.
- **FR-043a**: This locality requirement explicitly covers every inference call site, not only the main pipeline: policy evidence-item extraction (FR-007), case-metadata auto-extraction (FR-011), and the NLP search query-translation call (FR-036a) all use the same local LLM — none has a separate or external code path.
- **FR-043b**: Agent prompts and logs MUST contain the minimum PHI necessary for the task; Summary and Reasoning outputs MUST NOT reproduce full patient records verbatim.
- **FR-043c**: No document content, embedding vector, or derived text MUST be persisted to browser local storage, browser cache, or client-side logs.
- **FR-043d**: The vector store (dense + sparse index) MUST be a locally hosted instance with no cloud-hosted vector database option.
- **FR-043e**: The audit trail and all application data MUST be stored on locally hosted infrastructure (relational database, vector store, object storage), with no external log-aggregation or analytics service ever receiving case or document content.
- **FR-044**: Dev/test environments MUST use synthetic data only.

**GPU Resource Management**

- **FR-045**: The local LLM MUST always have GPU priority over OCR and embedding workloads.
- **FR-046**: An explicit in-process concurrency guard MUST gate GPU-heavy calls so that OCR and embedding use the GPU only when the LLM is not actively generating.
- **FR-046a**: An OCR or embedding request that arrives while the LLM is actively generating MUST queue behind the LLM call up to a configurable timeout (default: 10 seconds); if the timeout is exceeded, the request MUST fall back to CPU execution rather than blocking indefinitely.
- **FR-046b**: The GPU-priority policy and the CPU-fallback timeout MUST both be configuration values, not hardcoded, since deployment hardware GPU headroom varies.
- **FR-046c**: The NLP search query-translation LLM call (FR-036a) MUST be subject to this same GPU-contention guard as any other LLM call.
- **FR-046d**: Contention events (queue waits, CPU fallbacks) MUST be logged to an operational log for capacity monitoring — distinct from the per-case audit trail.
- **FR-047**: If the GPU is entirely unavailable (e.g. driver failure, hardware fault), the system MUST fall back to CPU execution for the LLM, OCR, and embedding workloads rather than halting case processing; this degraded mode MUST be flagged in the operational log, and case processing MAY take substantially longer but MUST still complete.
- **FR-048**: The system MUST target a VRAM budget no larger than the smallest GPU in the deployment fleet (e.g. 6GB); the LLM, OCR, and embedding services collectively MUST NOT be configured to assume more concurrent headroom than that budget provides.

### Key Entities

- **Policy**: A payer-defined authorization policy with a system-generated ID, admin-assigned name, source document(s), and a list of extracted required evidence items. Versioned — existing cases retain their association with the policy version at creation time.
- **Case**: A prior-authorization request with a unique Case ID, associated policy, uploaded case documents, extracted metadata (member ID, provider ID, CPT/HCPCS, ICD-10, service type), processing status, SLA start timestamp (set at submission, never reset), evidence summary, gap checklist, decision outcome, and full audit trail.
- **User**: An authenticated individual with exactly one role (Intake, Nurse, or Admin) and role-scoped access. Intake sees all cases in Case Management (not limited to self-created); Nurse sees full case detail only for cases they have locked, and their own decision History only; Admin sees everything, including any Nurse's History and the full audit trail.
- **Document**: An uploaded file (policy or case document) with a stable UUID, original filename, file type, extracted text content, OCR status, and index entries.
- **Evidence Claim**: A specific assertion about whether a policy requirement is met, with a classification (Present / Absent / Unclear), a composite confidence score (configurable weighted combination of retrieval relevance and LLM self-reported confidence; default `0.4 × retrieval + 0.6 × LLM`), the two component scores logged individually, and a citation to a source document, page/section, and document UUID.
- **Audit Entry**: A record of a single action with timestamp, actor identity, action type, associated case, model/version (if AI), and confidence score (if AI).
- **Case Lock**: A record associating a case with a Nurse, including lock acquisition time and a 24-hour expiration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new case (from document upload to "Pending Nurse Review" status) completes pipeline processing within 5 minutes for standard-complexity cases (under 20 pages of case documents).
- **SC-002**: A Nurse can complete a case review (lock → inspect evidence → record decision) in under 10 minutes for standard-complexity cases, compared to the baseline of reviewing raw documents without AI assistance.
- **SC-003**: 100% of submitted cases reach the Nurse Review queue — no case is silently dropped, stalled, or auto-decided by the pipeline.
- **SC-004**: Hybrid retrieval returns the correct evidence passage within the top-5 results for at least 90% of policy requirements, as measured against a synthetic test corpus.
- **SC-005**: Every case has a complete audit trail: 100% of agent actions, planner decisions, and human decisions are logged with all required fields (timestamp, actor, action type, model/version, confidence).
- **SC-006**: Role separation is absolute: 0% of cross-role access attempts succeed across all role-section combinations.
- **SC-007**: NLP search returns relevant case-level results for at least 85% of natural-language queries, and 100% of exact-identifier queries (CPT/ICD codes, Member IDs) return correct results.
- **SC-008**: Case locks auto-release within 60 seconds of the 24-hour inactivity threshold being reached.
- **SC-009**: Admin case modification immediately invalidates prior Nurse decisions within 5 seconds, with 100% reliability.
- **SC-010**: Zero document content or PHI is transmitted to any external API under any code path, as verified by network-level audit.

## Assumptions

- The deployment environment provides at least one CUDA-capable GPU. The system targets a VRAM budget no larger than the smallest GPU in the fleet (e.g. 6GB, per FR-048) and is designed around a single-GPU constraint with a CPU fallback (FR-047) if the GPU is unavailable.
- All LLM inference uses a single model (llama3.2:3b via Ollama) running locally. No cloud-hosted or third-party LLM services are used.
- Embedding generation uses a locally hosted embedding model (not a cloud API).
- OCR is handled by EasyOCR running locally with GPU sharing governed by the concurrency guard.
- Authentication is self-hosted (JWT/OAuth2); no external identity provider (e.g. Okta, Auth0) is assumed.
- The initial deployment targets a single-instance architecture (one application server, one database, one vector store). Horizontal scaling is out of scope for this specification.
- The system is a web application accessed via modern desktop browsers. Native mobile support is out of scope.
- Integration with external payer systems (claims, eligibility, provider networks) is mocked only; real integrations are out of scope.
- Synthetic data is used for all development and testing. No real PHI enters any non-production environment.
- HIPAA-compliant audit log retention (minimum six years) is a deployment concern addressed by infrastructure configuration, not application logic, but the application MUST produce the log data in a retainable format.
- State-specific prior-authorization timelines and notification requirements are configurable but not pre-loaded; initial deployment assumes a single-state configuration.

## Out of Scope

- Automated approval or denial of any kind by the system
- Final clinical decision-making by the system
- Real payer system integration (mocked only)
- Real PHI in development or test environments
- Claims or payment adjudication
- Regulatory or legal determination
- Sending any document content to a public or hosted API
- Mobile-native applications
- Multi-tenancy or multi-organization support
- Horizontal scaling or high-availability clustering
- Real-time notifications (e.g. push notifications, WebSocket alerts to nurses)
- Member or provider self-service portals
