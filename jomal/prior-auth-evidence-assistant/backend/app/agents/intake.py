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
from sqlalchemy.future import select
from qdrant_client.models import PointStruct

from app.db.models import PolicyRequirement, CaseDocument, Case, Policy
from app.services.document import document_service
from app.services.ollama import ollama_client
from app.services.chunking import chunking_service
from app.services.embedding import embedding_client, sparse_encoder
from app.services.qdrant import qdrant_service

logger = logging.getLogger("pa.agents.intake")

@dataclass
class CaseDocumentResult:
    document_id: str
    chunk_count: int
    ocr_status: str
    full_text: str

@dataclass
class CaseMetadata:
    member_id: str | None
    provider_id: str | None
    cpt_code: str | None
    icd_code: str | None
    service_type: str | None

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

    async def process_case_documents(
        self,
        db: AsyncSession,
        case_id: str,
        documents: list[CaseDocument],
        document_files: dict[str, bytes]
    ) -> list[CaseDocumentResult]:
        """
        1. Parse each document
        2. Chunk text
        3. Embed chunks (dense + sparse)
        4. Upsert to Qdrant as case_document_chunk
        """
        logger.info(f"Processing {len(documents)} documents for case {case_id}")
        results = []

        for doc in documents:
            file_bytes = document_files.get(str(doc.id))
            if not file_bytes:
                logger.warning(f"No bytes provided for document {doc.id}")
                continue

            doc_result = await document_service.process_document(
                file_bytes, doc.original_filename, doc.file_type
            )
            
            # Update doc status
            doc.ocr_status = doc_result.ocr_status
            doc.extracted_text_length = len(doc_result.full_text)
            doc.sha256_hash = doc_result.sha256_hash
            db.add(doc)

            chunks = chunking_service.chunk_text(doc_result.full_text)
            if chunks:
                chunk_texts = [c.text for c in chunks]
                dense_embeddings = await embedding_client.embed(chunk_texts)
                sparse_embeddings = sparse_encoder.encode_sparse(chunk_texts)
                
                points = []
                for i, chunk in enumerate(chunks):
                    payload = {
                        "doc_type": "case_document_chunk",
                        "case_id": str(case_id),
                        "document_id": str(doc.id),
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

            results.append(
                CaseDocumentResult(
                    document_id=str(doc.id),
                    chunk_count=len(chunks),
                    ocr_status=doc_result.ocr_status,
                    full_text=doc_result.full_text,
                )
            )

        await db.flush()
        return results

    async def extract_case_metadata(self, case_id: str, combined_text: str) -> CaseMetadata:
        """
        Extract structured metadata from the combined text of case documents.
        """
        logger.info(f"Extracting metadata for case {case_id}")
        prompt = f"Case Document Text:\n{combined_text[:6000]}\n\nExtract key patient and medical procedure identifiers from this case."
        system_prompt = "You are a medical data extraction assistant. Extract requested fields exactly. Return null if not found."
        format_schema = {
            "type": "object",
            "properties": {
                "member_id": {"type": ["string", "null"]},
                "provider_id": {"type": ["string", "null"]},
                "cpt_code": {"type": ["string", "null"]},
                "icd_code": {"type": ["string", "null"]},
                "service_type": {"type": ["string", "null"]}
            },
            "required": ["member_id", "provider_id", "cpt_code", "icd_code", "service_type"]
        }

        try:
            llm_response = await ollama_client.generate(prompt, system_prompt, format_schema)
            parsed = json.loads(llm_response)
            return CaseMetadata(
                member_id=parsed.get("member_id"),
                provider_id=parsed.get("provider_id"),
                cpt_code=parsed.get("cpt_code"),
                icd_code=parsed.get("icd_code"),
                service_type=parsed.get("service_type")
            )
        except Exception as e:
            logger.error(f"Failed to extract metadata for case {case_id}: {e}")
            return CaseMetadata(None, None, None, None, None)

    async def generate_case_profile(self, db: AsyncSession, case_id: str) -> None:
        """
        Generate a case_profile summary point and store in Qdrant for NLP search.

        Runs as a BackgroundTasks job after case submission — failures here
        must not crash the request that scheduled it, so the whole body is
        guarded and logged rather than left to bubble up as a bare traceback.
        """
        logger.info(f"Generating case profile for case {case_id}")
        try:
            await self._generate_case_profile(db, case_id)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Failed to generate case profile for case {case_id}: {e}")

    async def _generate_case_profile(self, db: AsyncSession, case_id: str) -> None:
        # Load case and documents
        result = await db.execute(
            select(Case).where(Case.id == case_id)
        )
        case_record = result.scalars().first()
        if not case_record:
            return
            
        doc_result = await db.execute(
            select(CaseDocument).where(CaseDocument.case_id == case_id)
        )
        documents = doc_result.scalars().all()
        doc_titles = [d.original_filename for d in documents]
        
        policy_result = await db.execute(
            select(Policy).where(Policy.id == case_record.policy_id)
        )
        policy = policy_result.scalars().first()
        policy_name = policy.name if policy else "Unknown Policy"

        summary_prompt = (
            f"Case Context:\n"
            f"Member ID: {case_record.member_id}\n"
            f"Provider ID: {case_record.provider_id}\n"
            f"Service Type: {case_record.service_type}\n"
            f"Documents: {', '.join(doc_titles)}\n\n"
            f"Write a single short paragraph summarizing this case for a quick overview."
        )
        
        try:
            summary = await ollama_client.generate(
                summary_prompt, 
                "You are a medical assistant summarizing prior authorization cases.", 
                None
            )
        except Exception:
            summary = "Summary generation failed."

        # Embed and upsert profile point
        dense_embedding = await embedding_client.embed([summary])
        sparse_embedding = sparse_encoder.encode_sparse([summary])
        
        payload = {
            "doc_type": "case_profile",
            "case_id": str(case_id),
            "member_id": case_record.member_id,
            "provider_id": case_record.provider_id,
            "cpt_code": case_record.cpt_code,
            "icd_code": case_record.icd_code,
            "service_type": case_record.service_type,
            "status": str(case_record.status.value),
            "policy_name": policy_name,
            "summary": summary,
            "document_titles": doc_titles
        }
        
        point = PointStruct(
            id=str(uuid.uuid4()),
            vector={
                "dense": dense_embedding[0],
                "sparse": sparse_embedding[0],
            },
            payload=payload
        )
        
        await qdrant_service.ensure_collection()
        await qdrant_service.upsert_points([point])

intake_agent = IntakeAgent()
