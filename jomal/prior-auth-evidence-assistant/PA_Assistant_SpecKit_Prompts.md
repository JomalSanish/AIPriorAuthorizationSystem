# Prior Authorization Evidence Assistant — Spec-Kit Prompt Pack (Custom 5-Agent Architecture)

This is a ready-to-paste prompt pack for building this app with GitHub Spec-Kit, following the
official workflow order:

```
/speckit.constitution → /speckit.specify → /speckit.clarify → /speckit.checklist →
/speckit.plan → /speckit.tasks → /speckit.analyze → /speckit.implement
```

**This is a from-scratch architecture** — a single Workflow Agent that acts as an LLM-driven
planner coordinating four worker agents (Intake, Retrieval, Reasoning, Summary), designed
specifically for on-prem, GPU-constrained hardware, where dev and target machines may not have
identical GPU headroom. It intentionally does not reuse the older 5-agent split (Intake / Evidence
RAG / Policy Gap / Reviewer Summary / Workflow-Audit) from any prior architecture document — here,
Workflow *is* the orchestrator and audit owner, not a peer agent at the end of the chain. The
planner is free to reorder, repeat, or skip steps adaptively rather than following one fixed
sequence — but it operates inside hard guardrails (a bounded step budget, a whitelist of allowed
actions, and mandatory audit logging of every decision) so it can never get stuck in a loop or
autonomously accept/reject a case.

Don't skip `/speckit.clarify`, `/speckit.checklist`, or `/speckit.analyze` — regulatory,
confidentiality, and hardware-budget constraints all need active gates, not just a one-time read.

## 0. Project setup

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
specify init pa-evidence-assistant --integration claude
cd pa-evidence-assistant
```

(Swap `claude` for your agent's integration key if using a different coding agent.)

---

## 1. `/speckit.constitution`

Paste as-is.

```
Prior Authorization Evidence Assistant — non-negotiable principles:

1. Human-in-the-loop only. No agent, workflow, or schema may represent, imply, or default to an
automated accept/reject outcome for a case. Every case reaches an explicit, attributed, timestamped
decision made by a Nurse Reviewer before it is marked Accepted or Rejected. Never model routing as
a hidden boolean (no `human_review_required`-style flag) — use explicit state fields instead
(`case_status`, `queue`, `locked_by`, `lock_expires_at`, `decided_by`, `decided_at`).

2. Confidentiality and full data locality, no exceptions. All uploaded material (policy documents,
case documents, member/provider data) is confidential. No document content, embedding, prompt, or
derived text may ever be sent to any public or third-party hosted API. All inference — OCR,
embeddings, LLM generation — runs on locally hosted / on-prem infrastructure with zero external
egress for document content or PHI. Dev/test environments use synthetic data only.

3. Hybrid retrieval is mandatory everywhere. Every retrieval path over policy or case documents
combines dense semantic search with sparse/keyword search, fused with Reciprocal Rank Fusion (RRF),
so exact identifiers (Case ID, Member ID, CPT/HCPCS, ICD-10 codes, policy names) are never lost to
embedding-only matching, while free-text concepts ("MRI", "conservative therapy") are still found
semantically.

4. Grounded, cited, fully auditable. Every evidence claim carries a citation to a specific source
document, page/section, and a stable document UUID. Every agent action — Intake extraction,
Retrieval query, Reasoning verdict, Summary generation, routing decision, human decision — is
logged with timestamp, actor identity, model/version used, and confidence score, sufficient to
reconstruct full case history for compliance audit.

5. Five-agent runtime, LLM-driven planner with hard guardrails. The Workflow Agent is an
LLM-driven planner (not a fixed-order script) that, at each turn, chooses one action from a
whitelisted action set — invoke Intake Agent, invoke Retrieval Agent, invoke Reasoning Agent,
invoke Summary Agent, request additional evidence, or finalize and route to Nurse Review — and
that choice, plus its stated reasoning, is written to the audit trail before it is executed. The
planner may reorder, repeat, or skip steps to adapt to a given case (e.g. re-running Retrieval with
a refined query after a low-confidence Reasoning verdict) rather than following one rigid sequence.
Regardless of the path taken, hard invariants always hold: a per-case turn budget (e.g. 10 planner
turns) forces deterministic finalization into the Nurse Review queue if exceeded, so a case can
never loop indefinitely or stall; the planner can never emit an accept/reject decision itself,
only ever a route-to-Nurse-Review action; and Summary Agent output is required before finalization
is allowed. The Workflow Agent also owns case-status transitions, the audit trail, and the 24-hour
case-lock release scheduler — these remain deterministic, non-LLM logic regardless of how the
per-case pipeline itself is planned.

6. Hardware-aware GPU sharing. The local LLM (Ollama, llama3.2:3b — the sole model in use)
runs natively on the host with CUDA and always has GPU priority. The OCR fallback (EasyOCR) and the
embedding service may use GPU only when the LLM is not actively generating; implement an explicit
in-process concurrency guard (e.g. a semaphore) around GPU-heavy calls rather than assuming the
hardware can run all of them simultaneously. Never assume more VRAM headroom is available than the
smallest GPU in the target deployment fleet actually provides.

7. Role-strict access. Three roles only: Intake, Nurse, Admin. JWT/OAuth2 self-hosted
authentication. Each role reaches only its own section of the UI and its own API scopes; there is
no shared "user" role. A Nurse never sees case summaries, AI evidence, or documents before locking
a case — pre-lock visibility is limited to case heading and metadata only.

8. Verification integrity. Any modification an Admin makes to a case that a Nurse has already
Accepted or Rejected immediately invalidates that decision: the case returns, unlocked, to the
Nurse Review queue (available to any nurse, not necessarily the original one) and is clearly marked
"Re-verification Required."

9. Secrets management abstraction from day one, never retrofitted. All credentials and connection
strings go through a secrets-manager abstraction layer starting in Phase 1.

10. Spec-Driven Development discipline. Every phase produces its full specification set before
implementation begins. Run /speckit.analyze after every implementation phase, not just once before
implementation starts.
```

---

## 2. `/speckit.specify`

Focus on *what* and *why* — tech stack is finalized separately below and confirmed again in
`/speckit.plan`.

```
Build the Prior Authorization Evidence Assistant: an on-prem payer-side web application that helps
payer operations staff process prior authorization (PA) requests, without the system itself ever
making the accept/reject decision.

Target users / roles (exactly three, JWT/OAuth2-authenticated, strictly separated):
- Intake: creates new PA cases and uploads case documents (PDF, DOCX, TXT, MD, and scanned
  images/faxes) in any combination.
- Nurse: reviews cases routed to the Nurse Review queue, locks a case to themselves before seeing
  any detail, inspects the AI-generated evidence summary and/or the raw documents, and records an
  Accept or Reject decision with a comment.
- Admin: uploads and names policy documents, manages policies, sees every case across every queue,
  can intervene/modify any case, sees which nurse has a case locked or has verified it, and manages
  nurse accounts.

Core workflow:

1. Policy ingestion (Admin). Admin uploads a policy document and manually assigns it a
human-readable Policy Name (the system never asks the admin to invent or enter a policy ID — IDs
are system-generated). The Intake Agent parses the document, builds hybrid (dense+sparse) index
entries for it, and extracts the definitive list of required evidence items for that policy (e.g.
"6 weeks conservative therapy," "neurological symptom documentation"). Elsewhere in the app, this
Policy Name (not its ID) is what's shown in the policy-selection dropdown.

2. Case creation (Intake). The Intake user starts a new case, uploads one or more case documents,
and selects the governing policy from a dropdown populated by policy name. Rather than requiring
every field to be typed manually, the system auto-extracts what it can from the uploaded documents
(member ID, provider ID, CPT/HCPCS code, ICD-10 code, service type) via the Intake Agent and
pre-fills the case form; the Intake user reviews/corrects these before final submission. Documents
that aren't natively text-extractable (scanned PDFs, photographed forms) are passed through an OCR
fallback so no document type blocks processing.

3. Automated pipeline (Workflow Agent, LLM-driven planner). Once submitted, the Workflow Agent — an
LLM-driven planner, not a fixed script — plans and executes a sequence of agent calls that
typically resembles: Intake Agent (embed + index the new case documents into the vector store) →
Retrieval Agent (hybrid, RRF-fused search that, for each policy requirement, retrieves the
case-document chunks most likely to satisfy it) → Reasoning Agent (for each policy requirement,
classifies Present / Absent / Unclear with a citation and confidence score, by comparing retrieved
case evidence against the requirement) → Summary Agent (produces a nurse-facing evidence summary
and gap checklist) — but the planner may adapt this, for instance re-invoking Retrieval with a
refined query when a Reasoning verdict comes back low-confidence, rather than always following the
exact same order. Every planner decision (chosen action + reasoning) and every agent step is logged
for audit, a bounded turn budget guarantees the pipeline always terminates, and the case is always
placed in the Nurse Review queue at the end regardless of outcome — this pipeline never accepts or
rejects a case itself, no matter what path the planner takes to get there.

4. Nurse review. In the Nurse Review section, a nurse initially sees only case heading and metadata
(Case ID, service, submitted date, SLA clock) — never the summary, evidence, or documents — until
they explicitly lock the case to themselves. Once locked, no other nurse can open it. Locks
auto-release after 24 hours of inactivity. After locking, the nurse can choose to read the AI
evidence summary/gap checklist, or open and inspect the underlying documents directly, or both, and
then records an explicit Accept (with comment) or Reject (with comment) decision. Every case the
nurse has accepted or rejected appears in that nurse's personal History view.

5. NLP case search. Across Case Management, Nurse Review, and the Admin dashboard, users can search
in natural language (e.g. "MRI cases" or "cases for provider ABC Health") and get back the matching
list of cases. This must never work by having the LLM read through case documents or case records
at query time — that doesn't scale and reintroduces exactly the kind of unbounded LLM-does-everything
behavior the rest of this architecture avoids. Instead, a lightweight LLM call translates the free-
text query into a structured search request (a semantic query string plus any extracted filters —
CPT/ICD code, provider name, member ID, date range, case status), and that structured request is
what actually executes against the existing hybrid (dense+sparse, RRF-fused) index over case_profile
points — the same retrieval infrastructure used for policy-requirement matching, not a separate
document-reading pass. Exact identifiers resolve via the extracted-filter/keyword path; conceptual
or free-text terms (procedure names, symptoms) resolve via the semantic path; both are fused
together.

6. Admin oversight and intervention. Admin sees all cases across all queues, who has each case
locked, and its verification status. Admin can modify case data directly. Any such modification
after a Nurse decision immediately and automatically invalidates that decision and routes the case
back into the (unlocked) Nurse Review queue, clearly flagged "Re-verification Required."

7. Full audit trail. Every agent action, every retrieval, every routing decision, and every human
decision (nurse accept/reject, admin edit) is logged with actor, timestamp, model/version, and
confidence — reconstructible into a complete per-case history.

Functional requirements: three-role JWT/OAuth2 auth with strict route/section separation; policy
upload + admin-named policy registry + policy-name dropdown (not ID) in case creation; multi-format
document upload (PDF/DOCX/TXT/MD/images) with OCR fallback for non-text-extractable documents;
auto-extraction of case metadata from uploaded documents with human confirmation step; hybrid
(dense+sparse, RRF-fused) retrieval over a single vector collection covering both policy and case
documents; an LLM-driven Workflow Agent planner (with a bounded turn budget and audit-logged
decisions) orchestrating Intake/Retrieval/Reasoning/Summary agents
in fixed order; NLP case search returning case lists (not just chunks); case locking with 24-hour
automatic release; Nurse pre-lock metadata-only visibility; Nurse Accept/Reject with mandatory
comment and per-nurse history; Admin case intervention with automatic re-verification routing;
full audit logging of every agent and human action; a Nurse-count and per-nurse workload/lock view
for Admin.

Out of scope: automated approval/denial of any kind by the system; final clinical decisioning by
the system; real payer system integration (mocked only); real PHI in development; claims/payment
adjudication; regulatory/legal determination; sending any document content to a public/hosted API.

Sample interactions to account for: "Create a new PA case", "What evidence supports this request?",
"What documents are missing?", "Summarize this case", "Show me all MRI-related cases", "Which
nurse has this case locked?", "Show the audit trail for this case", "What happens if no evidence is
found for a requirement?", "Why did this case need re-verification?"
```

---

## 3. `/speckit.clarify`

Run as-is; this walks Spec-Kit's structured clarification loop against `spec.md`. Steer it toward
these areas if it doesn't surface them on its own — they're the highest-ambiguity spots in this
particular spec:

```
Please prioritize clarifying questions in these areas, since they carry the most downstream risk
for this project:
1. Exact confidence-scoring formula for the Reasoning Agent's Present/Absent/Unclear verdicts (how
   retrieval score and LLM-reported confidence combine into one number shown to the nurse).
2. Precise behavior when a case document produces zero OCR-extractable text at all (fully blank
   scan / corrupted file) — what state does that document and the case enter?
3. What "Unclear" means operationally versus "Absent" for a policy requirement, and whether nurses
   can distinguish the two in the UI.
4. Exact SLA clock definition (what starts it, what pauses it, e.g. does it pause while a case is
   locked?).
5. Whether an Intake user can edit/resubmit a case after creation but before it's picked up by a
   nurse, and how that interacts with an in-flight Workflow Agent pipeline run.
6. GPU contention guard behavior in detail: does an OCR or embedding request that arrives while the
   LLM is generating queue and wait, or fall back to CPU immediately? Confirm this is configurable
   per-deployment rather than hardcoded, since dev and target hardware may have different GPU
   headroom.
```

---

## 4. `/speckit.checklist`

```
Generate a requirements-quality checklist (not a test-execution checklist) for this spec, covering
at minimum: role/permission completeness (every screen mapped to exactly one of Intake/Nurse/Admin,
no ambiguous shared access), data-locality completeness (every inference step confirmed as
on-prem/local with no public API path), audit-completeness (every state-changing action has a
corresponding audit log requirement), and hardware-budget completeness (every GPU-using component
has an explicit behavior defined for GPU contention/unavailability).
```

---

## 5. `/speckit.plan`

This is where the finalized tech stack is locked in. Paste as-is.

```
Technical architecture for the Prior Authorization Evidence Assistant:

RUNTIME TOPOLOGY (hardware-aware, minimal Docker footprint)
- Backend (FastAPI, Python) runs NATIVELY on the host — not containerized — so it has direct,
  simple access to the local GPU-using libraries (EasyOCR) without Docker GPU-passthrough
  complexity on Windows.
- Frontend (React + TypeScript) runs NATIVELY on the host (Vite dev server for dev, static build
  served by the backend or a lightweight server for anything closer to production).
- Ollama runs NATIVELY on the host with CUDA already configured, serving llama3.2:3b as the sole
  model, reachable at http://localhost:11434.
- Docker is used for: PostgreSQL, Qdrant, the embedding service (Hugging Face
  Text-Embeddings-Inference, CUDA image, serving BAAI/bge-small-en-v1.5), and MinIO for raw
  document storage. Keep this to exactly these four containers — still no Redis, no Celery, no
  reverse-proxy container for local/dev use. MinIO is lightweight (no GPU usage, modest CPU/RAM
  footprint) and gives S3-compatible object storage with none of the operational awkwardness of
  managing raw files directly on the host filesystem — worth the one extra container.

DATA LAYER
- PostgreSQL: all relational data — users (role: intake/nurse/admin), cases, case_documents,
  policies, policy_requirements, nurse_decisions, case_locks, audit_log. No separate audit
  datastore; audit_log is a Postgres table with an append-only access pattern enforced at the
  application layer (no UPDATE/DELETE on this table from app code).
- MinIO (S3-compatible, self-hosted, on-prem) for raw uploaded files, bucketed per environment
  (e.g. `pa-case-documents`), object key convention `{case_id}/{document_id}.{ext}`; object key +
  sha256 hash + doc_type stored in Postgres. Access via the standard S3 API/SDK pointed at the
  local MinIO endpoint — never a public cloud bucket.
- Qdrant: a SINGLE collection (e.g. `pa_documents`) holding three kinds of points, distinguished by
  a `doc_type` payload field: `policy_chunk`, `case_document_chunk`, and `case_profile` (one
  lightweight aggregated point per case — metadata + document titles + generated summary — that
  powers NLP case search without needing a separate search index). Each point carries both a dense
  vector (bge-small-en-v1.5, 384-dim) and a sparse vector (Qdrant-native BM25-style sparse encoding
  via fastembed) for hybrid search, fused at query time with Reciprocal Rank Fusion (RRF). No
  reranking step in v1 — RRF fusion alone is the retrieval quality bar for this release.

DOCUMENT INGESTION / OCR
- PDF: PyMuPDF for native text extraction first; if a page has no extractable text layer, rasterize
  that page to an image and route it through the preprocessing + OCR path below.
- DOCX: python-docx.
- TXT/MD: direct read.
- Images (scanned forms/faxes uploaded directly, and rasterized PDF pages from above): preprocess
  before OCR, not raw-into-EasyOCR. Preprocessing pipeline (OpenCV): grayscale conversion, deskew
  (detect and correct rotation/skew common in faxed or photographed forms), denoise, adaptive
  binarization/thresholding, and contrast normalization. This step measurably improves OCR accuracy
  on the kind of low-quality scans/faxes payer intake pipelines actually receive, and is cheap
  (CPU-only, no GPU/LLM contention) relative to the accuracy it buys. Only the preprocessed image is
  passed to EasyOCR (GPU).
- GPU contention guard: implement an in-process concurrency primitive (e.g. asyncio.Semaphore or an
  explicit lock) so EasyOCR GPU calls and Ollama LLM calls are never issued concurrently — LLM
  generation has priority; queue OCR requests behind it, with a configurable timeout after which OCR
  falls back to CPU mode rather than blocking indefinitely. Make the "GPU priority" policy and the
  CPU-fallback timeout both configuration values, not hardcoded, since dev hardware may have more
  GPU headroom than target deployment hardware.

FIVE-AGENT RUNTIME (Workflow Agent is an LLM-driven planner that coordinates the other four worker
agents; it may reorder/repeat/skip steps adaptively, inside hard guardrails)
- Workflow Agent: at each planning turn, prompts the LLM (structured JSON output) with the current
  case state, the history of actions already taken this case, and the fixed whitelist of allowed
  actions (`call_intake_agent`, `call_retrieval_agent`, `call_reasoning_agent`, `call_summary_agent`,
  `request_additional_evidence`, `finalize_to_nurse_review`). The LLM returns exactly one action +
  its reasoning; a Python validation layer rejects anything outside the whitelist and re-prompts on
  a malformed response. Every turn (chosen action, reasoning, and execution result) is written to
  audit_log before the next turn begins. Hard guardrails, enforced in code rather than left to the
  LLM: a per-case turn budget (default 10) that forces `finalize_to_nurse_review` once reached;
  `finalize_to_nurse_review` is only accepted as valid if Summary Agent has produced output at least
  once this case; the planner can never emit anything resembling an accept/reject verdict — that
  action simply doesn't exist in its action set. The Workflow Agent also owns case_status
  transitions, the audit trail schema, and the in-process APScheduler job that auto-releases case
  locks older than 24 hours — these remain deterministic, non-LLM logic.
- Intake Agent: (a) during policy ingestion — parses a policy document, extracts required-evidence
  items via the LLM with a structured-output prompt, chunks and embeds the policy text into Qdrant
  as `policy_chunk` points; (b) during case submission — runs the OCR/parsing pipeline above on
  each uploaded case document, extracts candidate case metadata (member/provider/CPT/ICD/service
  type) via the LLM for the Intake user to confirm, chunks and embeds case documents into Qdrant as
  `case_document_chunk` points, and (re)generates/updates the case's `case_profile` point.
- Retrieval Agent: for each policy requirement tied to the case's policy, issues a hybrid
  (dense+sparse, RRF-fused) query scoped to that case's `case_document_chunk` points, returning
  top-k candidate chunks with scores and citations; when the Workflow Agent re-invokes it with a
  refined query (e.g. after a low-confidence Reasoning verdict), it accepts that refinement as an
  optional query-augmentation parameter. Also serves the NLP case-search feature, in two stages: (1)
  a small LLM call — Query Understanding — parses the user's free-text search into a structured
  request (`semantic_query: str`, `filters: {cpt_code?, icd_code?, member_id?, provider_id?,
  date_range?, status?, policy_name?}`); (2) that structured request executes as a normal hybrid
  query against `case_profile` points — extracted filters apply as exact Qdrant payload filters /
  Postgres lookups, `semantic_query` drives the dense side, and any remaining free text also feeds
  the sparse side. The LLM's role here is strictly translating intent into a structured query — it
  never reads through case documents or case records to "find" the answer itself; that would neither
  scale nor stay within the turn/latency budget of an interactive search bar.
- Reasoning Agent: given a policy requirement and its retrieved candidate chunks, uses the LLM to
  classify Present / Absent / Unclear, attaches a citation (document + location) for Present/
  Unclear verdicts, and computes a confidence score combining retrieval-score signal and the LLM's
  self-reported confidence.
- Summary Agent: given the full set of Reasoning Agent verdicts for a case, generates a structured
  nurse-facing evidence summary and gap checklist via the LLM, grounded strictly in the verdicts and
  citations already produced (no new claims).

AUTHENTICATION / AUTHORIZATION
- Self-hosted JWT (short-lived access token + refresh token) + OAuth2 password flow via FastAPI's
  OAuth2PasswordBearer. Passwords hashed with bcrypt/passlib. Three roles only — intake, nurse,
  admin — enforced via a role-checking dependency on every route; no route is reachable by more
  than its intended role(s). Secrets (JWT signing key, DB connection string) go through a
  secrets-manager abstraction layer (e.g. a settings module backed by environment variables /
  a local secrets file, structured so it can be swapped for a real secrets manager later without
  changing call sites) from Phase 1 onward.

CASE LOCKING
- case_locks table: case_id, nurse_id, locked_at, lock_expires_at. An in-process APScheduler job
  runs on an interval (e.g. every 5 minutes) and releases any lock past its 24-hour expiry,
  writing an audit_log entry for the auto-release.

UI (React + TypeScript, light theme, persistent sidebar)
- Sidebar sections, each gated by role: Case Management (Intake + Admin visibility), Nurse Review
  (Nurse + Admin visibility), Administrative Dashboard (Admin only).
- Case Management: create case (auto-filled form from document extraction, editable before
  submit), policy dropdown populated by policy NAME, document upload (multi-file, multi-format),
  view existing cases, NLP search bar.
- Nurse Review: queue view showing heading/metadata only for unlocked cases; "Lock" action; once
  locked, full case view (summary/checklist + document viewer, nurse's choice which to open first);
  Accept/Reject action with mandatory comment; personal History tab of past accepted/rejected cases;
  NLP search bar.
- Administrative Dashboard: policy upload (with manual Policy Name field) + policy list/registry;
  all-cases view across every queue with lock/verification status visible per case; case
  edit/intervention capability with automatic re-verification routing on save; nurse account
  management + per-nurse workload view; NLP search bar; audit log / case-history viewer.
- Case status/agent-progress and lock indicators update via polling (no WebSocket infra in v1).

OBSERVABILITY / AUDIT
- audit_log captures: trace_id, case_id, actor (agent name or user_id), action, model/version (for
  agent actions), input/output summary, confidence score (where applicable), timestamp. Sufficient
  to reconstruct full case history end to end for compliance review.

OFFLINE RAG EVALUATION (dev-time only, never part of the live case pipeline)
- Use Ragas to score Retrieval Agent and Reasoning/Summary Agent quality against a curated,
  synthetic golden dataset (case documents, policy requirement, expected retrieved chunks, expected
  verdict) — never real member/PHI data, consistent with the synthetic-data-only rule for dev/test.
- Metrics: Context Precision and Context Recall (retrieval quality — are the right chunks being
  found for each policy requirement) and Faithfulness (generation quality — does the Reasoning/
  Summary Agent output only make claims the retrieved context actually supports). Answer Relevancy
  is lower priority here since this isn't open-ended QA, but may be added later for the NLP
  case-search feature.
- Judge model and judge embeddings must be wrapped via `LangchainLLMWrapper` /
  `LangchainEmbeddingsWrapper` pointed at local models (Ollama / the local embedding service) —
  never a hosted API — to stay consistent with the data-locality principle. Since this harness runs
  offline and not on the production GPU budget, it may use a heavier local judge model than the
  one running in the live pipeline (e.g. run on the dev machine with more VRAM headroom) if that
  improves judge reliability.
- Known risk to validate early: small local judge models can fail to produce the structured output
  Ragas expects internally, which silently surfaces as NaN scores rather than an error — confirm the
  chosen judge model produces valid scores on a handful of samples before relying on this harness as
  a regression gate.
- This harness is a development/CI quality check, not a runtime component — it must never be wired
  into the live Workflow Agent pipeline or influence a real case's outcome.

DELIVERABLES for this plan phase, each as its own artifact:
- data-model.md — full ERD/table definitions for the schema above.
- api-spec.md — REST endpoints grouped by role/section, including auth endpoints.
- agent-spec.md — per-agent input/output contracts, prompt-shape (structured-output), and the
  Workflow Agent's planner prompt/action-schema, guardrail logic, and audit-log write points.
- rag-pipeline-spec.md — ingestion → chunking → embedding → Qdrant schema → hybrid query → RRF
  fusion → citation-building, plus the case_profile / NLP-search path.
- rag-evaluation-spec.md — the Ragas metric set, golden-dataset schema and generation approach,
  judge model/embeddings configuration, and pass/fail thresholds used as a regression gate in CI.
- ocr-pipeline-spec.md — per-format handling, the image-preprocessing pipeline (deskew/denoise/
  binarize/contrast), and the GPU contention guard behavior.
- ui-spec.md — screen-by-screen spec for the three role-gated sections above.
- security-compliance.md — RBAC matrix, secrets abstraction, audit completeness, data-locality
  enforcement.
- deployment-spec.md — the four-container docker-compose plus native Ollama/backend/frontend setup,
  including a startup health-check sequence.
```

---

## 6. `/speckit.tasks`

```
Break the plan into phased, dependency-ordered tasks:

Phase 1: Foundation — secrets-manager abstraction, Postgres schema + migrations, JWT/OAuth2 auth
with 3-role RBAC, local Docker stack (Postgres, Qdrant, TEI embedding container, MinIO) reachable
and health-checked, native Ollama reachability check.
Phase 2: Document ingestion — multi-format parsers (PDF/DOCX/TXT/MD), OpenCV image-preprocessing
step (grayscale, deskew, denoise, binarize, contrast normalization) ahead of OCR, EasyOCR fallback
with the GPU contention guard, MinIO-backed storage layer (bucket setup, upload/retrieve helper,
object-key bookkeeping in Postgres).
Phase 3: Policy ingestion — admin policy upload UI, Policy Name registry, Intake Agent's
requirement-extraction path, policy_chunk embedding into Qdrant.
Phase 4: Case creation — Intake UI (policy-name dropdown, multi-file upload), Intake Agent's
metadata auto-extraction + confirmation step, case_document_chunk embedding, case_profile
generation.
Phase 5: Hybrid RAG — dense + sparse indexing confirmed in Qdrant, RRF fusion query path, Retrieval
Agent implementation, NLP case-search Query Understanding step (LLM parses free text into
semantic_query + structured filters) feeding the existing hybrid query path (no raw document
scanning), NLP search endpoint and UI search bars.
Phase 6: Reasoning + Summary agents — Present/Absent/Unclear classification with citations and
confidence scoring, evidence-summary/gap-checklist generation.
Phase 7: Workflow Agent orchestration — planner prompt + action-schema + validation layer,
turn-budget guardrail, finalize-requires-Summary guardrail, case_status state machine,
audit_log writes at every step.
Phase 8: Nurse Review UI — pre-lock metadata-only view, lock/unlock action, APScheduler 24-hour
auto-release job, summary/document viewer, Accept/Reject with comment, per-nurse History tab.
Phase 9: Admin dashboard — all-cases view with lock/verification status, case edit/intervention with
automatic re-verification routing, nurse account management, audit log viewer.
Phase 10: Automated tests derived from specs (per-agent, per-endpoint, and an end-to-end case
lifecycle test including the re-verification path), plus the offline Ragas evaluation harness —
synthetic golden dataset, judge LLM/embeddings wired to local models only, Context Precision/
Context Recall/Faithfulness scoring, and regression thresholds wired into CI (kept entirely
separate from the live Workflow Agent pipeline).
Phase 11: Deployment readiness — startup health-check sequence for the four containers plus native
services, and a CI step (or local script, since this is on-prem) that fails the build if any code
path references a public LLM/embedding API host.

Flag, rather than silently complete, any task that would require external network access, a call to
a public API, or more GPU memory than the configured budget allows.
```

---

## 7. `/speckit.analyze`

```
Cross-check spec.md, plan.md, and tasks.md for consistency before implementation. Specifically
re-verify:
(a) no schema anywhere includes an automated-decision boolean — routing stays explicit and
queue-based (case_status, queue, locked_by, decided_by, decided_at);
(b) every RAG/LLM/OCR call path stays local — Ollama on localhost, Qdrant/Postgres/embedding
containers on localhost, zero public-API dependency anywhere;
(c) the Workflow Agent's planner guardrails are all actually implemented and enforced in code, not
just described in prose: the action whitelist rejects any out-of-schema LLM output, the turn-budget
cap forces finalization, `finalize_to_nurse_review` is blocked until Summary Agent has run at least
once, and no code path allows the planner to emit an accept/reject decision, in both agent-spec.md
and the actual task breakdown;
(d) every role-gated UI section maps to exactly the intended role(s) with no accidental shared
access;
(e) the Admin-edit-invalidates-Nurse-decision rule is implemented consistently across data-model.md,
api-spec.md, and the tasks list — not just mentioned in spec.md;
(f) every artifact requested in the plan (data-model.md, api-spec.md, agent-spec.md,
rag-pipeline-spec.md, rag-evaluation-spec.md, ocr-pipeline-spec.md, ui-spec.md,
security-compliance.md, deployment-spec.md) exists and is consistent with tasks.md;
(g) the GPU-contention guard is present wherever OCR or embedding calls could overlap with LLM
generation, and its behavior is configurable rather than hardcoded;
(h) the Ragas evaluation harness uses only synthetic data, wires its judge LLM/embeddings to local
models via LangchainLLMWrapper/LangchainEmbeddingsWrapper with zero hosted-API dependency, and has
no code path that connects it to the live Workflow Agent pipeline;
(i) NLP case search is implemented as Query Understanding (LLM parses free text into a structured
semantic_query + filters) followed by a normal hybrid index query — confirm no code path has an LLM
iterating over case documents or case records directly to answer a search;
(j) every OCR call site (scanned PDFs and directly uploaded images alike) routes through the
image-preprocessing step first — confirm nothing calls EasyOCR on a raw, unprocessed image.
```

Re-run `/speckit.analyze` after each implementation phase completes, not just once before
`/speckit.implement`.

---

## 8. `/speckit.implement`

```
Implement Phase 1 only. Validate it works — secrets abstraction is wired, the three Docker
containers (Postgres, Qdrant, embedding, MinIO) are reachable, native Ollama responds, JWT/OAuth2 auth
issues and validates tokens per role — before moving to the next phase.
```

Repeat per phase (`Implement Phase 2`, `Implement Phase 3`, …), running `/speckit.analyze` between
phases.

---

## Notes

### Standing up the local stack before `/speckit.plan`

Minimal `docker-compose.yml` — four services, matching the plan above:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: pa_assistant
      POSTGRES_USER: pa_app
      POSTGRES_PASSWORD: changeme_use_secrets_manager
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  embeddings:
    image: ghcr.io/huggingface/text-embeddings-inference:latest  # use a cuda- tag for GPU
    command: --model-id BAAI/bge-small-en-v1.5
    ports:
      - "8080:80"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: pa_app
      MINIO_ROOT_PASSWORD: changeme_use_secrets_manager
    ports:
      - "9000:9000"   # S3 API
      - "9001:9001"   # web console
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  qdrant_data:
  minio_data:
```

```bash
docker compose up -d
```

Ollama runs natively (already CUDA-configured per your setup) — just confirm it's serving:

```bash
ollama pull llama3.2:3b
ollama serve   # if not already running as a service
```

Health-check everything before touching `/speckit.plan`:

```bash
curl http://localhost:6333/collections                     # Qdrant
curl http://localhost:5432 2>&1 | head -1                  # Postgres is listening (expect a protocol error, that's fine)
curl http://localhost:9000/minio/health/live               # MinIO
echo '{"inputs":"test sentence"}' > embed-test.json
curl http://localhost:8080/embed -X POST -H "Content-Type: application/json" -d @embed-test.json
echo '{"model":"llama3.2:3b","messages":[{"role":"user","content":"hi"}]}' > chat-test.json
curl http://localhost:11434/v1/chat/completions -X POST -H "Content-Type: application/json" -d @chat-test.json
```

> **Windows/PowerShell note**: use `curl.exe` (bundled with Windows 10+), not bare `curl`
> (aliased to `Invoke-WebRequest`, which doesn't understand `-X`/`-H`/`-d`).

### GPU sharing on a single card

Ollama (llama3.2:3b) should always win contention. A simple pattern for the backend:

```python
import asyncio

gpu_lock = asyncio.Semaphore(1)  # shared by OCR-GPU calls; LLM calls via Ollama bypass this
                                   # since Ollama manages its own GPU memory independently

async def run_ocr_gpu(page_image):
    async with gpu_lock:
        return easyocr_reader.readtext(page_image)
```

Since Ollama and EasyOCR are separate processes each managing their own CUDA context, real
contention shows up as slowdown/OOM under simultaneous load rather than a clean queue — the
semaphore above only serializes *your own* OCR calls against each other; pair it with a short
timeout that falls back EasyOCR to CPU mode (`gpu=False`) if the LLM is known to be mid-generation
(track this with a simple shared flag the Workflow Agent sets/clears around each Ollama call).

### Why the embedding container, not in-process

bge-small-en-v1.5 is small enough to run in-process on CPU with near-zero latency cost, but per
your call to keep it in Docker (and to leverage the GPU where available), the TEI container above
uses a CUDA image. Since embedding calls are short and mostly batched during document ingestion
(not on the hot path of every chat turn), they're the least disruptive thing to share GPU time with
llama3.2:3b — but if you see contention in practice, switching the `embeddings` service to the
CPU-tagged TEI image is a one-line change with no other architecture impact.

### CI / build-time confidentiality check

Worth adding even as a local pre-commit or Phase-1 script rather than full CI, since this is
on-prem: a simple grep/AST check that fails the build if any source file references a public LLM or
embedding API host (`api.openai.com`, `api.anthropic.com`, cloud embedding endpoints, etc.).

### RAG evaluation with Ragas (offline, dev-time only)

Ragas doesn't require a hosted API — wrap your local judge model and embeddings via LangChain and
it runs entirely on-prem:

```python
from langchain_community.chat_models import ChatOllama
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.metrics import faithfulness, context_precision, context_recall
from ragas import evaluate

judge_llm = LangchainLLMWrapper(ChatOllama(model="llama3.2:3b", temperature=0))
judge_embeddings = LangchainEmbeddingsWrapper(your_local_bge_small_embeddings_wrapper)

results = evaluate(
    dataset=golden_dataset,   # synthetic: question/context/answer/ground_truth per policy requirement
    metrics=[faithfulness, context_precision, context_recall],
    llm=judge_llm,
    embeddings=judge_embeddings,
)
```

Two practical notes:
- There are documented cases of small local judge models causing `faithfulness` to silently return
  `NaN` instead of a score, because the judge fails to produce the structured output Ragas parses
  internally. Run a handful of samples first and confirm real numeric scores come back before
  wiring this into a CI gate.
- This harness runs offline against a synthetic golden dataset — it's a development/regression tool
  for scoring the Retrieval and Reasoning/Summary agents, not a component of the live per-case
  pipeline. It can afford to use a heavier local model as judge (run on the dev machine) than
  whatever ships to the resource-constrained deployment target.
