# API Specification

## Auth (T012, T014, FR-001)
- `POST /api/auth/login` (Public): Validates credentials, returns JWT tokens.
- `POST /api/auth/refresh` (Public): Silent refresh mechanism.
- `GET /api/auth/me` (Authenticated): Returns current user info and role.

## Admin — User Management (T014, FR-034)
- `POST /api/admin/users` (Admin): Create a new user account (username, password, role).
- `GET /api/admin/users` (Admin): List all user accounts with role and active status.
- `PATCH /api/admin/users/{user_id}` (Admin): Deactivate a user account (soft-delete).

## Policies (T032, FR-005, FR-009a)
- `POST /api/policies` (Admin): Upload policy document + name; triggers ingestion.
- `GET /api/policies` (All): List active policies (name + id) for dropdowns.
- `GET /api/policies/{policy_id}` (Admin): Full policy detail.
- `PATCH /api/policies/{policy_id}` (Admin): Deactivate policy (soft delete).

## Cases (T038, T048, FR-010, FR-012, FR-035)
- `POST /api/cases` (Intake): Create case draft with policy_id.
- `POST /api/cases/{case_id}/documents` (Intake): Multi-file upload, triggers processing.
- `POST /api/cases/{case_id}/extract-metadata` (Intake): Triggers LLM metadata extraction.
- `POST /api/cases/{case_id}/submit` (Intake): Submits case, sets SLA start, triggers pipeline.
- `GET /api/cases` (Intake, Admin): List cases.
- `GET /api/cases/{case_id}` (Role-scoped): View case details.
- `POST /api/cases/search` (All): NLP case search (hybrid case profile search).

## Nurse Review (T058, T060, FR-023, FR-024, FR-028)
- `GET /api/nurse-review/queue` (Nurse, Admin): Metadata-only view of queue.
- `POST /api/nurse-review/{case_id}/lock` (Nurse): Acquire 24h lock.
- `DELETE /api/nurse-review/{case_id}/lock` (Nurse, Admin): Release lock.
- `POST /api/nurse-review/{case_id}/decide` (Nurse lock owner): Submit accept/reject with comment.
- `GET /api/nurse-review/history` (Nurse, Admin): View decided cases history.

## Admin (T068, T069, FR-030, FR-032, FR-041)
- `PATCH /api/admin/cases/{case_id}` (Admin): Modify case fields. Invalidates decisions if already accepted/rejected (triggers re-verification).
- `GET /api/admin/cases` (Admin): All-cases view.
- `GET /api/admin/nurses/workload` (Admin): View nurse workload.
- `GET /api/admin/nurses/{nurse_id}/history` (Admin): View any nurse's decided-case history (FR-029a).
- `GET /api/admin/audit/{case_id}` (Admin): Chronological audit trail for a case.
- `GET /api/admin/audit` (Admin): Global audit log search.

## System
- `GET /api/health` (Public): Returns health status of all dependent services — Postgres, Qdrant, TEI, MinIO, Ollama (T091). Used by the startup sequence and external monitoring.