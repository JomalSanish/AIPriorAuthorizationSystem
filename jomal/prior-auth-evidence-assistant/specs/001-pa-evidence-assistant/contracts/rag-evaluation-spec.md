# RAG Evaluation Specification

This document outlines the offline evaluation harness for the RAG pipeline.

## Golden Dataset (T087, FR-044)
- **Schema**: `case_document_text`, `policy_requirement`, `expected_retrieved_chunks`, `expected_verdict`, `expected_citation`.
- Data is entirely synthetic. No real PHI is permitted.

## Ragas Evaluation Harness (T088, T089)
- **Judge LLM**: `LangchainLLMWrapper` pointing to the local Ollama instance. **No OpenAI API fallback.**
- **Judge Embeddings**: `LangchainEmbeddingsWrapper` pointing to the local TEI instance. **No OpenAI API fallback.**
- **Metrics**: Context Precision (≥ 0.70), Context Recall (≥ 0.75), Faithfulness (≥ 0.80).
- **Isolation**: Runs against test database fixtures. Never connected to live `WorkflowAgent` or production Postgres.
- **Known Risk**: Small local judge models (llama3.2:3b) may fail to produce the structured
  output Ragas expects internally, which surfaces silently as NaN scores rather than an error.
  After implementing this harness, run it on 3–5 samples and confirm non-NaN scores BEFORE
  relying on it as a CI regression gate. If NaN scores appear, consider using a larger judge
  model on the dev machine specifically for evaluation — this harness runs offline and isn't
  bound by the same VRAM budget as the live pipeline.
