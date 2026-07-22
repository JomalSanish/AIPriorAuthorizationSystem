# Quickstart Validation Guide: React UI Prior Auth Dashboard

This guide provides instructions to run and validate the React-based Prior Auth Evidence Dashboard with the FastAPI backend wrapper.

---

## 1. Prerequisites

* **Node.js**: v18.0.0 or higher
* **Python**: v3.11.0 or higher
* **OpenAI API Key**: Exported as environment variable `OPENAI_API_KEY` (or entered in the UI settings sidebar)
* **Backend API Contract**: [api-spec.md](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/specs/004-react-ui-dashboard/contracts/api-spec.md)
* **Data Model Specs**: [data-model.md](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/specs/004-react-ui-dashboard/data-model.md)

---

## 2. Server & Frontend Setup

### Step A: Start the FastAPI Backend
Expose the Python multi-agent pipeline as REST endpoints using FastAPI and Uvicorn.
1. Run backend server:
   ```bash
   pip install fastapi uvicorn pydantic python-multipart
   python api.py
   ```
2. Confirm the API runs and Swagger docs are served at `http://localhost:8000/docs`.

### Step B: Build & Start the React Frontend
Initialize the frontend project and launch the Vite development server.
1. Move to the frontend folder and install packages:
   ```bash
   cd frontend
   npm install
   ```
2. Start the Vite dev server:
   ```bash
   npm run dev
   ```
3. Open the browser to `http://localhost:5173`.

---

## 3. End-to-End Validation Scenario

Follow these validation steps to confirm the dashboard operates correctly:

### Scenario 1: Case Ingestion (Step 1)
1. **Action**: Open the UI. Step 1 stepper must be highlighted. Columns 2 and 3 must have a disabled opacity overlay.
2. **Action**: Drag and drop the test clinical document `pcp_notes.txt` into the upload box.
3. **Action**: Click `[ Run Agentic Analysis Pipeline ]`.
4. **Expected Outcome**:
   * Extracted demographics (Member ID, provider ID) fill the demographics badge in Column 1.
   * Stepper moves to Step 2.
   * Column 2 is unblurred and active.

### Scenario 2: Policy Verification Check (Step 2)
1. **Action**: Expand a checklist accordion criterion in Column 2.
2. **Expected Outcome**:
   * The accordion expands to show the `Step-by-Step Reasoning` text block.
   * Column 2 splits 50/50 vertically.
   * The left split highlights the relevant clinical note passage.
   * The right split shows the raw policy text criteria.
3. **Action**: Click `[ Proceed to Route ]`.
4. **Expected Outcome**:
   * Stepper moves to Step 3.
   * Column 3 is unblurred and active.

### Scenario 3: Human Triage & Audit (Step 3)
1. **Action**: Review the generated clinical summary brief.
2. **Action**: Verify the pre-populated outreach letter (it must list missing documents if criteria are `ABSENT` or `UNCLEAR`).
3. **Action**: Edit the letter draft natively, then click `[ Route to Nurse ]`.
4. **Expected Outcome**:
   * Success toast appears.
   * A new row is added to the table in the collapsible Bottom Compliance Trail drawer with details: timestamp, action (`Route to Nurse Review Queue`), responsible actor, and a SHA-256 validation hash.
