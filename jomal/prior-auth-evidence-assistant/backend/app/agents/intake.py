"""
Intake Agent.
Responsible for processing newly uploaded policies, extracting requirements,
and embedding them for the RAG pipeline.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from qdrant_client.models import PointStruct

from app.db.models import PolicyRequirement
from app.services.document import document_service
from app.services.ollama import ollama_client
from app.services.chunking import chunking_service
from app.services.embedding import embedding_client, sparse_encoder
from app.services.qdrant import qdrant_service

logger = logging.getLogger("pa.agents.intake")

@dataclass
class PolicyIngestionResult:
    extracted_requirements_count: int
    chunk_count: int


class IntakeAgent:
    async def ingest_policy(
        self, 
        db: AsyncSession, 
        policy_id: str, 
        document_bytes: bytes, 
        filename: str, 
        file_type: str
    ) -> PolicyIngestionResult:
        """
        1. Parse document
        2. Extract requirements via LLM
        3. Save to DB
        4. Chunk text
        5. Embed chunks
        6. Upsert to Qdrant
        """
        logger.info(f"Ingesting policy {policy_id} ({filename})")
        
        # 1. Parse document
        doc_result = await document_service.process_document(document_bytes, filename, file_type)
        full_text = doc_result.full_text
        
        # 2. Extract requirements via LLM
        prompt = f"Policy Document Text:\n{full_text[:4000]}\n\nExtract all medical necessity requirements and evidence requirements from this policy."
        system_prompt = "You are a medical policy analyst. Extract precise requirements."
        format_schema = {
            "type": "object",
            "properties": {
                "requirements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "requirement_text": {"type": "string"},
                            "requirement_category": {"type": "string"}
                        },
                        "required": ["requirement_text", "requirement_category"]
                    }
                }
            },
            "required": ["requirements"]
        }
        
        extracted_reqs_count = 0
        try:
            llm_response = await ollama_client.generate(prompt, system_prompt, format_schema)
            # parse response
            parsed = json.loads(llm_response)
            reqs = parsed.get("requirements", [])
            
            # 3. Save PolicyRequirement records to Postgres
            for idx, r in enumerate(reqs):
                db_req = PolicyRequirement(
                    policy_id=policy_id,
                    requirement_text=r.get("requirement_text", ""),
                    ordinal=idx
                )
                db.add(db_req)
            await db.flush() # flush to get IDs if needed
            extracted_reqs_count = len(reqs)
        except Exception as e:
            logger.error(f"Failed to extract requirements from policy {policy_id}: {e}")
            # we continue even if extraction fails, to at least index the text

        # 4. Chunk full text
        chunks = chunking_service.chunk_text(full_text)
        
        # 5. Embed chunks
        if chunks:
            chunk_texts = [c.text for c in chunks]
            
            dense_embeddings = await embedding_client.embed(chunk_texts)
            sparse_embeddings = sparse_encoder.encode_sparse(chunk_texts)
            
            # 6. Upsert into Qdrant
            points = []
            for i, chunk in enumerate(chunks):
                payload = {
                    "doc_type": "policy_chunk",
                    "policy_id": str(policy_id),
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "text": chunk.text,
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char
                }
                
                point_id = str(uuid.uuid4())
                points.append(
                    PointStruct(
                        id=point_id,
                        vector={
                            "dense": dense_embeddings[i],
                            "sparse": sparse_embeddings[i],
                        },
                        payload=payload
                    )
                )
            
            await qdrant_service.ensure_collection()
            await qdrant_service.upsert_points(points)
            
        return PolicyIngestionResult(
            extracted_requirements_count=extracted_reqs_count,
            chunk_count=len(chunks)
        )

intake_agent = IntakeAgent()
