# UI Specification

## Tech Stack (T002)
- React, TypeScript, Vite, React Router, Axios.

## General Navigation (T034, T037, FR-003)
- Role-gated Sidebar with sections: Case Management, Nurse Review, Admin Dashboard.
- React Router protected routes redirecting unauthenticated users to `/login`.

## Pages & Components

### Case Management (Intake)
- **New Case** (T042): Multi-file upload, LLM metadata extraction trigger, editable fields (FR-012), submit button with warning on OCR failure (FR-013a).
- **Case Management** (T043): List of cases with status badges and SLA clocks.

### Nurse Review (Nurse)
- **Queue** (T061): Metadata-only view. No summary or documents visible pre-lock (FR-023). Lock button.
- **Case Detail** (T062-065): Only accessible post-lock. Shows Evidence Summary with Gap Checklist (Absent/Unclear) and Document Viewer. Decision panel (Accept/Reject + mandatory comment) (FR-028).
- **History** (T066): View previously decided cases.

### Admin Dashboard (Admin)
- **All Cases** (T070): View all cases. Inline edit action (invalidates decision, FR-032).
- **Nurse Workload** (T072): View locked/decided counts.
- **Audit Log Viewer** (T071): Filterable chronological case timeline (FR-041).

### Global Components
- **SearchBar** (T049): NLP search input with debouncing.
- **CaseCard** (T044): Reusable card for cases in queues.
