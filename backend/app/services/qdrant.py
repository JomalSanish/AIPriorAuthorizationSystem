"""
Qdrant Vector Database Service.
Handles hybrid search (dense + sparse) with RRF fusion.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as rest
from qdrant_client.models import PointStruct, Filter

from app.config import get_settings

logger = logging.getLogger("pa.services.qdrant")

@dataclass
class SearchResult:
    point_id: str | int
    score: float
    payload: Dict[str, Any]
    doc_type: str


class QdrantService:
    COLLECTION_NAME = "pa_documents"

    def __init__(self):
        self._settings = get_settings()
        self.client = AsyncQdrantClient(url=self._settings.QDRANT_URL)

    async def ensure_collection(self):
        """Creates collection if not exists with dense and sparse vector configs."""
        collections = await self.client.get_collections()
        if not any(c.name == self.COLLECTION_NAME for c in collections.collections):
            logger.info(f"Creating Qdrant collection: {self.COLLECTION_NAME}")
            
            await self.client.create_collection(
                collection_name=self.COLLECTION_NAME,
                vectors_config={
                    "dense": rest.VectorParams(
                        size=384,  # bge-small-en-v1.5
                        distance=rest.Distance.COSINE
                    )
                },
                sparse_vectors_config={
                    "sparse": rest.SparseVectorParams()
                }
            )
            
            # Create payload indexes for faster filtering
            await self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="doc_type",
                field_schema=rest.PayloadSchemaType.KEYWORD
            )
            await self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="policy_id",
                field_schema=rest.PayloadSchemaType.KEYWORD
            )
            await self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="case_id",
                field_schema=rest.PayloadSchemaType.KEYWORD
            )

    async def upsert_points(self, points: List[PointStruct]):
        """Upserts points into the collection."""
        if not points:
            return
        await self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=points
        )

    async def delete_points(self, filter: Filter):
        """Deletes points matching a specific filter."""
        await self.client.delete(
            collection_name=self.COLLECTION_NAME,
            points_selector=rest.FilterSelector(filter=filter)
        )

    async def hybrid_search(
        self,
        query_dense: List[float],
        query_sparse: rest.SparseVector,
        filter: Optional[Filter],
        top_k: int,
        doc_type: str,
        score_threshold: Optional[float] = None,
        relative_cutoff_ratio: Optional[float] = None,
    ) -> List[SearchResult]:
        """
        Prefetch dense + sparse results, fuse with Qdrant-native RRF.
        Filter is applied to scope by doc_type (e.g. policy_chunk or case_chunk).

        Relevance filtering (both optional, off by default — existing callers
        that don't pass these get identical behavior to before):

        - ``score_threshold``: an absolute floor passed straight to Qdrant's
          query API. NOTE — RRF fused scores are rank-based (roughly
          ``1 / (k + rank)`` per prefetch list, summed across dense + sparse;
          with Qdrant's default k=60 the theoretical max is ~0.033 for a
          point ranked #1 in both lists). This is NOT a 0–1 similarity score
          the way raw cosine similarity is, so don't reuse similarity-style
          thresholds (e.g. 0.7) here — start low (this module defaults
          callers to ~0.005 where used) and tune empirically once there's
          real query traffic to look at.
        - ``relative_cutoff_ratio``: a value in (0, 1]. After fusion, any
          result scoring below ``top_result.score * relative_cutoff_ratio``
          is dropped. This self-scales with whatever the top match's score
          happens to be for a given query, so it doesn't need the same
          empirical tuning ``score_threshold`` does — it directly targets
          "there's one clearly-best match and a long tail of much weaker
          ones," which is the shape of the problem that was causing NLP case
          search to surface unrelated results.
        """
        # Ensure doc_type is in the filter
        must_clauses = [
            rest.FieldCondition(
                key="doc_type",
                match=rest.MatchValue(value=doc_type)
            )
        ]
        
        if filter and filter.must:
            must_clauses.extend(filter.must if isinstance(filter.must, list) else [filter.must])
            
        combined_filter = rest.Filter(must=must_clauses)

        prefetch = [
            rest.Prefetch(
                query=query_dense,
                using="dense",
                limit=top_k * 2,
                filter=combined_filter,
            ),
            rest.Prefetch(
                query=rest.SparseVector(
                    indices=query_sparse.indices,
                    values=query_sparse.values,
                ),
                using="sparse",
                limit=top_k * 2,
                filter=combined_filter,
            )
        ]
        
        # In newer Qdrant, we use fusion=rest.Fusion.RRF natively via search API
        results = await self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            prefetch=prefetch,
            query=rest.FusionQuery(fusion=rest.Fusion.RRF),
            limit=top_k,
            score_threshold=score_threshold,
        )

        points = results.points

        # Relative cutoff: drop results far weaker than the best match.
        # query_points returns points sorted by score descending, so points[0]
        # is always the top score when the list is non-empty.
        if relative_cutoff_ratio is not None and points:
            top_score = points[0].score
            if top_score > 0:
                min_allowed = top_score * relative_cutoff_ratio
                points = [p for p in points if p.score >= min_allowed]

        # Convert to SearchResult
        final_results = []
        for p in points:
            final_results.append(
                SearchResult(
                    point_id=p.id,
                    score=p.score,
                    payload=p.payload or {},
                    doc_type=p.payload.get("doc_type", doc_type) if p.payload else doc_type
                )
            )
            
        return final_results

qdrant_service = QdrantService()
