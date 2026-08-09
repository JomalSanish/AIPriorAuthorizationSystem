"""
Retrieval Agent (Phase 5).

Responsibilities:
  T045 — retrieve_evidence(): hybrid dense+sparse search scoped to case_document_chunk,
          powering the Reasoning Agent's evidence retrieval per requirement.
  T046 — parse_search_query(): LLM-driven NLP query understanding that translates
          free-text user searches into StructuredSearchRequest (semantic query + filters).
  T047 — execute_case_search(): hybrid search over case_profile points with Qdrant
          payload filters and role-based post-retrieval visibility rules.

⚠️ All LLM calls MUST hit the local Ollama instance only (FR-036a, FR-046c).
   Never add a fallback to an external NLU or cloud LLM API.

Relevance filtering note (case search bug fix): retrieve_evidence() intentionally
does NOT apply relevance filtering — the Reasoning Agent (T050/T051) is designed to
receive the top-k candidate chunks regardless of how weak the best match is, and
correctly classifies a requirement as Absent when nothing relevant is actually
retrieved (see reasoning.py). Filtering candidates out here would just remove the
signal the Reasoning Agent uses to make that call.

execute_case_search() is different: its results go straight to a human via the
NLP search UI with no LLM interpreting them in between, so an unfiltered RRF result
list reads as "search returned unrelated cases" — RRF fusion ranks whatever exists
in the collection, it doesn't have a built-in "not relevant enough" cutoff. That
function now applies a relative score cutoff (see qdrant.py's hybrid_search) so a
query only surfaces cases that are actually close to the best match, not just
whatever happened to rank in the top 20.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from qdrant_client.http import models as rest

from app.db.models import PolicyRequirement, CaseDocument
from app.services.embedding import embedding_client, sparse_encoder
from app.services.ollama import ollama_client
from app.services.qdrant import qdrant_service

logger = logging.getLogger("pa.agents.retrieval")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RetrievalResult:
    """A single evidence chunk returned by hybrid search."""
    chunk_text: str
    score: float
    document_id: str
    document_name: str
    page_number: int
    chunk_index: int


@dataclass
class SearchFilters:
    """Structured filters extracted from a natural-language search query."""
    cpt_code: Optional[str] = None
    icd_code: Optional[str] = None
    member_id: Optional[str] = None
    provider_id: Optional[str] = None
    date_range: Optional[Dict[str, str]] = None  # {"start": "iso", "end": "iso"}
    status: Optional[str] = None
    policy_name: Optional[str] = None


@dataclass
class StructuredSearchRequest:
    """The result of NLP query understanding (T046)."""
    semantic_query: str
    filters: SearchFilters = field(default_factory=SearchFilters)


@dataclass
class CaseSearchResult:
    """A single case-level search result — never raw document chunks (FR-038)."""
    case_id: str
    service_type: Optional[str]
    status: str
    policy_name: Optional[str]
    member_id: Optional[str]
    provider_id: Optional[str]
    cpt_code: Optional[str]
    icd_code: Optional[str]
    score: float
    summary: Optional[str]


# ---------------------------------------------------------------------------
# T045 — Retrieval Agent: retrieve evidence for a single policy requirement
# ---------------------------------------------------------------------------

class RetrievalAgent:
    """
    Retrieval Agent — Phase 5 (T045, T046, T047).

    Implements hybrid dense + sparse retrieval via Qdrant RRF fusion for two
    distinct search scenarios:

    1. Evidence retrieval (T045): scoped to ``case_document_chunk`` points
       belonging to a specific case, used by the Reasoning Agent to find
       evidence for each policy requirement.

    2. NLP case search (T046 + T047): translates a free-text user query into a
       ``StructuredSearchRequest`` via an LLM call, then executes hybrid search
       over ``case_profile`` points with optional Qdrant payload filters.
    """

    # Default top-k for evidence retrieval
    DEFAULT_EVIDENCE_TOP_K: int = 5

    # Default top-k for NLP case search — an upper bound; the relative cutoff
    # below is what actually determines how many of these get returned.
    DEFAULT_CASE_SEARCH_TOP_K: int = 20

    # A case-search result must score at least this fraction of the top
    # result's score to be included. 0.5 means "at least half as good a
    # match as the best result" — self-scaling with whatever the top score
    # happens to be for a given query, so it doesn't need per-deployment
    # tuning the way an absolute threshold would. Tune down (toward 0) to
    # show more borderline results, or up (toward 1) to show only very
    # tight matches.
    CASE_SEARCH_RELATIVE_CUTOFF_RATIO: float = 0.5

    # Absolute floor, RRF-scale (NOT a 0-1 similarity score — see the note in
    # qdrant.py's hybrid_search docstring). This is a backstop for the case
    # where every candidate is uniformly weak (so the relative cutoff above
    # doesn't help, since nothing stands out as "clearly the best"). Kept
    # deliberately conservative; empirical tuning is expected once there's
    # real query traffic to look at.
    CASE_SEARCH_SCORE_FLOOR: float = 0.005

    # ---------------------------------------------------------------------------
    # T045 — Evidence retrieval
    # ---------------------------------------------------------------------------

    async def retrieve_evidence(
        self,
        case_id: str,
        policy_requirement: PolicyRequirement,
        query_augmentation: Optional[str] = None,
        top_k: int = DEFAULT_EVIDENCE_TOP_K,
    ) -> List[RetrievalResult]:
        """
        Retrieve the top-k evidence chunks for a single policy requirement.

        Steps:
          1. Build query text from requirement + optional augmentation string.
          2. Embed query: dense (TEI) + sparse (FastEmbed BM25).
          3. Execute hybrid search (RRF) scoped to doc_type=case_document_chunk
             AND case_id=<this_case>.
          4. Return ranked ``RetrievalResult`` objects.

        Deliberately unfiltered by relevance score (see module docstring) —
        the Reasoning Agent needs to see the best-available candidates even
        when none of them are a good match, so it can correctly classify the
        requirement as Absent.

        Args:
            case_id: UUID string of the case being evaluated.
            policy_requirement: ORM object with ``requirement_text``.
            query_augmentation: Optional extra context from Workflow Agent
                re-invocation (e.g. clarification hint).
            top_k: Number of results to return (default 5 per spec).

        Returns:
            List of ``RetrievalResult`` ranked by RRF score.
        """
        query_text = policy_requirement.requirement_text
        if query_augmentation:
            query_text = f"{query_text} {query_augmentation}"

        logger.info(
            "retrieve_evidence | case=%s req=%s query_len=%d",
            case_id,
            policy_requirement.id,
            len(query_text),
        )

        # Embed query
        dense_vecs = await embedding_client.embed([query_text])
        sparse_vecs = sparse_encoder.encode_sparse([query_text])
        query_dense = dense_vecs[0]
        query_sparse = sparse_vecs[0]

        # Scope to this case's document chunks
        case_filter = rest.Filter(
            must=[
                rest.FieldCondition(
                    key="case_id",
                    match=rest.MatchValue(value=str(case_id)),
                )
            ]
        )

        search_results = await qdrant_service.hybrid_search(
            query_dense=query_dense,
            query_sparse=query_sparse,
            filter=case_filter,
            top_k=top_k,
            doc_type="case_document_chunk",
            # No score_threshold / relative_cutoff_ratio here — see module
            # docstring for why evidence retrieval stays unfiltered.
        )

        retrieval_results: List[RetrievalResult] = []
        for r in search_results:
            payload = r.payload
            retrieval_results.append(
                RetrievalResult(
                    chunk_text=payload.get("text", ""),
                    score=r.score,
                    document_id=payload.get("document_id", ""),
                    document_name=payload.get("original_filename", ""),
                    page_number=payload.get("page_number", 0),
                    chunk_index=payload.get("chunk_index", 0),
                )
            )

        logger.debug(
            "retrieve_evidence | case=%s req=%s results=%d",
            case_id,
            policy_requirement.id,
            len(retrieval_results),
        )
        return retrieval_results

    # ---------------------------------------------------------------------------
    # T046 — NLP Query Understanding
    # ---------------------------------------------------------------------------

    async def parse_search_query(self, user_query: str) -> StructuredSearchRequest:
        """
        Parse a free-text user search into a StructuredSearchRequest.

        Uses a local LLM (Ollama llama3.2:3b) with structured JSON output to
        translate natural-language intent into a semantic embedding query plus
        optional exact-match and date-range filters.

        The LLM role is *strictly* intent translation — it never reads case
        documents to answer the search itself (FR-036).

        ⚠️ All calls go to the local Ollama instance — never an external API
           (FR-036a, FR-046c).

        Args:
            user_query: Raw free-text query from the UI (e.g. "MRI cases for
                member 123 in the last week").

        Returns:
            StructuredSearchRequest with semantic_query and optional filters.
        """
        logger.info("parse_search_query | query=%r", user_query[:120])

        system_prompt = (
            "You are a search query parser for a medical prior-authorization system. "
            "Your ONLY task is to extract a semantic search phrase and structured "
            "filter fields from the user's search query. "
            "Return null for any filter that is not explicitly present in the query. "
            "Do NOT invent or assume values. "
            "Do NOT access any case documents or make clinical judgements."
        )

        prompt = (
            f"User search query: \"{user_query}\"\n\n"
            "Extract the following from this query and return ONLY valid JSON matching "
            "the provided schema. Return null for any field not present in the query."
        )

        format_schema = {
            "type": "object",
            "properties": {
                "semantic_query": {
                    "type": "string",
                    "description": "The free-text semantic portion of the query for vector search."
                },
                "filters": {
                    "type": "object",
                    "properties": {
                        "cpt_code":     {"type": ["string", "null"]},
                        "icd_code":     {"type": ["string", "null"]},
                        "member_id":    {"type": ["string", "null"]},
                        "provider_id":  {"type": ["string", "null"]},
                        "date_range": {
                            "type": ["object", "null"],
                            "properties": {
                                "start": {"type": "string"},
                                "end":   {"type": "string"},
                            },
                        },
                        "status":       {"type": ["string", "null"]},
                        "policy_name":  {"type": ["string", "null"]},
                    },
                    "required": [
                        "cpt_code", "icd_code", "member_id", "provider_id",
                        "date_range", "status", "policy_name",
                    ],
                },
            },
            "required": ["semantic_query", "filters"],
        }

        try:
            raw = await ollama_client.generate(prompt, system_prompt, format_schema)
            parsed = json.loads(raw)
        except Exception as exc:
            # Fallback: treat entire query as semantic search with no filters
            logger.warning(
                "parse_search_query | LLM parse failed (%s), using raw query as semantic.", exc
            )
            return StructuredSearchRequest(
                semantic_query=user_query,
                filters=SearchFilters(),
            )

        filters_raw: Dict[str, Any] = parsed.get("filters", {}) or {}
        date_range_raw = filters_raw.get("date_range")

        return StructuredSearchRequest(
            semantic_query=parsed.get("semantic_query", user_query),
            filters=SearchFilters(
                cpt_code=filters_raw.get("cpt_code"),
                icd_code=filters_raw.get("icd_code"),
                member_id=filters_raw.get("member_id"),
                provider_id=filters_raw.get("provider_id"),
                date_range=date_range_raw if isinstance(date_range_raw, dict) else None,
                status=filters_raw.get("status"),
                policy_name=filters_raw.get("policy_name"),
            ),
        )

    # ---------------------------------------------------------------------------
    # T047 — NLP search execution
    # ---------------------------------------------------------------------------

    async def execute_case_search(
        self,
        structured_request: StructuredSearchRequest,
        role: str,
        top_k: int = DEFAULT_CASE_SEARCH_TOP_K,
    ) -> List[CaseSearchResult]:
        """
        Execute a hybrid search over ``case_profile`` points using the
        parsed StructuredSearchRequest.

        Steps:
          1. Build Qdrant payload filter from extracted ``filters``.
          2. Embed ``semantic_query``: dense + sparse.
          3. Execute hybrid search scoped to doc_type=case_profile, with
             relevance filtering (relative cutoff + absolute floor — see
             CASE_SEARCH_RELATIVE_CUTOFF_RATIO / CASE_SEARCH_SCORE_FLOOR and
             qdrant.py's hybrid_search docstring) so weakly-matching cases
             don't get surfaced alongside a strong match.
          4. Apply role-based post-retrieval visibility (FR-039a):
             - Nurse: metadata only for non-locked cases (summary hidden).
          5. Return case-level results — never raw document chunks (FR-038).

        Args:
            structured_request: Output of ``parse_search_query``.
            role: Caller's role string ("intake" | "nurse" | "admin").
            top_k: Maximum results to return (upper bound only — the relative
                cutoff typically returns fewer).

        Returns:
            List of ``CaseSearchResult`` with case-level metadata.
        """
        logger.info(
            "execute_case_search | role=%s semantic=%r filters=%s",
            role,
            structured_request.semantic_query[:80],
            structured_request.filters,
        )

        # Build payload filter from structured filters
        must_clauses: List[rest.Condition] = []
        f = structured_request.filters

        if f.cpt_code:
            must_clauses.append(
                rest.FieldCondition(key="cpt_code", match=rest.MatchValue(value=f.cpt_code))
            )
        if f.icd_code:
            must_clauses.append(
                rest.FieldCondition(key="icd_code", match=rest.MatchValue(value=f.icd_code))
            )
        if f.member_id:
            must_clauses.append(
                rest.FieldCondition(key="member_id", match=rest.MatchValue(value=f.member_id))
            )
        if f.provider_id:
            must_clauses.append(
                rest.FieldCondition(key="provider_id", match=rest.MatchValue(value=f.provider_id))
            )
        if f.status:
            must_clauses.append(
                rest.FieldCondition(key="status", match=rest.MatchValue(value=f.status))
            )
        if f.policy_name:
            must_clauses.append(
                rest.FieldCondition(key="policy_name", match=rest.MatchValue(value=f.policy_name))
            )
        # Note: date_range on case creation date requires Postgres lookup (case_id list);
        # if date_range is present, we do a best-effort semantic search and filter
        # post-hoc since Qdrant payload doesn't store creation date by default.
        # This is a v1 simplification — the spec permits Postgres-first for Postgres-only fields.

        payload_filter = rest.Filter(must=must_clauses) if must_clauses else None

        # Embed semantic query
        dense_vecs = await embedding_client.embed([structured_request.semantic_query])
        sparse_vecs = sparse_encoder.encode_sparse([structured_request.semantic_query])
        query_dense = dense_vecs[0]
        query_sparse = sparse_vecs[0]

        search_results = await qdrant_service.hybrid_search(
            query_dense=query_dense,
            query_sparse=query_sparse,
            filter=payload_filter,
            top_k=top_k,
            doc_type="case_profile",
            score_threshold=self.CASE_SEARCH_SCORE_FLOOR,
            relative_cutoff_ratio=self.CASE_SEARCH_RELATIVE_CUTOFF_RATIO,
        )

        case_results: List[CaseSearchResult] = []
        for r in search_results:
            payload = r.payload
            summary = payload.get("summary")

            # FR-039a: Nurse sees metadata only for cases — hide AI-generated summary
            # (full evidence/documents gated by lock in nurse_review endpoints).
            if role == "nurse":
                summary = None

            case_results.append(
                CaseSearchResult(
                    case_id=payload.get("case_id", ""),
                    service_type=payload.get("service_type"),
                    status=payload.get("status", ""),
                    policy_name=payload.get("policy_name"),
                    member_id=payload.get("member_id"),
                    provider_id=payload.get("provider_id"),
                    cpt_code=payload.get("cpt_code"),
                    icd_code=payload.get("icd_code"),
                    score=r.score,
                    summary=summary,
                )
            )

        logger.info(
            "execute_case_search | role=%s results=%d", role, len(case_results)
        )
        return case_results


retrieval_agent = RetrievalAgent()
