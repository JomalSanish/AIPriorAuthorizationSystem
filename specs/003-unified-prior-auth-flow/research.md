# Research & Decisions: Unified Prior Auth Flow & Mock Policy Ground Truth

## Decisions

### 1. Mock Policy Database Design
- **Decision**: Store ground-truth policies in a JSON-formatted database at `data/mock_policies.json`.
- **Rationale**: A structured JSON format is machine-readable and eliminates the non-deterministic nature of parsing unstructured PDFs, ensuring high-fidelity matching of clinical criteria.
- **Alternatives Considered**: Keeping policies in a local PDF document. Rejected because extracting explicit structured checklists and specific CPT validation requirements from free-form PDF text is prone to extraction errors and limits precision in gap verification.

### 2. RAG Agent Mapping Design
- **Decision**: Perform direct CPT-to-Policy lookup in the RAG agent to retrieve the ground truth guidelines, then build a temporary local vector store containing the chunks of the uploaded provider clinical documents to query against each requirement.
- **Rationale**: Maximizes retrieval relevance. Finding specific clinical evidence within provider documents is highly efficient when queries are derived directly from the exact policy rules retrieved from the database.
- **Alternatives Considered**: Vectorizing both the policy PDF and provider notes into a single vector database. Rejected because it risks confusing guidelines with case evidence and leads to lower citation precision.

### 3. Streamlined UI Workflow
- **Decision**: Implement a linear layout in Streamlit.
- **Rationale**: Removes friction for user roles (Intake, Nurse, Director). A top-to-bottom layout visualizes the data progression sequentially and naturally guides the user to action.
- **Alternatives Considered**: Role-based tabs (Intake, Nurse, Director views). Rejected because it requires the user to toggle tabs repeatedly, splitting the context and increasing cognitive load.

## References
- Core principles outlined in the [Prior Authorization Evidence Assistant Constitution](../../.specify/memory/constitution.md).
