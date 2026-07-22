# Research and Decisions: React UI Prior Auth Dashboard

This document details the architectural decisions, tech stack choices, and integration design patterns for migrating the Streamlit Prior Auth Dashboard to React, keeping the multi-agent backend intact.

---

## 1. Frontend Build Tool & Framework

### Decision
Use **Vite** with **React (JavaScript/TS)** for the frontend structure.

### Rationale
* **Lightweight and Fast**: Vite provides near-instant hot module replacement (HMR), making frontend design changes rapid and interactive.
* **Simple Integration**: Vite projects compile to static files that can easily be served or run independently alongside a local backend.
* **Next.js Overhead**: Next.js App Router introduces SSR and complex file-system routing which are unnecessary for a single-page human-in-the-loop review dashboard.

### Alternatives Considered
* **Next.js App Router**: Rejected due to unnecessary server-side rendering overhead, complex routing setup, and increased bundle sizes for a local prototype tool.

---

## 2. Component and Style Libraries

### Decision
Use **Tailwind CSS** with **Lucide React** icons. For UI components, we will implement custom responsive grid layouts and clean visual badges (glassmorphism look matching the design specs) natively in CSS/Tailwind, supplemented by Radix primitives if needed.

### Rationale
* **Tailwind CSS**: Offers absolute design control, utility-first classes, and enables glassmorphism styles, overlay filters (e.g., `backdrop-blur-sm`), and responsiveness matching the detailed column specs.
* **Lucide React**: Clean, lightweight SVG icon package that integrates seamlessly with React.

### Alternatives Considered
* **Component Framework (Chakra UI / Material UI)**: Rejected because their default styles are heavy and make custom layouts (like the 50/50 vertical split inside a specific column and custom stepper focus) harder to configure than utility CSS.

---

## 3. Backend Integration & API Layer

### Decision
Introduce a lightweight **FastAPI** server (`api.py` in the root) that wraps the existing agent logic (`IntakeAgent`, `EvidenceAgent`, `GapAgent`, `SummaryAgent`, `AuditAgent`) and serializes the `SessionState` to/from JSON.

### Rationale
* **FastAPI**: Extremely lightweight, fast, has automatic OpenAPI document generation, and natively supports Pydantic models which match our typed python constraints.
* **Compatibility**: Allows the exact same python backend files and agent pipelines to be run unmodified. We only capture the state transitions and expose them as JSON endpoints.

### Alternatives Considered
* **Flask**: Rejected as it does not natively support modern async features, type-based serialization (Pydantic), and automatic Swagger docs out of the box.

---

## 4. State Management and Synchronization

### Decision
Utilize standard React **`useState`** hooks mapped to synchronous fetch requests. Session state updates are sent to the backend endpoints, which return the updated case representation. The frontend updates its local React state using the returned JSON payload.

### Rationale
* **Simple Reactivity**: A full Redux or Context implementation is unnecessary since all dashboard columns operate on a single shared case object (`SessionState`).
* **Synchronous Updates**: Matching backend execution directly maps to visual step transitions (`currentStep`), guaranteeing consistency between UI and agent state.

### Alternatives Considered
* **Redux / Zustand**: Rejected as state is centralized on the backend; the frontend only acts as an interactive client representing the backend state.
