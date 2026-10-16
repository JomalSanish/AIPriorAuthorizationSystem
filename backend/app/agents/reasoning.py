"""
Reasoning Agent (Phase 6 — T050, T051).

Responsibilities:
  T050 — classify_requirement(): LLM-powered per-requirement evidence classification.
          Produces Present / Absent / Unclear verdict with citation and composite
          confidence score (0.4 × retrieval_score + 0.6 × llm_confidence).

  T051 — classify_all_requirements(): Batch loop over all PolicyRequirement rows
          for a case's linked policy; invokes the Retrieval Agent (T045) and
          then classify_requirement for each, returning a full verdict list.

Governance constraints:
  FR-021  — classification labels are exactly {Present, Absent, Unclear}.
  FR-043b — prompts MUST include ONLY the single requirement text and its
             retrieved chunks; never other requirements, other cases, or the
             full case record.
  FR-046c — LLM calls go through the GPU guard (LLM priority).
  Constitution P1 — Reasoning Agent NEVER emits accept / reject.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from app.agents.retrieval import RetrievalResult, retrieval_agent
from app.db.models import PolicyRequirement
from app.services.ollama import ollama_client

logger = logging.getLogger("pa.agents.reasoning")


# ---------------------------------------------------------------------------
# Data classes / enums
# ---------------------------------------------------------------------------

class EvidenceClassification(str, Enum):
    """FR-021: exactly three classification labels."""
    PRESENT = "Present"
    ABSENT  = "Absent"
    UNCLEAR = "Unclear"


@dataclass
class Citation:
    """Source reference for a Present or Unclear verdict."""
    document_id: str
    document_name: str
    page_number: int
    relevant_excerpt: str  # short quoted phrase, never a full page (FR-043b)


@dataclass
class RequirementVerdict:
    """
    Complete classification result for a single policy requirement.

    Composite confidence (FR-021):
        composite = RETRIEVAL_WEIGHT * max(retrieval_scores) + LLM_WEIGHT * llm_confidence

    Both component scores are stored individually for the audit trail.
    """
    requirement_id: str
    requirement_text: str
    classification: EvidenceClassification
    citation: Optional[Citation]
    composite_confidence: float
    retrieval_score: float       # max RRF score from Retrieval Agent
    llm_confidence: float        # self-reported by the LLM (0.0–1.0)
    reasoning_text: str          # brief LLM explanation (audit trail)


# Composite confidence weights (FR-021 — configurable in future via settings)
_RETRIEVAL_WEIGHT = 0.4
_LLM_WEIGHT       = 0.6


# ---------------------------------------------------------------------------
# T050 — classify_requirement
# ---------------------------------------------------------------------------

class ReasoningAgent:
    """
    Reasoning Agent — Phase 6 (T050, T051).

    Classifies retrieved evidence against each policy requirement using a
    local LLM (Ollama llama3.2:3b) with structured JSON output.

    Governance:
        * NEVER emits accept / reject (Constitution P1).
        * Prompt scope is strictly one requirement + its chunks (FR-043b).
        * All LLM calls via the existing OllamaClient (GPU guard, LLM priority).
    """

    async def classify_requirement(
        self,
        policy_requirement: PolicyRequirement,
        retrieved_chunks: List[RetrievalResult],
    ) -> RequirementVerdict:
        """
        Classify evidence for a single policy requirement.

        Steps:
          1. Build a prompt that presents the requirement text and each
             retrieved chunk with its source document + page number.
          2. Call the local LLM with a structured JSON schema that captures
             classification, citation, confidence, and brief reasoning.
          3. Compute composite confidence from retrieval and LLM scores.
          4. Return a RequirementVerdict.

        Args:
            policy_requirement: ORM object with id and requirement_text.
            retrieved_chunks:   Top-k results from Retrieval Agent (T045).

        Returns:
            RequirementVerdict with classification, optional citation, and
            composite confidence.
        """
        req_id   = str(policy_requirement.id)
        req_text = policy_requirement.requirement_text

        logger.info(
            "classify_requirement | req=%s chunks=%d",
            req_id,
            len(retrieved_chunks),
        )

        # --- Build chunk block for prompt (FR-043b: ONLY these chunks) -------
        if retrieved_chunks:
            chunk_lines: List[str] = []
            for i, chunk in enumerate(retrieved_chunks, start=1):
                chunk_lines.append(
                    f"[Chunk {i}]\n"
                    f"Document: {chunk.document_name or chunk.document_id} "
                    f"(page {chunk.page_number})\n"
                    f"Retrieval score: {chunk.score:.4f}\n"
                    f"Text: {chunk.chunk_text[:800]}"   # cap to avoid oversized prompts
                )
            chunks_block = "\n\n".join(chunk_lines)
        else:
            chunks_block = "(No evidence chunks were retrieved for this requirement.)"

        # Max retrieval score (used in composite confidence)
        max_retrieval = max((c.score for c in retrieved_chunks), default=0.0)

        # --- Prompt ----------------------------------------------------------
        system_prompt = (
            "You are a medical evidence evaluator for a prior-authorization system. "
            "Your task is strictly to assess whether provided text evidence satisfies "
            "a stated policy requirement. "
            "Allowed classifications: Present, Absent, Unclear. "
            "Present = clear evidence found. "
            "Absent = no relevant evidence found in the provided chunks. "
            "Unclear = evidence found but it is ambiguous, contradictory, or insufficient. "
            "You MUST NOT make accept or reject decisions — only classify the evidence. "
            "You MUST base your response ONLY on the provided chunks — no outside knowledge."
        )

        prompt = (
            f"Policy Requirement:\n{req_text}\n\n"
            f"Retrieved Evidence Chunks:\n{chunks_block}\n\n"
            "Evaluate whether the evidence satisfies the requirement and return "
            "your assessment as structured JSON. You MUST include a 'reasoning_text' "
            "field explaining your classification."
        )

        format_schema = {
            "type": "object",
            "properties": {
                "classification": {
                    "type": "string",
                    "enum": ["Present", "Absent", "Unclear"],
                    "description": "Evidence classification for this requirement.",
                },
                "citation": {
                    "type": ["object", "null"],
                    "properties": {
                        "document_id":      {"type": "string"},
                        "document_name":    {"type": "string"},
                        "page_number":      {"type": "integer"},
                        "relevant_excerpt": {"type": "string",
                                            "description": "Short quoted phrase (max 200 chars)."},
                    },
                    "required": ["document_id", "document_name", "page_number", "relevant_excerpt"],
                    "description": "Citation for Present or Unclear verdicts; null for Absent.",
                },
                "llm_confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "description": "Self-reported confidence in the classification (0.0–1.0).",
                },
                "reasoning_text": {
                    "type": "string",
                    "description": "Brief explanation of the classification (1-3 sentences).",
                },
            },
            "required": ["classification", "citation", "llm_confidence", "reasoning_text"],
        }

        # --- LLM call --------------------------------------------------------
        try:
            raw = await ollama_client.generate(prompt, system_prompt, format_schema)
            parsed = json.loads(raw)
        except Exception as exc:
            logger.warning(
                "classify_requirement | LLM failed for req=%s (%s). Defaulting to Unclear.",
                req_id, exc,
            )
            # Safe fallback — never silently drop a verdict
            parsed = {
                "classification": "Unclear",
                "citation": None,
                "llm_confidence": 0.0,
                "reasoning_text": f"LLM unavailable during classification: {exc}",
            }

        # --- Parse LLM output ------------------------------------------------
        raw_cls = parsed.get("classification", "Unclear")
        try:
            classification = EvidenceClassification(raw_cls)
        except ValueError:
            logger.warning(
                "classify_requirement | Unexpected classification %r for req=%s, defaulting to Unclear.",
                raw_cls, req_id,
            )
            classification = EvidenceClassification.UNCLEAR

        llm_confidence = float(parsed.get("llm_confidence", 0.0))
        llm_confidence = max(0.0, min(1.0, llm_confidence))   # clamp to [0, 1]

        # Citation — only meaningful for Present / Unclear
        citation: Optional[Citation] = None
        raw_citation = parsed.get("citation")
        if raw_citation and classification != EvidenceClassification.ABSENT:
            # Find matching chunk to resolve document_id / name from the chunk list
            doc_id   = raw_citation.get("document_id", "")
            doc_name = raw_citation.get("document_name", "")
            # If LLM gave a chunk index, resolve to the actual document info
            if not doc_id and retrieved_chunks:
                best = max(retrieved_chunks, key=lambda c: c.score)
                doc_id   = best.document_id
                doc_name = best.document_name

            citation = Citation(
                document_id=doc_id,
                document_name=doc_name,
                page_number=int(raw_citation.get("page_number", 0)),
                relevant_excerpt=str(raw_citation.get("relevant_excerpt", ""))[:200],
            )

        # Composite confidence (FR-021)
        composite = _RETRIEVAL_WEIGHT * max_retrieval + _LLM_WEIGHT * llm_confidence

        reasoning_val = parsed.get("reasoning_text")
        if not reasoning_val or str(reasoning_val).strip() == "":
            reasoning_text = "No reasoning provided by LLM."
        else:
            reasoning_text = str(reasoning_val).strip()

        logger.info(
            "classify_requirement | req=%s classification=%s composite=%.3f "
            "retrieval=%.3f llm=%.3f",
            req_id, classification.value, composite, max_retrieval, llm_confidence,
        )

        return RequirementVerdict(
            requirement_id=req_id,
            requirement_text=req_text,
            classification=classification,
            citation=citation,
            composite_confidence=round(composite, 4),
            retrieval_score=round(max_retrieval, 4),
            llm_confidence=round(llm_confidence, 4),
            reasoning_text=reasoning_text,
        )

    # ---------------------------------------------------------------------------
    # T051 — classify_all_requirements
    # ---------------------------------------------------------------------------

    async def classify_all_requirements(
        self,
        case_id: str,
        policy_requirements: List[PolicyRequirement],
    ) -> List[RequirementVerdict]:
        """
        Classify all policy requirements for a given case.

        For each requirement:
          1. Calls Retrieval Agent (T045) to fetch top-k evidence chunks.
          2. Calls classify_requirement (T050) to produce a verdict.

        If no evidence is retrieved for any requirement, it is classified as
        Absent (spec edge case).

        Args:
            case_id:             UUID string of the case being processed.
            policy_requirements: All PolicyRequirement ORM objects for the case's
                                 linked policy (caller loads them from Postgres).

        Returns:
            List of RequirementVerdict, one per requirement, in the same order
            as the input list.
        """
        logger.info(
            "classify_all_requirements | case=%s requirements=%d",
            case_id,
            len(policy_requirements),
        )

        if not policy_requirements:
            logger.warning("classify_all_requirements | No requirements found for case=%s", case_id)
            return []

        verdicts: List[RequirementVerdict] = []

        for req in policy_requirements:
            # Retrieve evidence chunks for this requirement (T045)
            try:
                chunks = await retrieval_agent.retrieve_evidence(
                    case_id=case_id,
                    policy_requirement=req,
                )
            except Exception as exc:
                logger.error(
                    "classify_all_requirements | Retrieval failed for req=%s case=%s: %s",
                    req.id, case_id, exc,
                )
                chunks = []  # Treat as Absent if retrieval fails

            # Classify this requirement (T050)
            verdict = await self.classify_requirement(
                policy_requirement=req,
                retrieved_chunks=chunks,
            )
            verdicts.append(verdict)

        absent_count  = sum(1 for v in verdicts if v.classification == EvidenceClassification.ABSENT)
        unclear_count = sum(1 for v in verdicts if v.classification == EvidenceClassification.UNCLEAR)
        present_count = sum(1 for v in verdicts if v.classification == EvidenceClassification.PRESENT)

        logger.info(
            "classify_all_requirements | case=%s done — present=%d absent=%d unclear=%d",
            case_id, present_count, absent_count, unclear_count,
        )

        return verdicts


reasoning_agent = ReasoningAgent()
