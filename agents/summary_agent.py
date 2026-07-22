from __future__ import annotations

import logging
import os
from pydantic import BaseModel, Field

logger = logging.getLogger("summary_agent")
logger.setLevel(logging.INFO)
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from state.session_state import SessionState


class SummaryExtraction(BaseModel):
    summary: str = Field(
        ..., description="Clinical case summary brief formatted in clean Markdown."
    )
    communication_draft: str = Field(
        ...,
        description="Formal, neutral communication letter draft (either approval, request for information, or denial notification).",
    )


class SummaryAgent:
    """Generate case summary briefs and provider-facing communication letters using OpenAI, with robust fallbacks."""

    def run(self, state: SessionState) -> SessionState:
        gap_status = str(state.gap_analysis.get("status", "PENDING"))
        missing_info = state.gap_analysis.get("missing_info", [])
        api_key = os.getenv("OPENAI_API_KEY")

        # Map overall status
        if gap_status == "APPROVED":
            state.review_status = "APPROVED"
        elif gap_status == "REJECTED":
            state.review_status = "REJECTED"
        else:
            state.review_status = "REQUEST MORE INFO"

        fallback_key = os.getenv("GEMINI_API_KEY")
        if api_key or fallback_key:
            try:
                from utils.llm_utils import run_chain_with_fallback

                # Format prompts containing case data
                case_details = (
                    f"Member ID: {state.patient_data.get('member_id', 'UNKNOWN')}\n"
                    f"Provider ID: {state.patient_data.get('provider_id', 'UNKNOWN')}\n"
                    f"CPT Code: {state.patient_data.get('cpt_code', 'UNKNOWN')}\n"
                    f"Service Type: {state.classification.get('type', 'UNKNOWN')} ({state.classification.get('urgency', 'UNKNOWN')})\n"
                    f"Status of Gap Analysis: {gap_status}\n"
                    f"Missing Criteria: {', '.join(missing_info) if missing_info else 'None'}\n"
                    f"Clinical Notes:\n{state.patient_data.get('raw_text', '')}\n\n"
                    f"Retrieved Evidence:\n"
                    + "\n".join(f"- {e.get('text', '')}" for e in state.evidence)
                )

                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            "You are a prior authorization coordinator. Create a concise medical summary brief for a clinical reviewer "
                            "and a formal, neutral, provider-facing letter based on the case facts. "
                            "CRITICAL: You MUST use the exact Member ID, Provider ID, CPT Code, and Service Type provided in the details. "
                            "Do NOT hallucinate, change, or invent identifiers (like using M98765 or 27447 if the details specify other values). "
                            "Formatting guidelines:\n"
                            "1. Summary brief MUST use clean Markdown sections (Case Summary, Evidence Map, Gaps & Checklist).\n"
                            "2. The provider letter draft MUST explain the review status (Approval, Request for More Information, or Denial). "
                            "If the status is REQUEST MORE INFO, list the missing details clearly in a bulleted list.",
                        ),
                        ("user", "Draft case outputs for the following data:\n\n{details}"),
                    ]
                )

                result: SummaryExtraction = run_chain_with_fallback(
                    prompt=prompt,
                    inputs={"details": case_details},
                    structured_schema=SummaryExtraction,
                    temperature=0.2
                )

                logger.info("[SUMMARY AGENT] Generated Case Summary Brief successfully.")
                logger.debug(f"[SUMMARY AGENT BRIEF]\n{result.summary}")
                logger.info("[SUMMARY AGENT] Generated Correspondence Letter successfully.")
                logger.debug(f"[SUMMARY AGENT LETTER DRAFT]\n{result.communication_draft}")

                state.artifacts = {
                    "summary": result.summary,
                    "communication_draft": result.communication_draft,
                }

            except Exception as e:
                state.audit_trail.append(f"Summary LLM agent error, running fallback: {str(e)}")
                self._run_fallback(state, gap_status, missing_info)
        else:
            state.audit_trail.append("No active LLM API keys found. Running Summary fallback templates.")
            self._run_fallback(state, gap_status, missing_info)

        state.audit_trail.append("Case summary and communication draft generation complete.")
        return state

    def _run_fallback(self, state: SessionState, gap_status: str, missing_info: list[str]) -> None:
        """Compose fallback markdown text if LLM is unavailable."""
        member = state.patient_data.get("member_id", "UNKNOWN")
        provider = state.patient_data.get("provider_id", "UNKNOWN")
        cpt = state.patient_data.get("cpt_code", "UNKNOWN")
        service = state.classification.get("type", "UNKNOWN")
        urgency = state.classification.get("urgency", "UNKNOWN")

        # 1. Summary
        summary = (
            f"## Clinical Case Summary\n\n"
            f"**Member ID:** {member} | **Provider ID:** {provider}\n"
            f"**Requested Service:** {service} (CPT: {cpt})\n"
            f"**Urgency:** {urgency}\n"
            f"**Triage Queue Status:** {state.review_status}\n\n"
            f"### Audit Comparison Findings\n"
            f"- Clinical notes show acute indicators.\n"
        )
        if missing_info:
            summary += "\n### Identified Criteria Gaps\n"
            for item in missing_info:
                summary += f"- ⚠️ **Missing:** {item}\n"
        else:
            summary += "\n✅ All standard criteria mapped successfully.\n"

        # 2. Letter
        if state.review_status == "APPROVED":
            letter = (
                f"Date: 2026-07-08\n\n"
                f"To: Provider {provider}\n"
                f"Re: Prior Authorization Approval for Member {member}\n\n"
                f"Dear Provider,\n\n"
                f"We are pleased to inform you that the prior authorization request for procedure CPT {cpt} has been APPROVED.\n"
                f"The clinical documentation meets all coverage guidelines for {service}.\n\n"
                f"Sincerely,\n"
                f"Prior Authorization Operations Team"
            )
        elif state.review_status == "REQUEST MORE INFO":
            items_list = "".join(f"- {item}\n" for item in missing_info)
            letter = (
                f"Date: 2026-07-08\n\n"
                f"To: Provider {provider}\n"
                f"Re: Request for Information for Prior Authorization (Member {member})\n\n"
                f"Dear Provider,\n\n"
                f"We have received your prior authorization request for procedure CPT {cpt}. "
                f"To complete our review, please submit the following additional clinical information:\n\n"
                f"{items_list}\n"
                f"Please submit these documents within 14 business days.\n\n"
                f"Sincerely,\n"
                f"Prior Authorization Operations Team"
            )
        else:
            letter = (
                f"Date: 2026-07-08\n\n"
                f"To: Provider {provider}\n"
                f"Re: Prior Authorization Denial for Member {member}\n\n"
                f"Dear Provider,\n\n"
                f"We regret to inform you that the prior authorization request for CPT {cpt} has been DENIED.\n"
                f"The clinical notes submitted do not satisfy the medical necessity criteria for {service}.\n\n"
                f"Sincerely,\n"
                f"Prior Authorization Operations Team"
            )

        logger.info("[SUMMARY AGENT] Generated fallback Case Summary Brief successfully.")
        logger.debug(f"[SUMMARY AGENT FALLBACK BRIEF]\n{summary}")
        logger.info("[SUMMARY AGENT] Generated fallback Correspondence Letter successfully.")
        logger.debug(f"[SUMMARY AGENT FALLBACK LETTER DRAFT]\n{letter}")

        state.artifacts = {
            "summary": summary,
            "communication_draft": letter,
        }
