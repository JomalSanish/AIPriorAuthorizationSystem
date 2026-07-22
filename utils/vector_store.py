from __future__ import annotations

import hashlib
import os
import pickle
import re
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from utils.pdf_utils import chunk_pdf

# In-memory store cache to prevent reloading during a single session or run
_STORE_CACHE: dict[str, FAISS] = {}


def get_vector_store(pdf_path: Path, openai_api_key: str | None = None) -> FAISS:
    """Load, chunk, and index a policy PDF using FAISS and OpenAI/Resilient Embeddings."""
    path_key = str(pdf_path.resolve())
    if path_key in _STORE_CACHE:
        return _STORE_CACHE[path_key]

    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

    # Resolve paths carefully
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF guidelines file not found at: {pdf_path}")

    # Chunk PDF
    chunks = chunk_pdf(pdf_path)
    if not chunks:
        chunks = [
            Document(
                page_content="Prior Authorization Policy Guidelines: Standard Procedure.",
                metadata={"source": pdf_path.name, "page": 1},
            )
        ]

    # Initialize Embeddings & FAISS
    embeddings = ResilientEmbeddings(openai_api_key=api_key)
    db = FAISS.from_documents(chunks, embeddings)
    _STORE_CACHE[path_key] = db
    return db


def build_in_memory_store(documents: list[Document], openai_api_key: str | None = None) -> FAISS:
    """Build a temporary in-memory FAISS database for uploaded documents."""
    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

    embeddings = ResilientEmbeddings(openai_api_key=api_key)
    if not documents:
        documents = [Document(page_content="No clinical documents uploaded.", metadata={"source": "upload", "page": 1})]
    return FAISS.from_documents(documents, embeddings)


def load_persistent_policy_store(
    faiss_path: Path | str = "data/indices/policies_faiss",
    bm25_path: Path | str = "data/indices/policies_bm25.pkl",
    openai_api_key: str | None = None
) -> tuple[FAISS, BM25Retriever] | None:
    """Load both the persistent FAISS index and serialized BM25 index from disk."""
    faiss_dir = Path(faiss_path)
    bm25_file = Path(bm25_path)

    if not faiss_dir.exists() or not bm25_file.exists():
        return None

    api_key = openai_api_key or os.getenv("OPENAI_API_KEY")

    embeddings = ResilientEmbeddings(openai_api_key=api_key)
    db = FAISS.load_local(str(faiss_dir), embeddings, allow_dangerous_deserialization=True)

    with open(bm25_file, "rb") as f:
        bm25_data = pickle.load(f)

    if isinstance(bm25_data, BM25Retriever):
        bm25_retriever = bm25_data
    elif isinstance(bm25_data, list):
        bm25_retriever = BM25Retriever.from_documents(bm25_data)
    else:
        raise TypeError("Unknown format in BM25 index pickle.")

    return db, bm25_retriever


def hybrid_policy_search(
    query: str,
    faiss_db: FAISS,
    bm25_retriever: BM25Retriever,
    cpt_code: str | None = None,
    k: int = 3,
    alpha: float = 0.5
) -> list[tuple[Document, float]]:
    """Perform hybrid search over policy guidelines using combined dense and sparse retrieval ranks."""
    # 0. CPT code priority routing: if CPT matches a page's parsed CPT codes exactly, return immediately
    if cpt_code:
        cpt_str = str(cpt_code).strip()
        cpt_matches: list[tuple[Document, float]] = []
        if hasattr(bm25_retriever, "docs"):
            for doc in bm25_retriever.docs:
                if cpt_str in doc.metadata.get("cpt_codes", []):
                    cpt_matches.append((doc, 20.0))  # Assign high static match score
        if cpt_matches:
            cpt_matches.sort(key=lambda x: (x[0].metadata.get("source", ""), x[0].metadata.get("page", 0)))
            return cpt_matches[:k]

    # 1. Retrieve from BM25
    bm25_docs = bm25_retriever.invoke(query)[:k*2]

    # 2. Retrieve from FAISS
    # similarity_search_with_relevance_scores returns tuples of (doc, score)
    faiss_results = faiss_db.similarity_search_with_relevance_scores(query, k=k*2)

    doc_scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    def doc_key(doc: Document) -> str:
        source_name = str(doc.metadata.get("source", "unknown"))
        page_num = int(doc.metadata.get("page", 0))
        return f"{source_name}_p{page_num}_{doc.page_content[:50]}"

    # Process FAISS results
    for rank, (doc, score) in enumerate(faiss_results):
        key = doc_key(doc)
        doc_map[key] = doc
        doc_scores[key] = doc_scores.get(key, 0.0) + alpha * score

    # Process BM25 results
    for rank, doc in enumerate(bm25_docs):
        key = doc_key(doc)
        doc_map[key] = doc
        # RRF Rank-based score mapped to similar scale
        lexical_score = (1.0 / (rank + 60.0)) * 10.0
        doc_scores[key] = doc_scores.get(key, 0.0) + (1.0 - alpha) * lexical_score

    # Apply CPT code matching boost if CPT is present in query context
    if cpt_code:
        cpt_str = str(cpt_code).strip()
        for key, doc in doc_map.items():
            if cpt_str in doc.page_content or cpt_str in str(doc.metadata.get("cpt_codes", [])):
                doc_scores[key] = doc_scores.get(key, 0.0) + 10.0

    # Sort and slice
    sorted_candidates = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
    results: list[tuple[Document, float]] = []
    for key, score in sorted_candidates[:k]:
        results.append((doc_map[key], score))

    return results


class HashingEmbeddings(Embeddings):
    """Local, offline, zero-dependency deterministic hashing embedding model."""

    def __init__(self, dimension: int = 1536) -> None:
        self.dimension = dimension

    def _embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        words = re.findall(r"\b\w+\b", text.lower())
        if not words:
            return vector
        for word in words:
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            vector[idx] += 1.0
        # Normalize (L2 norm)
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)


class ResilientEmbeddings(Embeddings):
    """Embeddings wrapper that falls back to Gemini and then HashingEmbeddings if OpenAI calls fail."""

    def __init__(self, openai_api_key: str | None = None) -> None:
        self.openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        
        self.openai: OpenAIEmbeddings | None = None
        self.gemini: Any | None = None
        self.fallback = HashingEmbeddings()
        self.is_fallback = True

        if self.openai_key:
            try:
                self.openai = OpenAIEmbeddings(openai_api_key=self.openai_key)
                self.is_fallback = False
            except Exception:
                pass

        if self.gemini_key:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                # Use Google Generative AI Embeddings, scaling to 1536 dimensions
                self.gemini = GoogleGenerativeAIEmbeddings(
                    model="models/gemini-embedding-2",
                    google_api_key=self.gemini_key,
                    output_dimensionality=1536
                )
                if not self.openai:
                    self.is_fallback = False
            except Exception as e:
                print(f"Failed to initialize GoogleGenerativeAIEmbeddings: {e}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        # 1. Try OpenAI
        if self.openai:
            try:
                return self.openai.embed_documents(texts)
            except Exception as e:
                print(f"OpenAI embedding failed: {e}. Trying Gemini embedding fallback...")
        
        # 2. Try Gemini
        if self.gemini:
            try:
                result = self.gemini.embed_documents(texts)
                self.is_fallback = False
                return result
            except Exception as e:
                print(f"Gemini embedding failed: {e}. Falling back to local offline HashingEmbeddings.")
                self.is_fallback = True
        else:
            self.is_fallback = True

        # 3. Try Local Hashing Fallback
        return self.fallback.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        # 1. Try OpenAI
        if self.openai:
            try:
                return self.openai.embed_query(text)
            except Exception as e:
                print(f"OpenAI embedding failed: {e}. Trying Gemini embedding fallback...")
        
        # 2. Try Gemini
        if self.gemini:
            try:
                result = self.gemini.embed_query(text)
                self.is_fallback = False
                return result
            except Exception as e:
                print(f"Gemini embedding failed: {e}. Falling back to local offline HashingEmbeddings.")
                self.is_fallback = True
        else:
            self.is_fallback = True

        # 3. Try Local Hashing Fallback
        return self.fallback.embed_query(text)


class HybridPolicyRetriever:
    """Retriever wrapper combining FAISS semantic vector store and BM25 lexical retriever."""

    def __init__(
        self,
        faiss_db: FAISS,
        bm25_retriever: BM25Retriever,
        alpha: float = 0.5
    ) -> None:
        self.faiss_db = faiss_db
        self.bm25_retriever = bm25_retriever
        self.alpha = alpha

    def search(self, query: str, cpt_code: str | None = None, k: int = 3) -> list[tuple[Document, float]]:
        """Search policy guidelines using both BM25 and FAISS dense index queries."""
        return hybrid_policy_search(
            query=query,
            faiss_db=self.faiss_db,
            bm25_retriever=self.bm25_retriever,
            cpt_code=cpt_code,
            k=k,
            alpha=self.alpha
        )


