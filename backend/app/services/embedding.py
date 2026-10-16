"""
Embedding Services.
Provides dense embeddings via local TEI container and sparse embeddings via FastEmbed.
Respects GPU Contention Guard.
"""

from __future__ import annotations

import logging
from typing import List, Iterable

import httpx
from qdrant_client.models import SparseVector
from fastembed import SparseTextEmbedding

from app.config import get_settings
from app.core.gpu_guard import gpu_guard, GpuPriority

logger = logging.getLogger("pa.services.embedding")

class EmbeddingClient:
    """TEI client for dense embeddings."""
    def __init__(self):
        self._settings = get_settings()
        self.base_url = self._settings.TEI_URL

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Calls TEI /embed endpoint.
        Returns 384-dim dense vectors.
        """
        if not texts:
            return []

        payload = {"inputs": texts}
        timeout = 30.0

        async with gpu_guard.acquire_or_fallback(GpuPriority.EMBEDDING, timeout=60.0) as acquired:
            if not acquired:
                # TEI is configured in docker to run on CPU if GPU is unavailable, 
                # but if we are waiting on a GPU-bound lock and time out, we can proceed
                # since TEI handles concurrent requests. However, our architecture restricts
                # TEI to GPU or strict CPU fallback. Since TEI is in a container, we just 
                # let it process. If lock acquired, we hold it.
                logger.warning("TEI Embedding GPU lock timed out. Proceeding without lock (container will handle).")

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"{self.base_url}/embed", json=payload)
                    response.raise_for_status()
                    return response.json()
            except Exception as e:
                logger.error(f"TEI Embedding failed: {e}")
                raise

class SparseEncoder:
    """FastEmbed client for sparse BM25-style embeddings (CPU only)."""
    def __init__(self):
        # Initialize lazily to save memory during startup
        self._model = None

    def _get_model(self) -> SparseTextEmbedding:
        if self._model is None:
            logger.info("Loading FastEmbed Sparse model (CPU)...")
            self._model = SparseTextEmbedding(model_name="prithivida/Splade_PP_en_v1")
        return self._model

    def encode_sparse(self, texts: List[str]) -> List[SparseVector]:
        """
        Returns Qdrant-compatible sparse vectors.
        """
        if not texts:
            return []
            
        model = self._get_model()
        
        # model.embed returns a generator of SparseEmbedding objects
        # Each has .indices (list of int) and .values (list of float)
        embeddings = list(model.embed(texts))
        
        results = []
        for emb in embeddings:
            results.append(
                SparseVector(
                    indices=emb.indices.tolist() if hasattr(emb.indices, "tolist") else list(emb.indices),
                    values=emb.values.tolist() if hasattr(emb.values, "tolist") else list(emb.values),
                )
            )
        return results

embedding_client = EmbeddingClient()
sparse_encoder = SparseEncoder()
