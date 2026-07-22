from __future__ import annotations

import os
from typing import Any, List, Optional, Literal
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from state.session_state import SessionState


class ChecklistItemModel(BaseModel):
    step_by_step_reasoning: str = Field(
        ...,
        description="A step-by-step clinical auditing evaluation (Chain-of-Thought) analyzing if the evidence text explicitly supports, fails, or remains unclear regarding the guideline requirement. Do not assume or imply unstated details."
    )
    status: Literal["PRESENT", "ABSENT", "UNCLEAR"] = Field(
        ...,
        description="The compliance status of the requirement: PRESENT, ABSENT, or UNCLEAR."
    )
    rationale: str = Field(
        ...,
        description="A short 1-2 sentence summary explaining the status determination."
    )
    citation: Optional[str] = Field(
        None,
        description="Exact quote or phrase from the clinical notes verifying the status, or null if ABSENT."
    )


class GapAgent:
    """Compare patient request against retrieved guidelines using OpenAI, identifying criteria gaps."""

    def run(self, state: SessionState) -> SessionState:
        evidence = state.evidence
        api_key = os.getenv("OPENAI_API_KEY")

        if not evidence:
            state.gap_analysis = {
                "status": "PENDING",
                "reasoning": "No guidelines or evidence matches were retrieved to perform gap analysis.",
                "checklist_items": [],
                "missing_info": ["All clinical policy documentation"]
            }
            state.audit_trail.append("Gap analysis skipped: no evidence segments found.")
            return state

        fallback_key = os.getenv("GEMINI_API_KEY")
        if api_key or fallback_key:
            try:

                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            "You are an expert clinical audit assistant checking prior authorization guidelines compliance.\n"
                            "Evaluate the given prior authorization guideline requirement against the provided clinical notes/evidence.\n\n"
                            "Guideline Requirement to check:\n"
                            "{requirement}\n\n"
                            "Strict Status Definitions to enforce:\n"
                            "- PRESENT: The requirement is explicitly and clearly stated as satisfied or documented within the clinical notes text.\n"
                            "- ABSENT: The requirement is neither mentioned nor implied anywhere in the notes text (e.g. if the note has no mention of conservative physical therapy, it must be ABSENT). Do not make assumptions or infer that it occurred.\n"
                            "- UNCLEAR: A trial or treatment is mentioned, but lacks required specifics (e.g. mentions 'physical therapy' but lacks duration/weeks details), or contradictory information exists.\n\n"
                            "SPECIAL RULES FOR REQUIRED DOCUMENTS:\n"
                            "If the requirement is a required document type (e.g., 'Radiology Report', 'Conservative Therapy Logs', 'Prior Authorization Drug Request Form'), it is only PRESENT if the actual raw report or detailed logs are provided in the clinical notes/evidence segment. If the text merely states that a radiology report or therapy logs were 'reviewed' or 'completed' by the doctor, but the raw document/data itself is not included, you must mark it as ABSENT or UNCLEAR because the physical document is missing from the case files.\n\n"
                            "You must follow a step-by-step reasoning process (Chain-of-Thought) inside the `step_by_step_reasoning` field before selecting the final `status`. If the notes do not mention the prerequisite, you must output ABSENT."
                        ),
                        (
                            "user",
                            "Clinical Evidence Note Segment:\n---\n{evidence_segment}\n---"
                        ),
                    ]
                )

                checklist_items = []
                missing_info = []

                all_criteria = list(state.current_policy_rules) if state.current_policy_rules else []
                if not all_criteria and not state.current_required_docs:
                    all_criteria = [item.get("prerequisite") for item in evidence if item.get("prerequisite")]
                    
                # 1. Evaluate required documents using structural metadata checks (bypassing RAG)
                for req_doc in state.current_required_docs:
                    uploaded_docs = state.patient_data.get("documents", [])
                    matched_doc = next((d for d in uploaded_docs if req_doc.lower() in d.get("document_type", "").lower()), None)

                    if matched_doc:
                        checklist_items.append({
                            "criterion": req_doc,
                            "status": "PRESENT",
                            "rationale": f"Structurally validated document attached: {matched_doc.get('filename')}",
                            "citation": matched_doc.get("filename")
                        })
                    else:
                        checklist_items.append({
                            "criterion": req_doc,
                            "status": "ABSENT",
                            "rationale": "Required document was not attached in the submission files.",
                            "citation": "N/A"
                        })
                        missing_info.append(req_doc)

                # 2. Evaluate clinical prerequisites and unattached documents using semantic RAG evidence and LLM reasoning

                for criterion in all_criteria:
                    ev = next((item for item in evidence if item.get("prerequisite") == criterion), None)
                    evidence_segment = ev.get("text", "") if ev else ""
                    citation_val = ev.get("citation", "Clinical Documents") if ev else "N/A"

                    if not evidence_segment or "no matching statement" in evidence_segment.lower():
                        checklist_items.append({
                            "criterion": criterion,
                            "status": "ABSENT",
                            "rationale": "No matching text segment was found in the clinical notes.",
                            "citation": "N/A"
                        })
                        missing_info.append(criterion)
                        continue

                    from utils.llm_utils import run_chain_with_fallback
                    result: ChecklistItemModel = run_chain_with_fallback(
                        prompt=prompt,
                        inputs={
                            "requirement": criterion,
                            "evidence_segment": evidence_segment
                        },
                        structured_schema=ChecklistItemModel,
                        temperature=0
                    )

                    status_val = result.status.upper()
                    rationale_val = f"Reasoning: {result.step_by_step_reasoning} | Summary: {result.rationale}"
                    
                    if status_val in ("ABSENT", "UNCLEAR"):
                        missing_info.append(criterion)

                    checklist_items.append({
                        "criterion": criterion,
                        "status": status_val,
                        "rationale": rationale_val,
                        "citation": result.citation or citation_val
                    })

                has_absent = any(item["status"] == "ABSENT" for item in checklist_items)
                has_unclear = any(item["status"] == "UNCLEAR" for item in checklist_items)

                if has_absent or has_unclear:
                    overall_status = "PENDING"
                else:
                    overall_status = "APPROVED"

                state.gap_analysis = {
                    "status": overall_status,
                    "reasoning": f"Audit of {len(checklist_items)} checklist criteria completed.",
                    "checklist_items": checklist_items,
                    "missing_info": missing_info
                }

            except Exception as e:
                state.audit_trail.append(f"Gap LLM agent error, running fallback: {str(e)}")
                self._run_fallback(state)
        else:
            state.audit_trail.append("No active LLM API keys found. Running Gap fallback checklist generator.")
            self._run_fallback(state)

        state.audit_trail.append(
            f"Gap analysis completed. Decision: {state.gap_analysis.get('status')}"
        )
        return state

    def _run_fallback(self, state: SessionState) -> None:
        """Compose checklist using basic keyword checks if LLM is unavailable."""
        checklist = []
        missing = []

        for req_doc in state.current_required_docs:
            uploaded_docs = state.patient_data.get("documents", [])
            matched_doc = next((d for d in uploaded_docs if req_doc.lower() in d.get("document_type", "").lower()), None)

            if matched_doc:
                checklist.append({
                    "criterion": req_doc,
                    "status": "PRESENT",
                    "rationale": f"Validated document attached: {matched_doc.get('filename')}",
                    "citation": matched_doc.get("filename")
                })
            else:
                checklist.append({
                    "criterion": req_doc,
                    "status": "ABSENT",
                    "rationale": "Required document was not attached.",
                    "citation": "N/A"
                })
                missing.append(req_doc)

        # Fallback for clinical rules
        for ev in state.evidence:
            prereq = ev.get("prerequisite", "")
            if prereq in state.current_required_docs:
                continue # Already handled above
            matched_text = ev.get("text", "").lower()
            status = "PRESENT"
            rationale = f"Heuristic matched phrase in note quote: '{ev.get('text')}'."

            if "no matching statement" in matched_text or ev.get("score") == 0.0 or not ev.get("text"):
                status = "ABSENT"
                rationale = "No evidence found matching this requirement."
                missing.append(prereq)
            elif " weeks" in prereq:
                if "week" not in matched_text:
                    status = "UNCLEAR"
                    rationale = "Requirement mentions duration, but notes segment does not specify weeks."
                    missing.append(f"Duration details for: {prereq}")
            elif "month" in prereq:
                if "month" not in matched_text and "day" not in matched_text:
                    status = "UNCLEAR"
                    rationale = "Requirement mentions trial duration, but notes segment does not specify months."
                    missing.append(f"Duration details for: {prereq}")

            checklist.append({
                "criterion": prereq,
                "status": status,
                "rationale": rationale,
                "citation": ev.get("citation", "Clinical Documents")
            })

        has_absent = any(item["status"] == "ABSENT" for item in checklist)
        has_unclear = any(item["status"] == "UNCLEAR" for item in checklist)

        if has_absent or has_unclear:
            overall_status = "PENDING"
        else:
            overall_status = "APPROVED"

        state.gap_analysis = {
            "status": overall_status,
            "reasoning": "Heuristic check completed on retrieved evidence segments.",
            "checklist_items": checklist,
            "missing_info": missing
        }
