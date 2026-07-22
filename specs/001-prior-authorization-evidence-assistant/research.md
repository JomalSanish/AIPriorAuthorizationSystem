# Research Notes

## Decision: Retrieval strategy for the prototype

- Use PyPDF to extract text from the local policy PDF.
- Use a lightweight keyword and section-matching approach for retrieval instead of a full vector database so the prototype remains simple and local.
- Use LangChain prompt templates and deterministic routing logic to keep the multi-agent flow readable and testable.

## Rationale

The prototype must remain focused on the single available policy PDF and should not introduce unnecessary infrastructure. A simple retrieval approach is sufficient for a demo and keeps the dependency footprint smaller.

## Alternatives considered

- Full embeddings + vector database: rejected because it adds operational complexity beyond the prototype scope.
- Direct LLM-only reasoning without retrieved evidence: rejected because the app should show evidence-backed outputs grounded in the policy PDF.
