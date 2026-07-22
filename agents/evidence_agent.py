from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("evidence_agent")
logger.setLevel(logging.INFO)
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from state.session_state import SessionState
from utils.vector_store import load_persistent_policy_store, hybrid_policy_search, ResilientEmbeddings

from pydantic import BaseModel, Field
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from utils.llm_utils import run_chain_with_fallback

class RequirementVerification(BaseModel):
    requirement_name: str = Field(description="The name of the requirement being evaluated")
    status: str = Field(description="MET, NOT_MET, or PARTIAL")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")
    supporting_quote: str = Field(description="Exact excerpt from clinical note proving the match, or empty string")

class BatchVerification(BaseModel):
    evaluations: List[RequirementVerification] = Field(description="List of all evaluated requirements")

BATCH_EVAL_PROMPT = ChatPromptTemplate.from_template("""
You are a Medical Prior Authorization Auditor. Evaluate if the patient case note satisfies the following list of policy requirements.

REQUIREMENTS TO VERIFY:
{requirements_list}

PATIENT CASE NOTE:
"{case_note}"

Determine if each requirement is MET or NOT_MET based ONLY on the case note.
""")


class EvidenceAgent:
    """Retrieve guidelines from mock_policies.json and query clinical notes for evidence."""

    def __init__(self, pdf_path: str | Path | None = None) -> None:
        # Load mock policies from candidate paths
        self.policies_path = Path(__file__).resolve().parents[1] / "data" / "mock_policies.json"
        self.policies = self._load_policies()

    def _load_policies(self) -> list[dict[str, Any]]:
        # Candidate search paths for the policy DB
        candidate_paths = [
            self.policies_path,
            self.policies_path.parent / "sample_requests" / "mock_policies.json",
            self.policies_path.parent / "sample-requests" / "mock_policies.json",
        ]
        
        for db_path in candidate_paths:
            if db_path.exists():
                try:
                    with open(db_path, "r") as f:
                        return json.load(f).get("policies", [])
                except Exception:
                    pass

        
        # In-memory fallback dictionary
        return [
            {
                "cpt_code": "72148",
                "service_name": "Lumbar Spine MRI",
                "specialty_requirement": "Orthopedic Surgery, Neurosurgery, or Neurology referral",
                "required_documents": [
                    "Primary Care Clinical Assessment Notes",
                    "Conservative Physical Therapy Logs"
                ],
                "clinical_prerequisites": [
                    "Lower back pain radiating down the leg or signs of radiculopathy",
                    "Trial of conservative physical therapy for at least 6 weeks",
                    "Trial of conservative drug therapy (NSAIDs or analgesics) for at least 4 weeks"
                ]
            },
            {
                "cpt_code": "96372",
                "service_name": "Specialty Drug - Adalimumab",
                "specialty_requirement": "Rheumatologist or Dermatologist referral",
                "required_documents": [
                    "Prior Authorization Drug Request Form",
                    "Clinical Evaluation Notes"
                ],
                "clinical_prerequisites": [
                    "Diagnosis of moderate-to-severe Rheumatoid Arthritis or Plaque Psoriasis",
                    "Trial and failure of at least 2 conventional DMARDs (e.g. methotrexate, sulfasalazine) for at least 3 months each"
                ]
            },
            {
                "cpt_code": "27447",
                "service_name": "Total Knee Arthroplasty",
                "specialty_requirement": "Orthopedic Surgery referral",
                "required_documents": [
                    "Radiology Report",
                    "Clinical Assessment Notes",
                    "Conservative Therapy Logs"
                ],
                "clinical_prerequisites": [
                    "Diagnosis of advanced osteoarthritis (ICD-10 M17.11)",
                    "Radiology report confirming Kellgren-Lawrence Grade 3 or 4 joint space narrowing",
                    "Standardized joint pain assessment score (e.g. WOMAC or KOOS) confirming severe functional limitation",
                    "Trial of conservative non-surgical management for at least 12 weeks"
                ]
            }
        ]

    def run(self, state: SessionState) -> SessionState:
        cpt_code = str(state.patient_data.get("cpt_code", "")).strip()
        raw_text = str(state.patient_data.get("raw_text", "")).strip()
        api_key = os.getenv("OPENAI_API_KEY")

        # Load the persistent policy store and perform search
        store = load_persistent_policy_store()
        retrieved_passages: list[dict[str, Any]] = []

        query_text = (
            state.classification.get("requested_service")
            or state.patient_data.get("requested_service")
            or cpt_code
            or (raw_text[:300] if raw_text else "")
        )

        if store and query_text:
            faiss_db, bm25_retriever = store
            search_results = hybrid_policy_search(
                query=query_text,
                faiss_db=faiss_db,
                bm25_retriever=bm25_retriever,
                cpt_code=cpt_code if cpt_code else None,
                k=3
            )
            for doc, score in search_results:
                logger.info(f"[RAG SEARCH] Retrieved guideline passage | Source: {doc.metadata.get('source')} | Page: {doc.metadata.get('page')} | Score: {score}")
                logger.debug(f"[RAG SEARCH CONTENT] Content: {doc.page_content[:200]}...")
                retrieved_passages.append({
                    "text": doc.page_content,
                    "source": doc.metadata.get("source", "unknown"),
                    "page": doc.metadata.get("page", 0),
                    "score": round(float(score), 4)
                })

        state.retrieved_policy_passages = retrieved_passages

        # Find policy by CPT
        policy = next((p for p in self.policies if p["cpt_code"] == cpt_code), None)

        # Semantic CPT fallback: resolve CPT mapping using persistent index search
        if not policy and retrieved_passages:
            top_source = str(retrieved_passages[0]["source"]).lower()
            top_text = str(retrieved_passages[0]["text"]).lower()

            if "adalimumab" in top_source or "adalimumab" in top_text:
                policy = next((p for p in self.policies if p["cpt_code"] == "96372"), None)
            elif "knee" in top_text or "arthroplasty" in top_text:
                policy = next((p for p in self.policies if p["cpt_code"] == "27447"), None)
            elif "mri" in top_text or "lumbar" in top_text or "spine" in top_text:
                policy = next((p for p in self.policies if p["cpt_code"] == "72148"), None)
            elif "bypass" in top_text or "bariatric" in top_text:
                policy = next((p for p in self.policies if p["cpt_code"] == "43644"), None)
            elif "somnography" in top_text or "sleep" in top_text:
                policy = next((p for p in self.policies if p["cpt_code"] == "95810"), None)
            elif "glucose" in top_text or "cgm" in top_text:
                policy = next((p for p in self.policies if p["cpt_code"] == "E2103"), None)
            elif "migraine" in top_text or "botox" in top_text:
                policy = next((p for p in self.policies if p["cpt_code"] == "64615"), None)

            if policy:
                state.patient_data["cpt_code"] = policy["cpt_code"]
                state.audit_trail.append(
                    f"Resolved policy CPT {policy['cpt_code']} ('{policy['service_name']}') semantically from persistent index matches"
                )

        if not policy:
            state.audit_trail.append(f"No mock policy found for CPT code: {cpt_code}")
            state.evidence = []
            state.current_policy_rules = []
            state.current_required_docs = []
            return state

        prerequisites = policy.get("clinical_prerequisites", [])
        required_docs = policy.get("required_documents", [])

        # Assign resolved policy guidelines dynamically to the state
        state.current_policy_rules = prerequisites
        state.current_required_docs = required_docs

        all_criteria = prerequisites + required_docs
        evidence_results: list[dict[str, Any]] = []

        # Retrieve clinical evidence using LLM-based structured requirement verification
        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        has_keys = bool(openai_key or gemini_key)

        if raw_text:
            resolved_criteria = {}
            if has_keys:
                try:
                    req_string = "\n".join([f"- {req}" for req in all_criteria])
                    logger.info(f"[LLM BATCH EVALUATOR] Verifying all {len(all_criteria)} requirements against patient note.")
                    batch_res = run_chain_with_fallback(
                        prompt=BATCH_EVAL_PROMPT,
                        inputs={"requirements_list": req_string, "case_note": raw_text},
                        structured_schema=BatchVerification,
                        temperature=0.0
                    )
                    
                    evals_map = {e.requirement_name.strip().lower(): e for e in batch_res.evaluations}
                    
                    for item in all_criteria:
                        item_clean = item.strip().lower()
                        verification = evals_map.get(item_clean)
                        if not verification:
                            # Substring fallback matching
                            for k, v in evals_map.items():
                                if k in item_clean or item_clean in k:
                                    verification = v
                                    break
                                    
                        if verification:
                            if verification.status == "MET":
                                logger.info(f"[EVIDENCE MATCH - LLM BATCH] matched requirement '{item}' | Confidence: {verification.confidence}")
                                logger.debug(f"[EVIDENCE MATCH - LLM CONTENT] quote: '{verification.supporting_quote}'")
                                evidence_results.append({
                                    "prerequisite": item,
                                    "text": verification.supporting_quote or "Requirement met in clinical notes.",
                                    "citation": "Clinical Notes (LLM Evaluation)",
                                    "score": round(float(verification.confidence), 3)
                                })
                                resolved_criteria[item] = True
                            elif verification.status == "PARTIAL":
                                logger.info(f"[EVIDENCE MATCH - LLM BATCH] partially matched requirement '{item}' | Confidence: {verification.confidence}")
                                logger.debug(f"[EVIDENCE MATCH - LLM CONTENT] quote: '{verification.supporting_quote}'")
                                evidence_results.append({
                                    "prerequisite": item,
                                    "text": verification.supporting_quote or "Requirement partially met in clinical notes.",
                                    "citation": "Clinical Notes (LLM Evaluation)",
                                    "score": round(float(verification.confidence), 3)
                                })
                                resolved_criteria[item] = True
                            else: # NOT_MET
                                logger.info(f"[EVIDENCE MATCH - LLM BATCH] failed to match requirement '{item}'")
                                evidence_results.append({
                                    "prerequisite": item,
                                    "text": "No matching statement or attached document found in clinical documentation.",
                                    "citation": "N/A",
                                    "score": 0.0
                                })
                                resolved_criteria[item] = True
                except Exception as e:
                    logger.warning(f"LLM batch requirement verification failed: {e}. Using keyword matching fallback.")

            # Fallback to keyword matching for unresolved requirements
            for item in all_criteria:
                if not resolved_criteria.get(item):
                    kw_results = self._run_keyword_fallback(raw_text, [item])
                    if kw_results:
                        evidence_results.append(kw_results[0])
                    else:
                        evidence_results.append({
                            "prerequisite": item,
                            "text": "No matching statement or attached document found in clinical documentation.",
                            "citation": "N/A",
                            "score": 0.0
                        })
            state.audit_trail.append(f"Evidence retrieved from patient notes using Semantic LLM batch evaluation for policy: {policy['service_name']}")
        else:
            state.audit_trail.append("Empty clinical notes. No clinical evidence matched.")
            for item in all_criteria:
                evidence_results.append({
                    "prerequisite": item,
                    "text": "No matching statement or attached document found in clinical documentation.",
                    "citation": "N/A",
                    "score": 0.0
                })

        state.evidence = evidence_results
        state.audit_trail.append(f"Matched {len(evidence_results)} evidence passages against policy criteria using LLM Evaluator.")
        return state

    def _run_keyword_fallback(self, raw_text: str, prerequisites: list[str]) -> list[dict[str, Any]]:
        """Fallback keyword search scoring lines of notes text against prerequisite descriptions."""
        import re
        def clean_and_split(t: str) -> set[str]:
            cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', t.lower())
            return set(cleaned.split())

        sentences = [s.strip() for s in raw_text.split(".") if len(s.strip()) > 8]
        evidence_results: list[dict[str, Any]] = []

        for prereq in prerequisites:
            prereq_words = clean_and_split(prereq)
            best_match = ""
            best_score = 0.0

            # Only match based on actual textual overlap for clinical prerequisites. 
            # We don't automatically assume a document is attached just because a keyword is mentioned.
            for sent in sentences:
                sent_words = clean_and_split(sent)
                overlap = len(prereq_words.intersection(sent_words))
                if overlap > 0:
                    score = overlap / len(prereq_words)
                    if score > best_score:
                        best_score = score
                        best_match = sent

            if best_match and best_score > 0.15:
                logger.info(f"[EVIDENCE MATCH - KEYWORD] matched prerequisite '{prereq}' | Score: {best_score}")
                logger.debug(f"[EVIDENCE MATCH - KEYWORD CONTENT] text sentence: '{best_match}'")
                evidence_results.append({
                    "prerequisite": prereq,
                    "text": best_match,
                    "citation": "Clinical Documents (Keyword Match)",
                    "score": round(best_score, 3)
                })
            else:
                logger.info(f"[EVIDENCE MATCH - KEYWORD] failed to match prerequisite '{prereq}'")
                evidence_results.append({
                    "prerequisite": prereq,
                    "text": "No matching statement or attached document found in clinical documentation.",
                    "citation": "N/A",
                    "score": 0.0
                })

        return evidence_results

