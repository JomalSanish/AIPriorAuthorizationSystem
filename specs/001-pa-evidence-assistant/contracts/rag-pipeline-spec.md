# RAG Pipeline Specification

This document details the architecture of the Hybrid RAG pipeline.

## Embeddings (T027, T028)
- **Dense Encoder**: BAAI/bge-small-en-v1.5 served via local Hugging Face Text-Embeddings-Inference (TEI) container. CPU/GPU fallback managed by `GPU_PRIORITY_POLICY` (T023). Output dimension: 384.
- **Sparse Encoder**: `fastembed` BM25-style encoder (CPU-only, no GPU guard).

## Vector Store (T029, FR-043d)
- **Engine**: Qdrant (local Docker container).
- **Collections**: `pa_documents` (contains `policy_chunk`, `case_document_chunk`, `case_profile`).
- **Fusion**: Uses Qdrant-native Reciprocal Rank Fusion (`fusion=rrf`) to combine dense and sparse results.

## Text Chunking (T030)
- Sentence-aware chunking to prevent splitting mid-word.
- Configuration: `chunk_size=512`, `chunk_overlap=64`.
- Attributes: `start_char`, `end_char`, `page_number`, `chunk_index`.

## Retrieval Architecture (T045, FR-020)
- Retrieval Agent embeds the query (dense + sparse).
- Executes hybrid search scoped by `doc_type` and `case_id`.
- Returns top-k (default 5) most relevant evidence chunks with citations.
