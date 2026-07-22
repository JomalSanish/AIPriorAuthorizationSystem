# Implementation Plan: React UI Prior Auth Evidence Dashboard

**Branch**: `004-react-ui-dashboard` | **Date**: 2026-07-13 | **Spec**: [spec.md](file:///c:/Users/gauth/OneDrive/Documents/Study/SpecKit/Test2/specs/004-react-ui-dashboard/spec.md)

**Input**: Feature specification from `/specs/004-react-ui-dashboard/spec.md`

## Summary

Migrate the Prior Auth Evidence Dashboard from a Streamlit UI to a modern React-based UI (Vite with TypeScript, Tailwind CSS, and Lucide React). The existing Python agent workflow logic (`IntakeAgent`, `EvidenceAgent`, `GapAgent`, `SummaryAgent`, `AuditAgent`) will remain unchanged. A lightweight FastAPI server will be introduced to wrap the existing agents and state models, exposing REST endpoints for the React frontend.

## Technical Context

**Language/Version**: TypeScript / React 18+ (Frontend), Python 3.11 (Backend)

**Primary Dependencies**: React, Tailwind CSS, Lucide React, FastAPI, Uvicorn, LangChain (existing)

**Storage**: In-memory session state (via `SessionState` on the Python backend), static json configuration (`mock_policies.json`)

**Testing**: Vitest/Jest (Frontend), pytest (Backend API endpoints)

**Target Platform**: Desktop web browsers (Chrome, Edge, Safari)

**Project Type**: Web application (React SPA + FastAPI backend)

**Performance Goals**: UI interaction latency < 100ms, RAG analysis response within LLM processing bounds (< 5s for typical agent chains).

**Constraints**: Local execution only. Frontend runs on `http://localhost:5173` and backend FastAPI on `http://localhost:8000`.

**Scale/Scope**: Single dashboard with a three-step stepper wizard mapping ingestion, policy RAG checklists, and operational routing queues.

## Constitution Check

_GATE: Must pass before Phase 0 research. Re-check after Phase 1 design._

- The implementation MUST use Python and a Streamlit-based UI for any user-facing workflow. **[VIOLATED - React UI explicitly requested by user. Documented in Complexity Tracking below]**
- The implementation MUST use LangChain-based multi-agent routing when multi-agent orchestration is required. **[PASSED]**
- All Python files MUST include explicit type hints. **[PASSED]**
- The prototype MUST rely on the available local policy PDF and in-memory state unless persistence is explicitly introduced. **[PASSED]**

## Project Structure

### Documentation (this feature)

```text
specs/004-react-ui-dashboard/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── checklists/
│   └── requirements.md  # Spec validation checklist
└── contracts/           # Phase 1 output
    └── openapi.json     # OpenAPI contract for backend REST endpoints
```

### Source Code (repository root)

```text
backend/
├── agents/             # Existing multi-agent logic
│   ├── intake_agent.py
│   ├── evidence_agent.py
│   ├── gap_agent.py
│   ├── summary_agent.py
│   └── audit_agent.py
├── state/              # Existing session state model
│   └── session_state.py
├── utils/              # Existing utilities
├── tests/              # Pytest endpoint validation
│   └── test_api.py
└── api.py              # NEW: FastAPI wrapper exposing agent endpoints

frontend/               # NEW: React UI SPA project root
├── public/
├── src/
│   ├── components/     # UI wizard panels (Ingestion, Policy Check, Triage, Compliance)
│   ├── services/       # API integration client
│   ├── App.jsx         # App router and wizard state coordinator
│   ├── index.css       # Tailwind stylesheet
│   └── main.jsx
├── package.json
├── tailwind.config.js
└── vite.config.js
```

**Structure Decision**: Expose the backend via `backend/` components and introduce a dedicated `frontend/` React project initialized via Vite. During dev, Vite dev server will proxy `/api` requests to Uvicorn running on port 8000.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| React UI migration (Deviates from Streamlit-First constraint) | User explicitly requested a premium, fully customized React UI with advanced layouts (3-column layout with conditional blur overlays, split vertical panels, and custom stepper wizard). | Streamlit does not natively support advanced, stateful vertical split-pane layouts and column-specific overlays without custom HTML/JS hacks that compromise style and reactivity constraints. |
