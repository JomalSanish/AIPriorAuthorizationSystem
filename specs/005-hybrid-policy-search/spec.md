# Feature Specification: Persistent Hybrid Policy Document Search

**Feature Branch**: `005-hybrid-policy-search`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "Persistent hybrid policy document search using FAISS and BM25"

## Constitution Alignment

- The solution MUST use Python and a Streamlit UI whenever a user-facing workflow is required.
- The solution MUST use LangChain-based multi-agent routing when a multi-agent architecture is part of the feature.
- All Python files MUST include explicit type hints.
- Prototype work MUST use the available local evidence source and in-memory state unless persistence is explicitly requested.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Policy Document Ingestion & Persistent Indexing (Priority: P1)

As a Payer Operations Administrator, I want the system to ingest full clinical policy guidelines (PDFs) and save their searchable index persistently, so that policy criteria do not need to be hardcoded or rebuilt from scratch every time the server starts.

**Why this priority**: Crucial for scalability. Storing policy logic in persistent indexes allows the system to support any number of policies without modifying Python code.

**Independent Test**: Can be verified by running the ingestion command/tool on the Adalimumab policy PDF, restarting the backend session, and verifying that the policy vector index is loaded directly from local storage.

**Acceptance Scenarios**:

1. **Given** a raw policy guideline PDF, **When** the ingestion engine processes it, **Then** the policy's textual requirements are embedded, and a persistent index folder is created on disk.
2. **Given** a restarted system, **When** a policy search is triggered, **Then** the persistent index is loaded instantly from disk without re-parsing the original PDF.

---

### User Story 2 - Hybrid Semantic and Keyword Policy Retrieval (Priority: P1)

As a Prior Authorization Reviewer, I want the search engine to use a hybrid lookup approach that prioritizes exact CPT codes but gracefully falls back to clinical concept semantic search, so that I can retrieve the correct policy even when the provider request uses synonyms or misspells technical names.

**Why this priority**: Solves the fragility of exact-keyword searches. Ensures high coverage across varied medical terminology while maintaining 100% precision for correct billing codes.

**Independent Test**: Can be tested by searching for a policy using either a CPT code (e.g. `72148`) or a fuzzy semantic description (e.g. "joint space narrowing knee surgery") and verifying that both correctly resolve to their respective policy documents.

**Acceptance Scenarios**:

1. **Given** a case with a CPT code `96372`, **When** the search is run, **Then** the exact matching policy (Adalimumab) is returned with top priority.
2. **Given** a search query with semantic synonyms like "back pain radiating down leg", **When** queried, **Then** the search matches the Lumbar MRI policy based on clinical context, even if the text does not explicitly mention the term "MRI" initially.

---

### Edge Cases

- **CPT Not Found**: If an intake request has a CPT code not present in the ingested policies, the system must perform a semantic fallback search using the requested service name and log the fallback attempt in the audit trail.
- **Corrupt PDF Ingestion**: If a policy PDF is malformed or unreadable, the system must throw a clear, human-readable error without corrupting existing indexes.
- **Ambiguous Queries**: If a semantic search matches multiple policies with similar scores, the system must present the reviewer with a list of top candidates.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: The system MUST support pre-indexing policy guidelines from local files (`data/guidelines/`) and saving the index persistently to a disk directory.
- **FR-002**: The policy retriever MUST combine keyword-based search (lexical) and semantic vector search using a rank fusion mechanism.
- **FR-003**: The search pipeline MUST check for exact CPT code matching first, bypassing the hybrid model if an exact match is resolved.
- **FR-004**: The system MUST expose an initialization or CLI utility to build/refresh the persistent policy index.
- **FR-005**: The `EvidenceAgent` MUST use this hybrid index to resolve policy rules and search patient clinical notes.

### Key Entities

- **PolicyIndex**: A persistent file-based index (containing vector and lexical structures) representing ingested policy documents.
- **ResolvedPolicy**: A clinical guidelines object containing CPT code, service name, requirements, and clinical prerequisites extracted from the policy.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: The search system resolves the correct policy document for 100% of the standard test cases (MRI, Adalimumab, Knee Replacement).
- **SC-002**: Average query lookup time against the persistent index must be under 1.0 second.
- **SC-003**: The hybrid index resolves the correct policy when queried with clinical synonym variants containing 0% word-for-word overlap with the CPT code or service name.

## Assumptions

- **A-001**: A fixed set of medical policy PDFs exists in the repository under `data/guidelines/`.
- **A-002**: The OpenAI API key is configured and active for generating embeddings.
- **A-003**: Ingestion is a build-time or admin-controlled action rather than a real-time patient-facing activity.
