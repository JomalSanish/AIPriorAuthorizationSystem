"""
Summary Agent (Phase 6 — T052).

Responsibility:
  generate_summary(): Takes a complete list of RequirementVerdict objects produced
  by the Reasoning Agent and uses the local LLM (llama3.2:3b) to generate:
    1. A structured nurse-facing evidence summary — per-requirement status
       with citation reference.
    2. A gap checklist — Absent and Unclear items in separate sections
       (FR-022) with different visual indicators.
    3. Optional warning flags (turn-budget exhaustion, document extraction
       failure, partial analysis).

Governance constraints:
  FR-022  — gap checklist must distinguish Absent from Unclear items.
  FR-043b — summary text composed ONLY from the verdict list and short
             cited excerpts; never from full source documents or pages verbatim.
  Constitution P4 — summary is grounded strictly in verdicts already
                    produced; no new clinical claims.
  Constitution P1 — Summary Agent NEVER emits accept / reject.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.agents.reasoning import EvidenceClassification, RequirementVerdict
from app.services.ollama import ollama_client

logger = logging.getLogger("pa.agents.summary")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class GapItem:
    """
    A single entry in the gap checklist (Absent or Unclear requirement).

    FR-022: Unclear items include the ambiguous citation so the Nurse can
    evaluate the source directly.
    """
    requirement_id: str
    requirement_text: str
    classification: str        # "Absent" | "Unclear"
    citation: Optional[Dict[str, Any]]   # serialised Citation for Unclear; None for Absent
    confidence: float


@dataclass
class CaseSummary:
    """
    Nurse-facing case summary produced by the Summary Agent.

    summary_text:   Full prose summary of evidence coverage per requirement.
    gap_checklist:  Structured list of Absent and Unclear requirements.
    flags:          Warning strings (pipeline incomplete, extraction failure, etc.)
    """
    summary_text: str
    gap_checklist: List[GapItem] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


# Known flag keys (used by Workflow Agent in Phase 7)
FLAG_PARTIAL_ANALYSIS    = "Pipeline incomplete — partial analysis"
FLAG_NO_EXTRACTABLE_CONTENT = "No extractable content — document extraction failed for all files"


# ---------------------------------------------------------------------------
# T052 — Summary Agent
# ---------------------------------------------------------------------------

class SummaryAgent:
    """
    Summary Agent — Phase 6 (T052).

    Consumes the full RequirementVerdict list from the Reasoning Agent and
    produces a CaseSummary for the Nurse Review UI.

    Governance:
        * Grounded strictly in the verdicts and short cited excerpts
          (Constitution P4, FR-043b).
        * NEVER emits accept / reject (Constitution P1).
        * Calls local Ollama LLM via OllamaClient (GPU guard, LLM priority).
    """

    async def generate_summary(
        self,
        case_id: str,
        verdicts: List[RequirementVerdict],
        *,
        partial: bool = False,
        all_documents_failed: bool = False,
    ) -> CaseSummary:
        """
        Generate a nurse-facing evidence summary and gap checklist.

        Args:
            case_id:               Case UUID string (used for logging).
            verdicts:              Full RequirementVerdict list from Reasoning Agent.
            partial:               True if the pipeline hit the turn budget before
                                   all requirements were processed (FR-016).
            all_documents_failed:  True if all case documents had OCR/extraction
                                   failure (FR-013a).

        Returns:
            CaseSummary with summary_text, gap_checklist, and flags.
        """
        logger.info(
            "generate_summary | case=%s verdicts=%d partial=%s all_failed=%s",
            case_id, len(verdicts), partial, all_documents_failed,
        )

        flags: List[str] = []
        if partial:
            flags.append(FLAG_PARTIAL_ANALYSIS)
        if all_documents_failed:
            flags.append(FLAG_NO_EXTRACTABLE_CONTENT)

        # --- Build gap checklist (deterministic — no LLM needed) -------------
        gap_checklist: List[GapItem] = []
        for v in verdicts:
            if v.classification in (EvidenceClassification.ABSENT, EvidenceClassification.UNCLEAR):
                citation_dict: Optional[Dict[str, Any]] = None
                if v.citation and v.classification == EvidenceClassification.UNCLEAR:
                    citation_dict = {
                        "document_id":      v.citation.document_id,
                        "document_name":    v.citation.document_name,
                        "page_number":      v.citation.page_number,
                        "relevant_excerpt": v.citation.relevant_excerpt,
                    }
                gap_checklist.append(GapItem(
                    requirement_id=v.requirement_id,
                    requirement_text=v.requirement_text,
                    classification=v.classification.value,
                    citation=citation_dict,
                    confidence=v.composite_confidence,
                ))

        # --- Build compact verdict block for LLM prompt (FR-043b) ------------
        verdict_lines: List[str] = []
        for v in verdicts:
            citation_str = "—"
            if v.citation:
                citation_str = (
                    f"{v.citation.document_name} p.{v.citation.page_number}: "
                    f"\"{v.citation.relevant_excerpt[:120]}\""
                )
            verdict_lines.append(
                f"- [{v.classification.value}] {v.requirement_text}\n"
                f"  Citation: {citation_str}\n"
                f"  Confidence: {v.composite_confidence:.2f}"
            )
        verdicts_block = "\n".join(verdict_lines) if verdict_lines else "(No verdicts available)"

        flags_block = ""
        if flags:
            flags_block = "\n\nWarning flags: " + "; ".join(flags)

        # --- LLM prompt for summary text -------------------------------------
        system_prompt = (
            "You are a clinical case summariser for a medical prior-authorization system. "
            "Your task is to write a clear, factual evidence summary for a nurse reviewer. "
            "Base your summary STRICTLY on the provided requirement verdicts and their "
            "short cited excerpts — do NOT reproduce full document pages, invent findings, "
            "or make clinical judgements beyond what is stated in the verdicts. "
            "Do NOT recommend accept or reject — that decision belongs to the Nurse. "
            "Use plain medical language suitable for a nurse reviewer."
        )

        prompt = (
            f"Prior-authorization case evidence summary\n"
            f"Case ID: {case_id}\n\n"
            f"Requirement Verdicts:\n{verdicts_block}"
            f"{flags_block}\n\n"
            "Write a structured prose summary covering:\n"
            "1. An overview sentence describing overall evidence coverage.\n"
            "2. For each requirement: its classification and citation (if any).\n"
            "3. A brief note on any gaps (Absent or Unclear items) the Nurse should check.\n"
            "Return ONLY the JSON object below."
        )

        format_schema = {
            "type": "object",
            "properties": {
                "summary_text": {
                    "type": "string",
                    "description": (
                        "Structured prose evidence summary for the nurse reviewer. "
                        "Must be grounded only in the provided verdicts."
                    ),
                },
            },
            "required": ["summary_text"],
        }

        # --- LLM call --------------------------------------------------------
        try:
            raw = await ollama_client.generate(prompt, system_prompt, format_schema)
            parsed = json.loads(raw)
            summary_text = str(parsed.get("summary_text", "")).strip()
            if not summary_text:
                raise ValueError("Empty summary_text from LLM")
        except Exception as exc:
            logger.warning(
                "generate_summary | LLM failed for case=%s (%s). Using fallback summary.",
                case_id, exc,
            )
            # Deterministic fallback — build a minimal summary from verdicts
            summary_text = self._fallback_summary(verdicts, flags)

        logger.info(
            "generate_summary | case=%s summary_len=%d gaps=%d flags=%d",
            case_id, len(summary_text), len(gap_checklist), len(flags),
        )

        return CaseSummary(
            summary_text=summary_text,
            gap_checklist=gap_checklist,
            flags=flags,
        )

    # ---------------------------------------------------------------------------
    # Fallback — deterministic summary when LLM is unavailable
    # ---------------------------------------------------------------------------

    def _fallback_summary(
        self,
        verdicts: List[RequirementVerdict],
        flags: List[str],
    ) -> str:
        """
        Build a minimal but complete summary without an LLM call.
        Used when Ollama is unavailable during summary generation.
        Satisfies FR-043b (no new claims — only verdict data).
        """
        if not verdicts:
            return "No evidence verdicts available for this case."

        present  = [v for v in verdicts if v.classification == EvidenceClassification.PRESENT]
        absent   = [v for v in verdicts if v.classification == EvidenceClassification.ABSENT]
        unclear  = [v for v in verdicts if v.classification == EvidenceClassification.UNCLEAR]

        lines: List[str] = [
            f"Evidence coverage: {len(present)} Present, "
            f"{len(absent)} Absent, {len(unclear)} Unclear "
            f"(out of {len(verdicts)} requirements).",
            "",
        ]

        for v in verdicts:
            citation_str = ""
            if v.citation:
                citation_str = (
                    f" — see {v.citation.document_name} p.{v.citation.page_number}"
                    f": \"{v.citation.relevant_excerpt[:100]}\""
                )
            lines.append(
                f"• [{v.classification.value}] {v.requirement_text}{citation_str} "
                f"(confidence {v.composite_confidence:.2f})"
            )

        if flags:
            lines.append("")
            lines.append("Warnings: " + "; ".join(flags))

        return "\n".join(lines)


summary_agent = SummaryAgent()
