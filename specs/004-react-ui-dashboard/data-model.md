# Data Model: React UI Prior Auth Dashboard

This document details the data structures, entities, and states managed by the React frontend and synchronized with the FastAPI backend.

---

## 1. UI Session State (Frontend & API Payload)

The React UI coordinates layout visibility, stepper focus, and active reviews using a single serialized case state object, which extends the backend `SessionState`.

### Properties
* **`currentStep`** (`number`): Active wizard step (`1` = Ingestion, `2` = Policy Gap Analysis, `3` = Triage and Summary).
* **`requestId`** (`string`): The unique identifier of the active prior authorization case.
* **`patientData`** (`object`): Patient, provider, and clinical metadata.
  * `memberId` (`string`): Patient Member ID (editable/override).
  * `providerId` (`string`): Billing Provider NPI/ID (editable/override).
  * `cptCode` (`string`): CPT Procedure Code (editable/override).
  * `icdCode` (`string`): ICD-10 Diagnosis Code (editable/override).
  * `rawText` (`string`): Extracted clinical documentation note text.
  * `missingFields` (`array` of `string`): List of missing fields detected by the Intake Agent.
* **`classification`** (`object`): Service category classification.
  * `type` (`string`): Service type (e.g., `IMAGING`, `DRUG`, `SURGERY`).
  * `urgency` (`string`): Urgency priority (e.g., `ROUTINE`, `URGENT`).
  * `reason` (`string`): Rationale for categorization.
* **`evidence`** (`array` of `object`): Matching facts extracted from documentation.
  * `prerequisite` (`string`): The policy guideline criteria.
  * `text` (`string`): The exact matching passage from notes.
  * `citation` (`string`): File citation source.
  * `score` (`number`): Agent semantic match score.
* **`gapAnalysis`** (`object`): Policy checklist audit results.
  * `status` (`string`): Overall check status (`APPROVED`, `PENDING`, `REJECTED`).
  * `reasoning` (`string`): Brief explanation.
  * `checklistItems` (`array` of `object`): Accordion card criteria details:
    * `criterion` (`string`): Rule requirement text.
    * `status` (`string`): Verification result (`PRESENT`, `ABSENT`, `UNCLEAR`).
    * `rationale` (`string`): Agent reasoning / logic.
    * `citation` (`string`): Document source citation.
  * `missingInfo` (`array` of `string`): Required docs or clinical parameters that were absent.
* **`artifacts`** (`object`): AI-generated documents.
  * `summary` (`string`): Markdown format clinical case summary brief.
  * `communicationDraft` (`string`): Pre-populated outreach letter.
  * `complianceHash` (`string`): SHA-256 integrity signature of review state.
  * `auditTimestamp` (`string`): Timestamp of audit event.
  * `auditModel` (`string`): LLM model used (e.g., `gpt-4o-mini`).
* **`reviewStatus`** (`string`): Operational review state (`PENDING`, `APPROVED`, `REJECTED`, `REQUEST MORE INFO`).
* **`routingQueue`** (`string`): Triage route endpoint (`Intake`, `Nurse Review`, `Information Request`, `Medical Director`).
* **`auditTrail`** (`array` of `string`): Telemetry logs of user and agent operations.

---

## 2. Mock Policies Store Entity (`data/mock_policies.json`)

Pre-defined guidelines loaded by the backend and displayed to verify policy rules.

* **`cpt_code`** (`string`): CPT key.
* **`service_name`** (`string`): Descriptor of CPT code.
* **`specialty_requirement`** (`string`): Authorized specialty (e.g., Orthopedic Surgery).
* **`clinical_prerequisites`** (`array` of `string`): Guidelines checklist.

---

## 3. Compliance Ledger Entry

Individual row representing transaction records in the bottom drawer table.

* **`timestamp`** (`string`): ISO time string.
* **`action`** (`string`): Description of step taken.
* **`actor`** (`string`): User role or specific AI Agent name.
* **`signature`** (`string`): Computed SHA-256 compliance hash.
