<!--
╔══════════════════════════════════════════════════════════════╗
║  Sync Impact Report                                        ║
╠══════════════════════════════════════════════════════════════╣
║  Version change : (new) → 1.0.0                            ║
║  Bump rationale : Initial constitution ratification.        ║
║                                                             ║
║  Added sections:                                            ║
║    - Core Principles (10 principles, expanded from 5-slot   ║
║      template to match user-supplied governance scope)      ║
║      P1  Human-in-the-Loop Only                            ║
║      P2  Confidentiality & Full Data Locality               ║
║      P3  Hybrid Retrieval Mandatory                         ║
║      P4  Grounded, Cited, Fully Auditable                   ║
║      P5  Five-Agent Runtime with LLM-Driven Planner         ║
║      P6  Hardware-Aware GPU Sharing                         ║
║      P7  Role-Strict Access                                 ║
║      P8  Verification Integrity                             ║
║      P9  Secrets Management Abstraction from Day One        ║
║      P10 Spec-Driven Development Discipline                 ║
║    - Compliance & Regulatory Alignment                      ║
║    - Development Workflow                                   ║
║    - Governance                                             ║
║                                                             ║
║  Removed sections : (none — initial version)                ║
║  Deferred TODOs   : none                                    ║
╚══════════════════════════════════════════════════════════════╝
-->

# Prior Authorization Evidence Assistant Constitution

## Core Principles

### I. Human-in-the-Loop Only

No agent, workflow, or schema may represent, imply, or default to an
automated accept/reject outcome for a prior-authorization case. Every
case MUST reach an explicit, attributed, timestamped decision made by
a Nurse Reviewer before it is marked Accepted or Rejected.

- Routing MUST use explicit state fields (`case_status`, `queue`,
  `locked_by`, `lock_expires_at`, `decided_by`, `decided_at`).
- Hidden boolean routing flags (e.g. `human_review_required`) are
  forbidden; they obscure decision authority.
- The Workflow Agent's planner may never emit an accept/reject
  decision — only a `route-to-Nurse-Review` action.

**Rationale:** Delegating accept/reject authority to automation
violates regulatory expectations for clinical review and eliminates
the accountability trail that compliance audits require.

### II. Confidentiality & Full Data Locality

All uploaded material — policy documents, case documents,
member/provider data — is confidential. No document content,
embedding, prompt, or derived text may ever be sent to any public or
third-party hosted API.

- All inference (OCR, embeddings, LLM generation) MUST run on locally
  hosted / on-prem infrastructure with zero external egress for
  document content or PHI.
- Dev/test environments MUST use synthetic data only.

**Rationale:** PHI exposure to external services creates HIPAA
liability and undermines member trust. Full data locality is the only
architecture that provides unconditional compliance.

### III. Hybrid Retrieval Mandatory

Every retrieval path over policy or case documents MUST combine dense
semantic search with sparse/keyword search, fused with Reciprocal
Rank Fusion (RRF).

- Exact identifiers (Case ID, Member ID, CPT/HCPCS codes, ICD-10
  codes, policy names) MUST never be lost to embedding-only matching.
- Free-text concepts ("MRI", "conservative therapy") MUST still be
  found semantically.

**Rationale:** Healthcare prior-auth documents are identifier-dense.
Pure vector search silently drops exact codes; pure keyword search
misses semantic intent. RRF fusion eliminates both failure modes.

### IV. Grounded, Cited, Fully Auditable

Every evidence claim MUST carry a citation to a specific source
document, page/section, and a stable document UUID.

- Every agent action — Intake extraction, Retrieval query, Reasoning
  verdict, Summary generation, routing decision, human decision —
  MUST be logged with: timestamp, actor identity, model/version used,
  and confidence score.
- Logs MUST be sufficient to reconstruct full case history for
  compliance audit.

**Rationale:** Ungrounded AI-generated text is inadmissible in
utilization-review appeals. Full citation and audit logging provide
the evidentiary chain regulators and appeals boards require.

### V. Five-Agent Runtime with LLM-Driven Planner

The system operates five agents: Workflow, Intake, Retrieval,
Reasoning, and Summary. The Workflow Agent is an LLM-driven planner
(not a fixed-order script) that, at each turn, chooses one action
from a whitelisted action set.

- Allowed actions: invoke Intake Agent, invoke Retrieval Agent,
  invoke Reasoning Agent, invoke Summary Agent, request additional
  evidence, finalize and route to Nurse Review.
- Each planner choice and its stated reasoning MUST be written to the
  audit trail **before** execution.
- The planner may reorder, repeat, or skip steps to adapt to a given
  case (e.g. re-running Retrieval with a refined query after a
  low-confidence Reasoning verdict).

**Hard invariants (non-LLM, deterministic logic):**

- A per-case turn budget (e.g. 10 planner turns) forces deterministic
  finalization into the Nurse Review queue if exceeded — a case MUST
  never loop indefinitely or stall.
- The planner MUST never emit an accept/reject decision, only a
  route-to-Nurse-Review action.
- Summary Agent output is REQUIRED before finalization is allowed.
- The Workflow Agent owns case-status transitions, the audit trail,
  and the 24-hour case-lock release scheduler — these remain
  deterministic, non-LLM logic regardless of how the per-case
  pipeline itself is planned.

**Rationale:** An LLM planner adapts to case complexity (simple cases
skip unnecessary steps; ambiguous cases iterate) while hard
guardrails prevent unbounded execution and unauthorized decision-
making.

### VI. Hardware-Aware GPU Sharing

The local LLM (Ollama, llama3.2:3b — the sole model in use) runs
natively on the host with CUDA and always has GPU priority.

- OCR fallback (EasyOCR) and the embedding service may use GPU only
  when the LLM is not actively generating.
- An explicit in-process concurrency guard (e.g. a semaphore) MUST
  gate GPU-heavy calls; never assume the hardware can run all of them
  simultaneously.
- Never assume more VRAM headroom than the smallest GPU in the target
  deployment fleet actually provides.

**Rationale:** A single consumer-grade GPU cannot time-share LLM
inference with OCR and embedding workloads without OOM risk. An
explicit concurrency guard makes resource contention deterministic
rather than probabilistic.

### VII. Role-Strict Access

Three roles only: **Intake**, **Nurse**, **Admin**. JWT/OAuth2
self-hosted authentication.

- Each role reaches only its own section of the UI and its own API
  scopes; there is no shared "user" role.
- A Nurse MUST NOT see case summaries, AI evidence, or documents
  before locking a case — pre-lock visibility is limited to case
  heading and metadata only.

**Rationale:** Pre-exposing AI conclusions before a Nurse commits to
review introduces anchoring bias. Role isolation ensures clinical
independence and satisfies separation-of-duty audit requirements.

### VIII. Verification Integrity

Any modification an Admin makes to a case that a Nurse has already
Accepted or Rejected MUST immediately invalidate that decision.

- The case returns, unlocked, to the Nurse Review queue (available to
  any nurse, not necessarily the original one).
- The case MUST be clearly marked "Re-verification Required."

**Rationale:** A post-decision data change makes the original verdict
potentially unsound. Automatic re-queue preserves decision integrity
without relying on manual notification.

### IX. Secrets Management Abstraction from Day One

All credentials and connection strings MUST go through a
secrets-manager abstraction layer starting in Phase 1.

- This abstraction MUST NOT be retrofitted — it is a Phase 1
  architectural requirement.
- The abstraction layer MUST support swapping backends (e.g. env
  vars in dev, Vault/HSM in production) without code changes.

**Rationale:** Retrofitting secrets management into a running system
inevitably leaves plaintext credentials in config files, environment
snapshots, and CI logs. Building the abstraction first eliminates
that class of leak entirely.

### X. Spec-Driven Development Discipline

Every phase MUST produce its full specification set before
implementation begins.

- Run `/speckit-analyze` after every implementation phase, not just
  once before implementation starts.
- Specifications are living documents: implementation findings MUST
  feed back into spec updates.

**Rationale:** Spec drift is the root cause of most inter-component
contract failures. Phase-gated spec validation catches drift before
it compounds across dependent components.

## Compliance & Regulatory Alignment

- **HIPAA:** All data-handling, storage, and access controls MUST
  satisfy the HIPAA Privacy and Security Rules. Audit logs MUST be
  retained for a minimum of six years.
- **URAC / NCQA:** Turnaround-time tracking and decision
  documentation MUST support utilization-management accreditation
  standards.
- **State Regulations:** The system MUST be configurable for
  state-specific prior-authorization timelines and notification
  requirements without code changes.
- **PHI Minimization:** Agent prompts and logs MUST contain the
  minimum PHI necessary for the task. Summarization and reasoning
  outputs MUST NOT reproduce full patient records verbatim.

## Development Workflow

- **Spec-Kit Pipeline:** Every feature follows the SpecKit lifecycle:
  `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
  `/speckit-implement` → `/speckit-analyze` (post-implementation).
- **Synthetic Data Only in Dev/Test:** No production PHI may exist in
  any non-production environment. Synthetic data generators MUST
  produce realistic but fictional clinical scenarios.
- **Code Review Gates:** All PRs MUST verify compliance with this
  constitution. Reviewers MUST confirm no external API egress for
  document content and no automated accept/reject paths.
- **Testing Pyramid:** Unit tests for each agent's deterministic
  logic; integration tests for agent-to-agent contracts; end-to-end
  tests for full case workflows using synthetic data.

## Governance

- This constitution supersedes all other project practices,
  conventions, and ad-hoc decisions where a conflict exists.
- Amendments require: (1) a written proposal referencing the
  principle(s) affected, (2) review by the project lead, (3) an
  updated Sync Impact Report, and (4) a migration plan for any
  in-flight work affected by the change.
- All PRs and code reviews MUST verify compliance with the principles
  above. Non-compliance is a blocking review finding.
- Complexity beyond what these principles require MUST be justified in
  writing before implementation.
- Use `/speckit-analyze` as the runtime compliance check against this
  constitution.

**Version**: 1.0.0 | **Ratified**: 2026-08-08 | **Last Amended**: 2026-08-08
