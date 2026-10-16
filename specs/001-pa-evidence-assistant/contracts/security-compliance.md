# Security & Compliance Specification

## Authentication & Roles (T009-T012, FR-001, FR-001a, FR-001b, FR-002, FR-003, FR-003a)
- Self-hosted JWT/OAuth2. Short-lived access tokens (default 15 min) + longer-lived refresh
  tokens (default 7 days). Login and refresh endpoints are the only routes accessible without a
  valid token (FR-001a).
- Silent refresh on mid-session access-token expiry; if the refresh token is also invalid, the
  user must re-authenticate — but case locks are tied to the case and the 24-hour timer, not to
  the session, so a forced re-login never releases a lock or loses in-progress review state
  (FR-001b).
- Three strict roles: Intake, Nurse, Admin. No shared generic "user" role (FR-002).

**API Scope Matrix (FR-003a)** — a role's token only carries the scopes listed for it:

| Role | Scopes |
|---|---|
| Intake | `case:create`, `case:read` (all cases), `document:upload`, `policy:read` (name list only) |
| Nurse | `case:read` (queue + own locked/decided cases), `case:lock`, `case:decide`, `history:read` (own only) |
| Admin | `case:*`, `policy:*`, `user:manage`, `audit:read`, `history:read` (any nurse) |

- Failed auth attempts logged to audit trail (FR-040b). Denied cross-role access attempts also
  logged (FR-040c).
- Pre-lock Nurse access is strictly metadata-only (FR-023). A Nurse's History view is limited to
  their own decisions; Admin may view any nurse's History read-only (FR-029a).
- The full case audit trail is Admin-only; Nurse visibility is limited to their own History;
  Intake has no audit trail access (FR-041a).

## Secrets Management (T003, T003a, FR-004)
- `SecretsProvider` abstraction layer.
- Credential access triggers operational security logs showing key names (FR-040f).

## Audit Logging (T053, FR-040)
- Immutable, append-only `AuditLog` table.
- Logs capture timestamp, actor, action, model details, confidence scores, and reasoning.
- Human decisions and planner decisions explicitly recorded.

## Data Locality & PHI Minimization (T092, FR-043, Constitution P2)
- **Zero public API egress.** Static analysis gate (`check_locality.py`) enforces this in CI.
- Document content/tokens are never stored in browser `localStorage` or `sessionStorage` (FR-043c).
- Local Ollama and TEI handle all inference.
- Synthetic data only in non-production environments (FR-044).
