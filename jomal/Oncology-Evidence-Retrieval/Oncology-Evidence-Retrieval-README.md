# Oncology Evidence Retrieval

A Spec-Driven architecture for a scientific evidence retrieval and provenance platform focused on oncology research.

The platform is designed to help researchers retrieve, validate, rank, trace, and summarise evidence while preserving source provenance and reproducibility.

> **Current status:** this directory currently contains the Spec-Kit architecture/playbook rather than a complete production implementation. The README therefore distinguishes the planned architecture from implemented source code.

---

## Problem

Scientific evidence retrieval is not simply a search problem.

A useful oncology evidence platform needs to answer questions such as:

- Has this topic ever been investigated?
- Did the search actually find evidence?
- Is the evidence complete and validated?
- Which version of the evidence is current?
- What evidence tier does the study belong to?
- How was its weight calculated?
- Can every generated claim be traced back to a source?
- Which rubric and decision logic produced the conclusion?
- Has a human reviewer accepted or annotated the result?

The architecture therefore treats **provenance, state resolution, deterministic reasoning, and reproducibility as first-class system requirements**.

---

# Architecture

```text
                         Researcher
                             │
                             ▼
                    ┌─────────────────┐
                    │ State Classifier │
                    │      Agent      │
                    └────────┬────────┘
                             │
               ┌─────────────┼─────────────┐
               ▼             ▼             ▼
      NOT_YET_INVESTIGATED  UNKNOWN   Investigated
               │                         │
               ▼                         ▼
        Ingestion Agent             Retrieval Agent
               │                         │
        ┌──────┴────────┐        ┌───────┼────────┐
        ▼               ▼        ▼       ▼        ▼
     PubMed        Other APIs   Dense   Sparse   Graph
        │                        │       │        │
        └──────────────┐         └───────┼────────┘
                       ▼                 ▼
                Provenance Layer   Hybrid Ranking
                       │                 │
                       └────────┬────────┘
                                ▼
                      Reasoning / Weighting
                                │
                                ▼
                       Summary / Citation
                                │
                                ▼
                         Human Review
```

---

# Core Principles

The Spec-Kit constitution establishes eleven binding principles.

## 1. Provenance first

An evidence record must pass completeness validation before it is embedded for search or surfaced as valid evidence.

Required provenance includes information such as:

- source;
- publication date;
- DOI/PMID;
- evidence tier;
- therapeutic context.

Incomplete evidence is flagged rather than silently treated as valid.

## 2. Four-state evidence resolution

Every query resolves to exactly one of:

```text
NOT_YET_INVESTIGATED
CONFIRMED_ABSENT
UNKNOWN
EVIDENCE_AVAILABLE
```

A simple "no results" response is not considered sufficient.

## 3. Deterministic weighting

Evidence weights come from a versioned rubric.

LLMs can extract the variables needed by the rubric, but they cannot silently invent or modify the coefficients.

## 4. Weight-dimension disambiguation

A request such as:

```text
"Give this evidence 10% weight"
```

is incomplete unless the dimension is specified.

Possible dimensions include:

- confidence;
- clinical importance;
- ranking weight;
- aggregation weight.

The system should request clarification instead of guessing.

## 5. Preserve component-level data

Important scientific fields must remain independently retrievable, including:

- hazard ratios;
- confidence intervals;
- treatment arms;
- biomarker status;
- patient populations.

Generated summaries do not replace the underlying structured evidence.

## 6. Traceable claims

Every generated assertion must resolve to a traceable evidence record.

If a claim cannot be grounded in the evidence store, it should not appear in the final summary.

## 7. Human review authority

Only human reviewers can:

- accept evidence;
- reject evidence;
- override validity;
- annotate reasoning;
- override weighting conclusions.

Agents assist; they do not own final authority.

## 8. Agent guardrails

The Workflow/Planner Agent operates using:

- a whitelist of actions;
- a bounded turn budget;
- deterministic checks;
- explicit phase boundaries.

## 9. Reproducibility

Changes to:

- weighting rubrics;
- evidence-tier definitions;
- state-resolution logic;

must be versioned.

Historical conclusions must remain reproducible under the versions active when they were produced.

## 10. Data-sensitivity gating

Every source is classified before processing as:

- public/non-PHI;
- internal/proprietary.

The classification determines whether hosted or local/on-premise model processing is permitted.

## 11. ADR-driven architecture

Significant architectural decisions must be recorded as Architecture Decision Records before implementation.

---

# Planned Agents

## Ingestion Agent

Responsible for programmatically obtaining evidence from supported sources.

The first planned source is PubMed through NCBI E-utilities.

The architecture explicitly avoids requiring researchers to manually upload every source.

## Provenance Agent

Validates evidence metadata and completeness before indexing.

It also performs data-sensitivity classification.

## State Classifier Agent

Determines which of the four query states applies.

The design favours a deterministic decision tree first, using LLM disambiguation only for genuine edge cases.

## Retrieval Agent

Combines:

- dense semantic search;
- sparse keyword retrieval;
- graph traversal.

The agent is read-only with respect to core evidence content.

## Reasoning / Weighting Agent

Extracts rubric inputs and calculates evidence weights according to a versioned deterministic formula.

It must not dynamically invent coefficients.

## Summary / Citation Agent

Generates publication/regulatory-oriented summaries while maintaining links to source evidence records.

## Human Review Loop

Researchers/reviewers can:

- accept;
- reject;
- annotate;
- challenge;
- preserve findings for later queries.

---

# Data Architecture

```text
                   ┌──────────────────┐
                   │    PostgreSQL    │
                   │ structured data  │
                   │ versions/weights │
                   │ query state      │
                   └────────┬─────────┘
                            │
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
      ┌────────┐        ┌────────┐       ┌────────┐
      │ Neo4j  │        │ Qdrant │       │ MinIO  │
      │lineage │        │ hybrid │       │ raw    │
      │ graph  │        │ search │       │source  │
      └────────┘        └────────┘       └────────┘
```

### PostgreSQL

Planned structured entities include:

- `evidence_record`
- `evidence_version`
- `weighting_result`
- `query_state`

### Neo4j

Planned lineage graph:

```text
EvidenceRecord
Publication
Trial
Researcher
```

with relationships such as:

```text
CITES
SUPERSEDES
VALIDATED_BY
DERIVED_FROM
```

### Qdrant

Planned hybrid retrieval store with dense and sparse representations.

Evidence types are expected to be separated into collections such as:

- literature;
- trial;
- regulatory.

Payloads retain a foreign-key relationship to PostgreSQL records.

### MinIO

Stores immutable source material and raw API responses.

The design intentionally preserves the original fetched payload rather than only storing parsed fields.

---

# PubMed Ingestion

The first planned connector uses the NCBI E-utilities API.

```text
Research Query
      │
      ▼
   esearch
      │
      ▼
    PMIDs
      │
      ▼
   efetch
      │
      ▼
   XML records
      │
      ▼
Provenance Validation
      │
      ├──────────────► Invalid / Incomplete
      │
      ▼
  Valid Evidence
      │
      ├──► PostgreSQL
      ├──► Neo4j
      ├──► Qdrant
      └──► MinIO
```

The planned connector accounts for:

- `esearch.fcgi`;
- `efetch.fcgi`;
- XML parsing;
- API keys;
- NCBI request metadata;
- rate limits;
- retry/backoff;
- pagination;
- History Server usage for large result sets.

The playbook specifically calls out that a single search window cannot be assumed to handle arbitrarily large result sets.

---

# Retrieval

The platform uses hybrid retrieval because oncology research contains both semantic and exact-match information.

For example:

### Semantic matching

```text
"tumour shrinkage"
        ↓
"response rate"
```

These concepts may be related even when the exact words differ.

### Exact matching

```text
KRAS G12C
Osimertinib
NCT12345678
```

Exact identifiers can be poorly represented by semantic similarity alone.

The intended retrieval path is therefore:

```text
Query
  │
  ├──► Dense Search
  │
  ├──► Sparse Search
  │
  └──► Graph Traversal
          │
          ▼
    Combined Ranking
          │
          ▼
   Evidence + tier +
   validation status
```

---

# Four-State Resolution

The distinction between "not investigated" and "no evidence found" is central to the design.

```text
                        Query
                          │
                          ▼
                  State Classifier
                          │
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                  ▼
Not Investigated       Unknown         Investigated
        │                                    │
        ▼                                    ▼
 Optional Live Fetch                    Retrieval
        │                                    │
        └────────────────┬───────────────────┘
                         ▼
                 Evidence State
```

### `NOT_YET_INVESTIGATED`

The system has not performed a meaningful investigation of the topic.

### `UNKNOWN`

Evidence may exist, but available records are incomplete, invalid, or otherwise insufficient to establish a reliable conclusion.

### `CONFIRMED_ABSENT`

The topic has been investigated and no matching evidence was found under the defined search/validation process.

### `EVIDENCE_AVAILABLE`

Relevant, validated evidence is available.

---

# Evidence Weighting

The playbook specifies the following starting evidence-tier coefficients:

| Evidence tier | Starting coefficient |
|---|---:|
| Phase III trial | 50% |
| Meta-analysis | 25% |
| Phase II trial | 20% |
| Case report | 3% |
| Expert opinion | 2% |

The design further calls for factors such as:

- statistical significance;
- sample size;
- recency;
- regulatory status;
- study design.

These coefficients are **architecture/playbook-stage starting values**, not a claim of clinical validation or a universal scientific weighting standard.

Every computed weighting result is expected to retain the rubric version that produced it.

---

# Provenance and Reproducibility

A major design objective is to support a chain such as:

```text
Raw Source
    │
    ▼
Parsed Evidence
    │
    ▼
Provenance Validation
    │
    ▼
Evidence Record
    │
    ▼
Retrieval
    │
    ▼
Weighting Rubric vN
    │
    ▼
Reasoning
    │
    ▼
Summary
    │
    ▼
Human Review
```

A later change to the rubric should not silently change historical conclusions.

Instead:

```text
rubric_v1
    │
    └── historical result

rubric_v2
    │
    └── new result
```

This preserves reproducibility.

---

# Spec-Kit Development Workflow

The project is explicitly structured around Spec-Kit.

```text
/speckit.constitution
        │
        ▼
     /specify
        │
        ▼
      /plan
        │
        ▼
     /tasks
        │
        ▼
  Implementation
        │
        ▼
    /analyze
```

The playbook requires `/speckit.analyze` after every phase.

It also requires architecturally significant decisions to be captured as ADRs before implementation.

---

# Planned Phases

## Phase 0 — Constitution and ADR Framework

Establish:

- project constitution;
- ADR template;
- initial architecture decisions.

## Phase 1 — Data Layer and Ingestion

Build:

- PostgreSQL schema;
- Neo4j lineage model;
- Qdrant indexing;
- MinIO raw-source storage;
- PubMed connector;
- Provenance Agent.

## Phase 2 — State Classification and Retrieval

Build:

- deterministic state classifier;
- hybrid retrieval;
- graph-aware retrieval;
- live-fetch fallback for `NOT_YET_INVESTIGATED`.

## Phase 3 — Reasoning, Weighting and Summary

Build:

- deterministic weighting rubric;
- dimension disambiguation;
- traceable summary/citation generation.

## Phase 4 — Human Review and Additional Connectors

Add:

- human annotation;
- ClinicalTrials.gov;
- internal repository integration;
- sensitivity-aware model routing.

## Phase 5 — Production Hardening

Add:

- complete audit logging;
- access control;
- regulatory export;
- retention/versioning policies.

---

# ADR Framework

The playbook calls for ADRs covering decisions such as:

```text
0001  Provenance-first ingestion
0002  Four-state evidence resolution
0003  PostgreSQL for structured metadata
0004  Neo4j for lineage
0005  Qdrant hybrid search
0006  Domain-tuned biomedical embeddings
0007  Deterministic weighting rubric
0008  Weight-dimension disambiguation
0009  LLM tiering by data sensitivity
0010  Agent separation: reasoning vs summary
```

Later phases extend the ADR sequence for new architectural decisions.

---

# Repository Contents

```text
Oncology-Evidence-Retrieval/
├── oncology-evidence-platform-speckit-playbook.md
├── .agents/
│   └── skills/
└── .specify/
    ├── memory/
    ├── templates/
    ├── workflows/
    └── scripts/
```

The `oncology-evidence-platform-speckit-playbook.md` file is the main project-specific implementation guide currently present in this directory.

---

# Why This Project Is Interesting

This architecture demonstrates an approach to scientific GenAI where the goal is not simply to generate a plausible answer.

The system is designed around:

- **evidence provenance**;
- **retrieval correctness**;
- **deterministic scientific weighting**;
- **citation traceability**;
- **data sensitivity**;
- **versioned reasoning**;
- **human review**;
- **reproducibility**.

This is particularly important for domains where an unsupported generated claim can be more harmful than an explicit "unknown" result.

---

## Status

**Architecture / Spec-Kit playbook stage**

The repository currently documents the intended phased implementation. The README does not claim that the full ingestion, retrieval, graph, weighting, and review platform has already been implemented.

---

## Author

**Jomal Sanish**

Computer Science Engineering
