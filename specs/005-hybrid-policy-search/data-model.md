# Data Model: Persistent Hybrid Policy Document Search

## 1. Storage Schema

### A. Persistent FAISS Index File Layout
The vector store is serialized locally on the file system at `data/indices/policies_faiss/`:
- `index.faiss`: Binary file holding the search index, containing the high-dimensional vector representations of policy document chunks.
- `index.pkl`: Python pickle file containing the mapping of index coordinates to the underlying `Document` text and metadata (source PDF name, page number).

### B. Persistent BM25 Index File Layout
The lexical keyword index is serialized locally as a single pickle file at `data/indices/policies_bm25.pkl`:
- `policies_bm25.pkl`: Python pickle file containing:
  - List of preprocessed `Document` objects.
  - Initialized `BM25Retriever` state (document frequencies, token mappings).

---

## 2. SessionState In-Memory Schema
We extend `SessionState` to track the output of the policy document retrieval phase:

```python
@dataclass
class SessionState:
    # Existing fields...
    request_id: str = ""
    patient_data: dict[str, Any] = field(default_factory=dict)
    classification: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    gap_analysis: dict[str, Any] = field(default_factory=dict)
    
    # Policy mapping outcomes
    current_policy_rules: list[str] = field(default_factory=list)
    current_required_docs: list[str] = field(default_factory=list)
    
    # NEW: Hybrid policy retrieval metadata
    retrieved_policy_passages: list[dict[str, Any]] = field(default_factory=list)
    # Each entry in retrieved_policy_passages contains:
    # {
    #     "text": str,          # Raw text chunk from the policy PDF
    #     "source": str,        # Name of PDF file (e.g. PA-Notification-Adalimumab.pdf)
    #     "page": int,          # Page number in PDF
    #     "score": float        # Fusion match score
    # }
```

---

## 3. Policy Document Schema
During the ingestion parsing phase, each chunk is stored as a LangChain `Document` with structured metadata:

```json
{
  "page_content": "Clinical criteria for Adalimumab: Rheumatoid Arthritis...",
  "metadata": {
    "source": "PA-Notification-Adalimumab.pdf",
    "page": 2,
    "cpt_codes": ["96372", "90281"]
  }
}
```
