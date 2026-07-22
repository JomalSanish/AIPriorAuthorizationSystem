# Research: Persistent Hybrid Policy Document Search

## Core Architecture Decisions

### Decision 1: Index Persistence & Storage Location
* **Selected Option**: File-system-based FAISS index serialization.
* **Storage Location**: `data/indices/policies_faiss/` (for FAISS) and `data/indices/policies_bm25.pkl` (for BM25).
* **Rationale**: Since policy guidelines change infrequently (usually updated on a monthly or quarterly basis), rebuilding the vector store on every server startup or agent execution is highly inefficient. FAISS provides `save_local` and `load_local` out-of-the-box, allowing us to load indices into memory instantly (in milliseconds) at runtime.
* **Alternative Considered**: 
  - *Database-hosted vector storage (e.g. pgvector or Qdrant)*: Rejected because it introduces external container dependencies (Docker/DB setup), which violates the project's **Prototype Scope Discipline** principle.
  - *JSON caching*: Rejected because it does not support semantic indexing or proximity searching on the PDF text directly.

### Decision 2: Hybrid Search Algorithm
* **Selected Option**: Reciprocal Rank Fusion (RRF) or Weighted Linear Scoring combining `FAISS` (dense vector search) and `BM25` (sparse lexical search).
* **Implementation Details**:
  - We will use `OpenAIEmbeddings` (`text-embedding-3-small`) to generate dense vectors.
  - We will use `BM25Retriever` from `langchain_community.retrievers` for lexical keyword queries.
  - Because CPT codes (e.g., `72148`) are alphanumeric, standard dense vectors have low semantic sensitivity to single-digit changes. We will inject a custom query preprocessing step: if a CPT code is detected in the input, we prioritize exact keyword matches for that CPT code in the BM25/Lexical query step.
  - We will combine the candidates from both retrievers using a weighted scoring model:
    $$\text{Score} = \alpha \cdot \text{SemanticScore} + (1 - \alpha) \cdot \text{LexicalScore}$$
    where $\alpha = 0.5$ by default.

### Decision 3: Ingestion Command Line Utility
* **Selected Option**: Admin CLI command `python utils/ingest_policies.py`.
* **Rationale**: Decoupling the ingestion phase from the runtime agent execution keeps the Streamlit app fast and clean. The ingestion script will parse all PDFs under `data/guidelines/`, chunk the text using page-aware metadata tracking, embed, and write the persistent indices.

---

## Technical Context & Constraints
- **Language**: Python 3.11+
- **Key Dependencies**: `faiss-cpu`, `langchain-community`, `langchain-openai`, `pypdf`, `rank_bm25`
- **OpenAI Model**: `text-embedding-3-small` (or fallback to `text-embedding-ada-002`)
