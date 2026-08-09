# Spec-Kit Prompt Playbook
## Unified Scientific Evidence Retrieval and Provenance Platform for Oncology Research

This playbook gives copy-paste-ready `/speckit.*` prompts for the full build, phased to match the roadmap in the architecture doc (§10). Each phase ends with `/speckit.analyze` — run it after every phase, not just at milestones, so drift gets caught early rather than compounding.

**Tooling note:** when running Spec-Kit's PowerShell prerequisite scripts, always include `-Json -RequireTasks -IncludeTasks` — without these flags the output is silently incomplete.

---

## Phase 0 — Constitution

Run once, before any `/speckit.specify` call. This sets the non-negotiable rules every later phase must respect.

```
/speckit.constitution

This project is the Unified Scientific Evidence Retrieval and Provenance
Platform for Oncology Research. Establish the following as binding
constitution articles:

1. Provenance-first: no evidence record may be embedded for search or
   surfaced in any output until it has passed the Provenance Agent's
   completeness check (source, publication date, DOI/PMID, evidence
   tier, therapeutic context). Incomplete records are flagged, never
   silently accepted.

2. Four-state evidence resolution: every query must resolve to exactly
   one of NOT_YET_INVESTIGATED, CONFIRMED_ABSENT, UNKNOWN, or
   EVIDENCE_AVAILABLE before retrieval scoring runs. A bare "no results"
   response is never acceptable as a final answer.

3. Deterministic weighting: evidence weights are computed by a
   versioned, published rubric (rubric_vN). LLM agents may only extract
   rubric input variables from evidence records; they may never invent
   or silently adjust rubric coefficients. Every weighted conclusion
   must record which rubric version produced it.

4. Mandatory weight-dimension disambiguation: any user request to
   assign a weight/percentage to evidence must specify which dimension
   it refers to (confidence / clinical importance / ranking weight /
   aggregation weight). The system must never silently guess the
   dimension.

5. Component-level data survives summarization: raw fields (hazard
   ratios, confidence intervals, treatment arms, biomarker status,
   patient populations) must remain independently retrievable from
   their source record, not only accessible via a generated summary.

6. No un-sourced claims: every assertion in a Summary Agent output must
   resolve to a traceable evidence_record id. If it can't be traced,
   it cannot be stated.

7. Human review authority: only human reviewers may accept, reject, or
   override evidence validity or weighting. No agent — including the
   Workflow/Planner Agent — has accept/reject authority.

8. Agent guardrails: the Workflow/Planner Agent operates from a
   whitelisted action set with a turn budget cap. It may sequence
   agents but may not substitute its own judgment for the deterministic
   checks in articles 1-4.

9. Reproducibility: any change to the weighting rubric, evidence-tier
   definitions, or state-resolution logic must be versioned so that
   historical conclusions remain reproducible under the rubric/logic
   version active when they were computed.

10. Data-sensitivity gating: before any source is ingested, it must be
    classified as public/non-PHI or internal/proprietary. Classification
    determines LLM routing (hosted model vs. local/on-prem model) and
    must be recorded against the ingested record.

11. Architectural Decision Records (ADRs): every non-trivial
    architectural decision — choice of database/component, schema
    design, rubric formula design, agent boundary, guardrail
    mechanism, or any decision that reverses or narrows an earlier
    one — must be captured as an ADR before implementation begins,
    not written up retroactively. An ADR is not optional
    documentation; `/speckit.plan` for any phase must name the ADRs
    it will produce, and `/speckit.analyze` must fail the phase if an
    architecturally significant decision was implemented without a
    corresponding ADR.
```

---

## ADR Framework (established once, used every phase)

Run this once, immediately after the constitution, to set up the ADR log and template. Every later phase's `/speckit.plan` will reference this template by name rather than reinventing the format.

```
/speckit.specify

Establish an Architectural Decision Record (ADR) framework for this
project.

Create adr/0000-adr-template.md with the following fields for every
ADR:
- ID and title (e.g., "0007-neo4j-for-lineage-graph")
- Status: Proposed / Accepted / Superseded / Deprecated
- Date
- Context: what problem or fork in the road prompted this decision
- Decision: the choice actually made, stated plainly
- Alternatives considered: at least two, with why each was rejected
- Consequences: what this makes easier, what it makes harder, and
  what it forecloses
- Supersedes / Superseded-by: links to related ADRs if this decision
  revises an earlier one

Create adr/README.md as a running index of all ADRs, ordered by ID,
each with a one-line summary and current status.

Immediately backfill ADRs for the decisions already made in the
architecture doc, so the log starts accurate rather than starting
empty:
- 0001-provenance-first-ingestion.md (why no record is searchable
  before passing provenance validation)
- 0002-four-state-evidence-resolution.md (why "no data found" is
  split into four explicit states rather than one)
- 0003-postgres-for-structured-metadata.md
- 0004-neo4j-for-lineage-graph.md (vs. a relational join-table
  alternative, and why that alternative was rejected at this depth
  of lineage)
- 0005-qdrant-hybrid-search.md (dense + sparse, vs. dense-only)
- 0006-domain-tuned-biomedical-embeddings.md (vs. generic embeddings
  like bge-small)
- 0007-deterministic-weighting-rubric.md (vs. letting an LLM judge
  weight per-query)
- 0008-mandatory-weight-dimension-disambiguation.md
- 0009-llm-tiering-by-data-sensitivity.md (hosted vs. local routing)
- 0010-agent-separation-reasoning-vs-summary.md (why these are two
  agents, not one)

Success criteria: every constitution article that reflects an
architectural choice (not just a process rule) has a traceable ADR;
the index in adr/README.md is complete and status-accurate.
```

```
/speckit.tasks
/speckit.analyze
```

---

## Phase 1 — Foundational Data Layer + Ingestion

### 1a. Specify

```
/speckit.specify

Build the foundational data layer and ingestion pipeline for the
oncology evidence platform.

Ingestion must be API-driven, not manual document upload. Sources are
fetched programmatically:

- PubMed via NCBI E-utilities (base URL
  https://eutils.ncbi.nlm.nih.gov/entrez/eutils/):
  - esearch.fcgi resolves a text query (e.g. mutation + drug terms)
    to a list of PMIDs. Note: a single esearch call can return at most
    10,000 UIDs (retmax cap), so queries expected to exceed this must
    be paginated via retstart/retmax or handled through the NCBI
    History server (WebEnv/query_key) rather than one large call.
  - efetch.fcgi retrieves the full abstract/XML record for a batch of
    PMIDs.
  - Requires an NCBI API key (raises the rate limit from 3 to 10
    requests/sec) and must send tool + email parameters on every call
    per NCBI's usage policy.
  - efetch returns XML by default; the connector must parse this
    directly rather than assuming plain text.

- ClinicalTrials.gov via its REST API v2, which returns structured
  JSON per trial (phase, arms, endpoints, status, enrollment) —
  no HTML scraping and no PDF parsing needed for the core trial record
  itself, though linked full-text/result PDFs may still require the
  table-aware parser below.

- Fetches can run on a schedule (e.g. nightly sync for defined MeSH
  terms/drug classes) or on-demand, triggered when the State
  Classifier resolves a topic to NOT_YET_INVESTIGATED and a researcher
  requests a live check rather than waiting for the next scheduled run.

Scope:
- PostgreSQL schema for: evidence_record, evidence_version,
  weighting_result, query_state (see data model spec below).
- Neo4j graph schema for lineage: EvidenceRecord, Publication, Trial,
  Researcher nodes; CITES, SUPERSEDES, VALIDATED_BY, DERIVED_FROM
  relationships.
- Qdrant collections per evidence type (literature / trial /
  regulatory), hybrid dense+sparse indexing, payload includes
  record_id foreign key back to Postgres.
- MinIO bucket structure for immutable raw source documents (store the
  raw API response — XML/JSON — alongside any linked full-text PDF,
  so the original fetched payload is always reproducible, not just the
  parsed-out fields).
- Ingestion Agent: PubMed E-utilities connector as the first source
  (ClinicalTrials.gov API v2 and internal repos are out of scope for
  this phase — see Phase 4).
- Provenance Agent: metadata extraction and completeness validation
  per constitution article 1. Must classify data sensitivity
  (constitution article 10) at ingestion time.
- Document-parsing must be table-aware (not plain-text extraction) so
  hazard ratios, confidence intervals, and treatment-arm data in
  linked source PDFs are captured structurally, not flattened into
  prose.
- Relevance tagging at ingestion time is out of scope here — a fetched
  record is stored and embedded regardless of any specific query;
  matching a record to a specific researcher question is the
  Retrieval Agent's job in Phase 2, not something decided at ingest.

Explicitly out of scope for this phase: retrieval, state
classification, reasoning/weighting, summarization, and the frontend.
Those are later phases.

Success criteria: given only a search term (e.g. "KRAS G12C"), the
pipeline runs esearch → efetch against the live PubMed API with no
manually supplied document, and the resulting records land correctly
in Postgres (metadata), Neo4j (as nodes with no edges yet if no
citations known), Qdrant (embedded), and MinIO (raw API payload),
with a recorded data-sensitivity classification and a validation_status
that reflects whether the Provenance Agent's completeness check passed.
```

### 1b. Plan

```
/speckit.plan

Use domain-tuned biomedical embeddings (PubMedBERT- or BioBERT-based),
not a generic embedding model — oncology terminology (mutation
nomenclature, drug names, trial acronyms) needs it.

Use Docling or unstructured.io for parsing linked full-text PDFs;
require table extraction to be verified against at least one source
PDF containing a hazard ratio / confidence interval table before this
phase is marked complete.

Implement retry/backoff for E-utilities calls that respects NCBI's
published rate limits (3 req/sec without an API key, 10 req/sec with
one) rather than a generic exponential backoff — a naive retry loop
that ignores the documented limit risks the whole application getting
rate-limited or blocked.

Name and include these supplementary artifacts explicitly in this
plan, since they will not be picked up automatically:
- data-model.md (full Postgres/Neo4j/Qdrant schema, field-by-field)
- ingestion-connector-spec.md (PubMed E-utilities integration
  details: esearch/efetch call sequence, pagination via History
  server for >10,000-result queries, rate-limit handling, retry/backoff
  policy, XML parsing approach)
- provenance-validation-rules.md (exact completeness rules the
  Provenance Agent enforces, and what "incomplete" triggers)
- data-sensitivity-classification.md (the public/non-PHI vs.
  internal/proprietary decision tree and where it's recorded)

Any decision made during this phase that isn't already covered by an
ADR from the ADR Framework step — for example, choice of PubMed API
client library, retry/backoff strategy, or MinIO bucket-partitioning
scheme, if these turn out to be non-obvious — must get its own ADR
(adr/0011-... onward) using adr/0000-adr-template.md, added to
adr/README.md.
```

### 1c. Tasks + Analyze

```
/speckit.tasks
/speckit.analyze
```
Run `/speckit.analyze` again after implementation, before moving to Phase 2 — don't wait for a later milestone.

---


## Phase 2 — State Classification + Retrieval

### 2a. Specify

```
/speckit.specify

Build the State Classifier Agent and Retrieval Agent on top of the
Phase 1 data layer.

State Classifier Agent:
- Implements the four-state resolution from constitution article 2
  as a deterministic decision tree first (has this topic ever been
  queried? did search find matching records? did records pass
  validation?), with LLM disambiguation reserved only for genuine
  edge cases where the deterministic tree cannot resolve a state.
- Writes the resolved state to query_state (topic_hash, state,
  last_investigated_date) BEFORE the Retrieval Agent runs, so
  "no results" from retrieval is never presented as the final answer
  on its own.

Retrieval Agent:
- Hybrid search: Qdrant vector search (dense + sparse) combined with
  Neo4j graph traversal for lineage-aware queries (e.g., "show me the
  current version of this evidence, not a superseded one").
- Relevance matching against already-ingested records works as
  follows: the researcher's question is embedded with the same
  biomedical embedding model used at ingestion, compared against
  Qdrant's dense vectors for semantic matches (e.g. "tumor shrinkage"
  matching a record that says "response rate"), and combined with a
  sparse/keyword pass for exact-term matches (drug names, mutation
  codes) that semantic similarity alone can miss. Results are ranked
  by a combined score, not either signal alone.
- Live-fetch fallback: if the State Classifier resolves a topic to
  NOT_YET_INVESTIGATED, the Retrieval Agent may trigger the Phase 1
  Ingestion Agent to run an on-demand PubMed esearch/efetch pull for
  the query terms before returning a final answer, rather than only
  ever searching what happens to already be in Qdrant. This keeps the
  platform current without requiring a researcher to manually supply
  a document.
- Read-only with respect to evidence_record content: must not write to
  or re-tier any evidence_record itself (triggering a fetch is an
  Ingestion Agent action, not a Retrieval Agent edit).
- Must return results annotated with their evidence_tier and
  validation_status inline, not as a separate lookup.

Success criteria: querying a topic never yet ingested correctly
returns NOT_YET_INVESTIGATED; querying a topic with ingested but
failed-validation evidence returns UNKNOWN with the failing record
visible; querying a topic with no matching evidence after a real
search returns CONFIRMED_ABSENT with a record of when it was checked;
querying a topic not yet in the system but available on PubMed, with
live-fetch enabled, results in a fresh esearch/efetch pull and a
correctly ranked relevance match against the newly ingested record.
```

### 2b. Plan

```
/speckit.plan

Name and include explicitly:
- state-resolution-decision-tree.md (exact logic, including which
  cases escalate to LLM disambiguation and why)
- retrieval-scoring-spec.md (how dense/sparse/graph signals are
  combined into a single ranked result set)
- frontend-state-display-spec.md (how the four states are
  distinguished in the UI — this cannot be left as a backend-only
  concern, since the whole point is researcher-visible disambiguation)

Any new architecturally significant decision this phase makes — e.g.
how dense/sparse/graph signals are weighted against each other in
result ranking, or where the line sits between "deterministic tree"
and "LLM disambiguation" for edge cases — gets its own ADR
(adr/0012-... onward), added to adr/README.md.
```

### 2c. Tasks + Analyze

```
/speckit.tasks
/speckit.analyze
```

---

## Phase 3 — Reasoning/Weighting + Summary/Citation

### 3a. Specify

```
/speckit.specify

Build the Reasoning/Weighting Agent and Summary/Citation Agent.

Reasoning/Weighting Agent:
- Implements rubric_v1.0 exactly as defined in
  weighting-rubric-v1.md (see plan below), using the starting
  coefficients: Phase III trial 50%, Meta-analysis 25%, Phase II
  trial 20%, Case report 3%, Expert opinion 2% — combined with
  statistical_significance, sample_size, recency, and regulatory_status
  per the documented formula.
- Enforces constitution article 3: this agent extracts rubric inputs
  from evidence records; it never invents or adjusts coefficients.
- Enforces constitution article 4: any incoming request to assign a
  weight/percentage must include an explicit dimension (confidence /
  clinical importance / ranking weight / aggregation weight). If the
  dimension is missing, the agent must return a clarification request,
  not a best-guess weight.
- Every weighting_result record stores which rubric_version produced it.

Summary/Citation Agent:
- Produces publication-ready output where every claim resolves to a
  traceable evidence_record id (constitution article 6).
- Preserves access to component-level raw data (hazard ratios,
  confidence intervals, treatment arms, etc.) alongside the summary —
  the summary must link to these fields, not replace them.
- Output format must be suitable for regulatory documentation
  (citation-ready: journal, authors, DOI/PMID inline or as footnotes).

Success criteria: given a set of five evidence records across
different tiers, the Reasoning Agent produces weights matching
rubric_v1.0's formula exactly and reproducibly; a request for "10%
weight" with no dimension specified is rejected with a clarification
prompt rather than silently resolved.
```

### 3b. Plan

```
/speckit.plan

Name and include explicitly:
- weighting-rubric-v1.md (the full formula: evidence_tier,
  statistical_significance, sample_size, recency, regulatory_status,
  study_design — with exact coefficient values and worked examples)
- weight-dimension-disambiguation-ux.md (exact UI copy/flow for
  forcing dimension specification — e.g., dropdown next to a
  percentage field, not a free-text prompt that an LLM has to parse)
- citation-output-format.md (regulatory-documentation-ready citation
  format, with examples for at least PubMed and ClinicalTrials.gov
  sourced records)

Write adr/0013-rubric-v1-coefficients.md capturing the final
sign-off values and who approved them (this is the ADR that resolves
the open item flagged in the architecture doc §9 — it should record
the actual approving stakeholder, not "TBD"). Any further coefficient
change later must supersede this ADR explicitly, never edit it in
place, so historical conclusions stay reproducible under the version
that computed them.
```

### 3c. Tasks + Analyze

```
/speckit.tasks
/speckit.analyze
```

---

## Phase 4 — Human Review Loop + Remaining Source Connectors

### 4a. Specify

```
/speckit.specify

Build the human review/annotation loop and add ClinicalTrials.gov and
internal-repository connectors to the Ingestion Agent.

Human review:
- Reviewers can accept, reject, or annotate any Reasoning Agent output
  or Summary Agent citation (constitution article 7 — only humans
  hold this authority).
- Every accepted/annotated review writes back into the knowledge base
  as a new evidence_record or an annotation linked to an existing one,
  so the same question is never fully re-researched by a different
  team later.
- Reviewers can see, per constitution article 9, which rubric version
  and which state-resolution logic version produced the output they're
  reviewing.

New connectors:
- ClinicalTrials.gov API connector, same completeness/validation
  pipeline as PubMed from Phase 1.
- Internal-repository connector: requires the data-sensitivity gate
  (constitution article 10) to correctly route internal/proprietary
  content to local-LLM processing rather than any hosted-model agent.

Success criteria: a researcher's annotation on a Confirmed-Absent
result is preserved and surfaces automatically the next time any
researcher queries the same topic, without re-running the full
pipeline.
```

### 4b. Plan

```
/speckit.plan

Name and include explicitly:
- human-review-workflow.md (review queue UX, annotation data model,
  write-back mechanics)
- clinicaltrials-connector-spec.md
- internal-repo-connector-spec.md (must reference
  data-sensitivity-classification.md from Phase 1 and specify exactly
  how routing to local vs. hosted LLM is decided and enforced)

Write adr/0014-mvp-source-scope.md capturing which sources beyond
PubMed were actually included and which were deliberately deferred
(this resolves the second open item from architecture doc §9). Write
adr/0015-human-review-writeback-model.md documenting how reviewer
annotations become new evidence_record entries vs. remaining
annotations-only — this is a decision with real downstream effects on
retrieval and deserves its own record rather than being buried in the
review-workflow spec.
```

### 4c. Tasks + Analyze

```
/speckit.tasks
/speckit.analyze
```

---

## Phase 5 — Hardening: Audit, Access Control, Export Formats

### 5a. Specify

```
/speckit.specify

Harden the platform for production and regulatory use.

- Full audit logging: every read/write to evidence_record,
  weighting_result, and query_state is logged with actor, timestamp,
  and rubric/logic version in effect at the time.
- Access control: role-based access distinguishing researchers,
  reviewers, and administrators; internal/proprietary-classified
  records are additionally restricted per organizational policy.
- Regulatory-documentation export: a formal export path producing
  citation-ready, provenance-complete documents suitable for
  submission or publication, pulling directly from evidence_record
  and weighting_result — never from an unlinked summary.
- Retention/versioning policy: superseded evidence_version records
  remain queryable per the retention window decided in the open
  questions (architecture doc §9); this phase implements whatever
  window is finalized.

Success criteria: an end-to-end audit trail exists for any given
weighted conclusion, from raw source document through to the exact
rubric version and reviewer sign-off that produced it.
```

### 5b. Plan

```
/speckit.plan

Name and include explicitly:
- audit-logging-spec.md
- access-control-matrix.md (roles x record-sensitivity x permitted
  actions)
- regulatory-export-format.md
- retention-policy.md (finalized retention window and rationale)

Write adr/0016-retention-window.md capturing the finalized retention
policy and rationale, and adr/0017-access-control-model.md capturing
why role-based access was structured the way it was (e.g., why
internal/proprietary records get an additional restriction layer
rather than a separate system entirely).
```

### 5c. Tasks + Analyze

```
/speckit.tasks
/speckit.analyze
```

---

## Cross-Cutting Reminders for Every Phase

- Run `/speckit.analyze` **after every phase**, not just at named milestones — catching drift early is cheaper than reconciling it later.
- Any supplementary artifact you want `/speckit.plan` to actually produce must be **named explicitly** in the prompt; it will not infer unnamed artifacts on its own.
- Before starting Phase 1, confirm the two open items from the architecture doc that block real coefficients/scope: (1) final sign-off on rubric_v1.0's coefficients from a named scientific stakeholder, and (2) confirmation of which sources beyond PubMed count as MVP scope. Both are referenced as placeholders above and should be locked before `/speckit.plan` runs for the phases that depend on them (Phase 3 for the rubric, Phase 4 for connector scope).
- Every architecturally significant decision gets an ADR **before** implementation, using `adr/0000-adr-template.md`, added to `adr/README.md` immediately — not batched up and written retroactively at the end of a phase. `/speckit.analyze` should treat a missing ADR for a significant decision as a phase-blocking finding, the same way it would treat a missing required field in the provenance schema.
- If a later decision reverses or narrows an earlier one (e.g. the rubric coefficients change after Phase 3, or the retention window from Phase 5 gets revisited), write a new ADR that supersedes the old one explicitly. Never edit an existing ADR's Decision field in place — that destroys the reproducibility the constitution requires.
