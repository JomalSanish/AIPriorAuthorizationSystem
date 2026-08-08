# Agent Specification

## 1. Workflow Agent (T054, T055, FR-014 to FR-018)
- **Role**: LLM-driven planner orchestrating the pipeline.
- **Whitelist**: `call_intake_agent`, `call_retrieval_agent`, `call_reasoning_agent`, `call_summary_agent`, `request_additional_evidence`, `finalize_to_nurse_review`.
- **Guardrails**:
  - Validates output against whitelist. Re-prompts on failure up to 3 times. If retries exhaust, defaults to `finalize_to_nurse_review` **(subject to the FR-018 check: if Summary hasn't run yet, force `call_summary_agent` first)**.
  - Turn budget cap (forces finalization with the same Summary check).
  - Summary MUST run before finalization.
  - Never emits accept/reject decisions.
  - Writes audit logs before executing planned actions.

## 2. Intake Agent (T031, T039-041, FR-007, FR-011)
- **Role**: Document parsing and auto-extraction.
- **Functions**:
  - `ingest_policy()`: Extracts requirements, chunks text, embeddings, stores in Qdrant.
  - `process_case_documents()`: Parses, chunks, embeddings case docs.
  - `extract_case_metadata()`: Extracts fields `{member_id, provider_id, cpt_code, icd_code, service_type}` using LLM. Prompt includes *only* target document text (FR-043b).
  - `generate_case_profile()`: Creates dense/sparse indexed summary point for NLP case search.

## 3. Retrieval Agent (T045-047, FR-020, FR-036)
- **Role**: Hybrid RRF search implementation.
- **Functions**:
  - `retrieve_evidence()`: Embeds requirement query, performs hybrid search over case chunks, fuses results.
  - `parse_search_query()`: NLP query understanding, returns `{semantic_query, filters}`.
  - `execute_case_search()`: Executes hybrid case_profile search using extracted semantic query and filters.

## 4. Reasoning Agent (T050-051, FR-021)
- **Role**: Evidence classification.
- **Functions**:
  - `classify_requirement()`: Classifies evidence as Present/Absent/Unclear. Prompt includes *only* requirement text and retrieved chunks (FR-043b).
  - Computes composite confidence (0.4 × retrieval + 0.6 × llm).
  - Requires citations for Present/Unclear verdicts.

## 5. Summary Agent (T052, FR-022)
- **Role**: Creates nurse-facing evidence summary.
- **Functions**:
  - `generate_summary()`: Generates structured summary and gap checklist from verdicts.
  - Output MUST be composed from requirement verdicts and short cited excerpts — never reproducing full source documents verbatim (FR-043b, Constitution P4).
  - Flags partial analysis or extraction failures.
