# API Interface Contract: Prior Auth Agent Backend

This contract defines the REST API endpoints exposed by the FastAPI backend server (`api.py`) to serve the React UI dashboard client.

All endpoints use standard JSON request/response formats. All success payloads match the `SessionState` JSON schema defined in `data-model.md`.

---

## 1. Get Cases List
Retrieve all available case sessions. Used for Case Navigation in the UI.

* **URL**: `/api/cases`
* **Method**: `GET`
* **Response (200 OK)**:
  ```json
  {
    "cases": {
      "PA-72148-A (Approved MRI)": { "request_id": "PA-72148-A", "review_status": "APPROVED", ... },
      "PA-96372-I (Incomplete Drug)": { "request_id": "PA-96372-I", "review_status": "PENDING", ... }
    }
  }
  ```

---

## 2. Ingest Case / Trigger Analysis Pipeline
Upload clinical document, parse content, and run Intake and Evidence agents.

* **URL**: `/api/cases/ingest`
* **Method**: `POST`
* **Request Header**: `Content-Type: multipart/form-data`
* **Form Parameters**:
  * `member_id` (`string`, optional)
  * `provider_id` (`string`, optional)
  * `cpt_code` (`string`, optional)
  * `icd_code` (`string`, optional)
  * `file` (`file`, optional): Clinical document notes (PDF/TXT) or structured request payload (JSON)
* **Response (200 OK)**: Updates `SessionState` and returns the populated case object, transitioning `currentStep` to `2`.

---

## 3. Policy Gap Assessment
Run the Gap Agent to analyze clinical evidence against retrieved guideline requirements.

* **URL**: `/api/cases/gap-analysis`
* **Method**: `POST`
* **Request Payload**:
  ```json
  {
    "case_id": "string",
    "cpt_code": "string",
    "raw_text": "string"
  }
  ```
* **Response (200 OK)**: Returns updated `SessionState` with checklist items under `gapAnalysis`.

---

## 4. Run Summary & Audit
Run the Summary Agent to compile the clinical brief and write the outreach correspondence draft, and the Audit Agent to compute the tamper-evident hash.

* **URL**: `/api/cases/summarize`
* **Method**: `POST`
* **Request Payload**:
  ```json
  {
    "case_id": "string"
  }
  ```
* **Response (200 OK)**: Returns updated `SessionState` with summary markdown text, outreach letter, compliance hash, and audit log elements.

---

## 5. Submit Triage Decision
Update the review status and target queue of the case with a audit trail log trace.

* **URL**: `/api/cases/triage`
* **Method**: `POST`
* **Request Payload**:
  ```json
  {
    "case_id": "string",
    "route": "Nurse Review" | "Information Request" | "Medical Director",
    "status": "PENDING" | "REQUEST MORE INFO",
    "communication_draft": "string"
  }
  ```
* **Response (200 OK)**: Returns updated status and a confirmation row to append to the Compliance Ledger table.
