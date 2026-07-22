# Quickstart & Verification Guide: Prior Authorization Evidence Assistant

This guide explains how to set up, run, and verify the Payer Prior Authorization Evidence Assistant.

## 1. Prerequisites & Environment Setup

1. **API Keys**:
   Create a `.env` file in the project root directory and add your OpenAI API Key:
   ```env
   OPENAI_API_KEY=your-actual-api-key-here
   ```

2. **Activate Virtual Environment**:
   If not already activated, activate the project's virtual environment:
   - On Windows (PowerShell):
     ```powershell
     .venv\Scripts\activate
     ```
   - On Linux/macOS:
     ```bash
     source .venv/bin/activate
     ```

3. **Install Dependencies**:
   Install requirements including new RAG packages:
   ```bash
   pip install -r requirements.txt
   ```

---

## 2. Running the Dashboard Application

Start the Streamlit application:
```bash
streamlit run app.py
```
Streamlit will launch the web application in your default browser (usually at `http://localhost:8501`).

---

## 3. End-to-End Verification Scenarios

### Scenario A: Intake Associate - Document Ingestion & Completeness Check
- **Steps**:
  1. Open the application.
  2. Navigate to the **Ingest & Upload** tab.
  3. Enter Member ID: `M123` and Provider ID: `P456`.
  4. Select Service Type: `Imaging` and enter CPT Code: `72148` (Lumbar Spine MRI).
  5. Upload a medical record PDF or paste the clinical notes:
     > *"Patient reports severe lower back pain for 8 weeks radiating to the left leg. Has attempted physical therapy for 4 weeks with no improvement. Requesting MRI of lumbar spine."*
  6. Click **Run AI Pipeline**.
- **Expected Outcome**:
  - The status updates to **Ready for Evidence Review**.
  - The Intake queue displays the case metadata parsed from the text.
  - No mandatory fields are marked missing.

### Scenario B: Nurse Reviewer - RAG Evidence Retrieval & Policy Gap Check
- **Steps**:
  1. Run the pipeline as described in Scenario A.
  2. Navigate to the **Nurse Review Queue** tab.
  3. Expand the **Retrieved Policy Evidence** card.
- **Expected Outcome**:
  - Excerpts from `prior-authorization-and-step-therapy-guidelines.pdf` regarding MRI Lumbar Spine criteria are shown.
  - The Checklist lists `6 weeks conservative therapy` with status `Absent` (since clinical note only says 4 weeks) and `Neurological symptoms` as `Present`.
  - The Final Review Decision displays **REQUEST MORE INFO** (due to missing 6-week therapy gap).

### Scenario C: Auditor - Compliance Audit Trail
- **Steps**:
  1. Complete a pipeline run.
  2. Switch to the **Auditor Queue** tab.
- **Expected Outcome**:
  - The tab displays a full chronological table of agent operations (e.g., `IntakeAgent: Classification complete`, `EvidenceAgent: Retrieval complete`, etc.).
  - A SHA-256 validation compliance hash is displayed (e.g. `Audit finalized: a1b2c3d4e5f6`).

---

## 4. Running Automated Tests

Run the pipeline verification suite using pytest:
```bash
pytest tests/
```
Verify that all tests pass, validating state structure, RAG index creation, and agent execution.
