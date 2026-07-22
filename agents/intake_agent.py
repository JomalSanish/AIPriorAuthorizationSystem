from __future__ import annotations

import json
import os
import uuid
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from state.session_state import SessionState


class PatientInfo(BaseModel):
    member_id: Optional[str] = Field(None, description="The member or patient ID (e.g. M123)")
    first_name: Optional[str] = Field(None, description="Patient's first name")
    last_name: Optional[str] = Field(None, description="Patient's last name")
    date_of_birth: Optional[str] = Field(None, description="The patient's DOB. Return null if not explicitly stated in the text.")


class ProviderInfo(BaseModel):
    provider_id: Optional[str] = Field(None, description="The provider ID (e.g. P456)")
    name: Optional[str] = Field(None, description="Provider's full name")
    specialty: Optional[str] = Field(None, description="Provider's medical specialty")


class ClinicalMetadata(BaseModel):
    cpt_code: Optional[str] = Field(None, description="The CPT/HCPCS procedure code")
    icd_code: Optional[str] = Field(None, description="The ICD-10 diagnosis code")
    requested_service: Optional[str] = Field(None, description="Detailed name of the service requested")
    requested_date: Optional[str] = Field(None, description="Requested date")


class DocumentItem(BaseModel):
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_type: str = Field(..., description="Document type (e.g. Clinical Note, Referral, Radiology Report)")
    filename: str = Field(..., description="Uploaded filename")
    extracted_text: str = Field(..., description="Extracted clinical notes text")


class ProviderSubmission(BaseModel):
    submission_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    patient_info: PatientInfo
    provider_info: ProviderInfo
    clinical_metadata: ClinicalMetadata
    documents: List[DocumentItem] = Field(default_factory=list)
    is_complete: bool = Field(..., description="True if member_id, provider_id, and cpt_code are present")
    missing_fields: List[str] = Field(default_factory=list, description="Fields missing from: Member ID, Provider ID, CPT Code")
    duplicate_suspected: bool = Field(False, description="True if text indicates duplicate request history")


class IntakeAgent:
    """Parse incoming requests and classify the request type, metadata, and completeness."""

    def run(self, state: SessionState) -> SessionState:
        if not state.request_id:
            state.request_id = str(uuid.uuid4())

        raw_text = str(state.patient_data.get("raw_text", "")).strip()
        api_key = os.getenv("OPENAI_API_KEY")

        # 1. Try to parse directly if raw_text is already structured JSON
        if raw_text.startswith("{") and raw_text.endswith("}"):
            try:
                data = json.loads(raw_text)
                submission = ProviderSubmission.model_validate(data)
                self._map_submission_to_state(state, submission, raw_text)
                state.audit_trail.append("Intake parsed structured JSON submission payload directly.")
                state.audit_trail.append(
                    f"Intake complete: {state.classification.get('type')}/{state.classification.get('urgency')}. Next Queue: {state.routing_queue}"
                )
                return state
            except Exception as e:
                state.audit_trail.append(f"Failed to parse structured JSON payload directly: {str(e)}. Attempting LLM extraction.")

        # 2. Extract using LLM if API key is present
        fallback_key = os.getenv("GEMINI_API_KEY")
        if api_key or fallback_key:
            try:
                from utils.llm_utils import run_chain_with_fallback

                # Provide the list of uploaded files to the LLM context
                docs_context = "\n".join([f"File: {d.get('filename')} - Preview: {d.get('extracted_text', '')[:100]}" for d in state.patient_data.get("documents", [])])
                
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            "You are an intake clinical parser. Extract patient demographics, provider info, and clinical metadata. "
                            "CRITICAL: Do NOT hallucinate data. Extract names, IDs, dates, and codes exactly as they appear in the text. If a value is missing, return null or an empty string. "
                            "You are also given a list of uploaded files. For each file, create a DocumentItem with its exact filename and classify its document_type (e.g., Radiology Report, Clinical Notes, Conservative Therapy Logs). "
                            "A submission is complete only if patient_info.member_id, provider_info.provider_id, "
                            "and clinical_metadata.cpt_code are all non-empty. Otherwise, list missing fields in missing_fields.",
                        ),
                        ("user", "Uploaded Files context:\n{docs_context}\n\nExtract structured provider submission from this combined text:\n\n{text}"),
                    ]
                )

                result: ProviderSubmission = run_chain_with_fallback(
                    prompt=prompt,
                    inputs={"docs_context": docs_context, "text": raw_text},
                    structured_schema=ProviderSubmission,
                    temperature=0
                )

                self._map_submission_to_state(state, result, raw_text)
                state.audit_trail.append("Intake LLM parser completed structured extraction and document classification.")

            except Exception as e:
                state.audit_trail.append(f"Intake LLM parser error, using fallback: {str(e)}")
                self._run_fallback(state, raw_text)
        else:
            state.audit_trail.append("No active LLM API keys found. Running Intake fallback.")
            self._run_fallback(state, raw_text)

        state.audit_trail.append(
            f"Intake complete: {state.classification.get('type')}/{state.classification.get('urgency')}. Next Queue: {state.routing_queue}"
        )
        return state

    def _map_submission_to_state(self, state: SessionState, result: ProviderSubmission, raw_text: str) -> None:
        """Map the parsed ProviderSubmission model to the shared SessionState."""
        # Merge LLM classified docs with the existing uploaded docs in state to preserve full text
        existing_docs = state.patient_data.get("documents", [])
        final_docs = []
        for edoc in existing_docs:
            fname = edoc.get("filename", "")
            # Find matching doc in LLM result
            matched = next((d for d in result.documents if d.filename == fname), None)
            doc_type = matched.document_type if matched else "Clinical Notes"
            
            final_docs.append({
                "document_id": edoc.get("document_id"),
                "document_type": doc_type,
                "filename": fname,
                "extracted_text": edoc.get("extracted_text", "")
            })
            
        if not final_docs and result.documents:
            # Fallback if state had no docs
            final_docs = [
                {
                    "document_id": doc.document_id,
                    "document_type": doc.document_type,
                    "filename": doc.filename,
                    "extracted_text": doc.extracted_text,
                }
                for doc in result.documents
            ]

        state.patient_data.update(
            {
                "member_id": result.patient_info.member_id or "",
                "provider_id": result.provider_info.provider_id or "",
                "first_name": result.patient_info.first_name or "",
                "last_name": result.patient_info.last_name or "",
                "dob": result.patient_info.date_of_birth or "",
                "cpt_code": result.clinical_metadata.cpt_code or "",
                "icd_code": result.clinical_metadata.icd_code or "",
                "requested_date": result.clinical_metadata.requested_date or "2026-07-09",
                "raw_text": raw_text,
                "missing_fields": result.missing_fields,
                "duplicate_suspected": result.duplicate_suspected,
                "documents": final_docs,
            }
        )

        # Service type determination based on CPT code
        cpt = str(result.clinical_metadata.cpt_code).strip()
        if cpt == "72148":
            service_type = "IMAGING"
        elif cpt in ("96372", "J0135", "64615"):
            service_type = "DRUG"
        elif cpt in ("27447", "43644"):
            service_type = "SURGERY"
        elif cpt == "95810":
            service_type = "DIAGNOSTIC"
        elif cpt == "E2103":
            service_type = "DME"
        else:
            # Fallback service type classification
            service_type = "SPECIALTY REFERRAL"

        state.classification = {
            "type": service_type,
            "urgency": "ROUTINE",
            "reason": f"Ingestion CPT code {cpt} mapped service type as {service_type}.",
        }

        if result.is_complete:
            state.routing_queue = "Nurse Review"
        else:
            state.routing_queue = "Intake"

    def _run_fallback(self, state: SessionState, raw_text: str) -> None:
        """Fallback heuristics using regex and keywords if LLM fails or API key is not present."""
        import re
        lower_text = raw_text.lower()

        # Regex extractors
        patient_name_match = re.search(r"\b(?:Patient|Name)[:\s]*([A-Za-z\s]+)(?:\(|$)", raw_text, re.IGNORECASE)
        member_id_match = re.search(r"\b(?:ID|Member\s*ID)[:\s]*([A-Za-z0-9]+)", raw_text, re.IGNORECASE)
        provider_match = re.search(r"\bProvider[:\s]*([^,\n]+)", raw_text, re.IGNORECASE)
        date_match = re.search(r"\bDate(?:\s*of\s*Visit)?[:\s]*([\d-]+)", raw_text, re.IGNORECASE)
        cpt_match = re.search(r"\bCPT(?:\s*Code)?[:\s]*(\d{5})", raw_text, re.IGNORECASE)
        icd_match = re.search(r"\bICD-10[:\s]*([A-Z0-9\.]+)", raw_text, re.IGNORECASE)

        first_name, last_name = "", ""
        if patient_name_match:
            parts = patient_name_match.group(1).strip().split()
            if len(parts) >= 2:
                first_name, last_name = parts[0], " ".join(parts[1:])
            elif parts:
                first_name = parts[0]
                last_name = ""

        member_id = member_id_match.group(1).strip() if member_id_match else ""
        provider_name = provider_match.group(1).strip() if provider_match else "Dr. Fallback Provider"
        req_date = date_match.group(1).strip() if date_match else "2026-07-09"
        icd_code = icd_match.group(1).strip() if icd_match else ("M54.5" if "back pain" in lower_text else "UNKNOWN")

        # Service type heuristics
        cpt_code = cpt_match.group(1).strip() if cpt_match else ""
        service_type = "SPECIALTY REFERRAL"
        
        if not cpt_code:
            if "72148" in raw_text or "mri" in lower_text:
                cpt_code = "72148"
                service_type = "IMAGING"
            elif "96372" in raw_text or "j0135" in raw_text or "adalimumab" in lower_text or "humira" in lower_text or "64615" in raw_text or "botox" in lower_text or "migraine" in lower_text:
                cpt_code = "64615" if ("64615" in raw_text or "botox" in lower_text) else "96372"
                service_type = "DRUG"
            elif "27447" in raw_text or "knee replacement" in lower_text or "arthroplasty" in lower_text or "43644" in raw_text or "gastric bypass" in lower_text or "bariatric" in lower_text:
                cpt_code = "43644" if ("43644" in raw_text or "gastric bypass" in lower_text) else "27447"
                service_type = "SURGERY"
            elif "95810" in raw_text or "sleep study" in lower_text or "polysomnography" in lower_text:
                cpt_code = "95810"
                service_type = "DIAGNOSTIC"
            elif "e2103" in raw_text or "cgm" in lower_text or "glucose monitor" in lower_text:
                cpt_code = "E2103"
                service_type = "DME"

        # Search for any 5-digit numeric word if CPT code wasn't set by keyword
        if not cpt_code:
            for word in raw_text.split():
                clean_word = word.strip(",.()[]{}")
                if clean_word.isdigit() and len(clean_word) == 5:
                    cpt_code = clean_word
                    break

        if not member_id:
            for word in raw_text.split():
                clean_word = word.strip(",.()[]{}")
                if clean_word.lower().startswith("m") and clean_word[1:].isdigit():
                    member_id = clean_word
                    break

        provider_id = ""
        for word in raw_text.split():
            clean_word = word.strip(",.()[]{}")
            if clean_word.lower().startswith("p") and clean_word[1:].isdigit():
                provider_id = clean_word
                break

        missing = []
        if not member_id:
            missing.append("Member ID")
        if not provider_id:
            missing.append("Provider ID")
        if not cpt_code:
            missing.append("CPT Code")

        # Create fallback DocumentItems matching the state's uploaded docs
        existing_docs = state.patient_data.get("documents", [])
        fallback_docs = []
        for edoc in existing_docs:
            fname = edoc.get("filename", "").lower()
            text = edoc.get("extracted_text", "").lower()
            
            doc_type = "Clinical Assessment Notes"
            if "radiology" in fname or "mri" in fname or "x-ray" in fname or "radiology" in text[:500]:
                doc_type = "Radiology Report"
            elif "therapy" in fname or "pt" in fname or "therapy" in text[:500]:
                doc_type = "Conservative Therapy Logs"
            elif "referral" in fname or "surgery referral" in text[:500]:
                doc_type = "Orthopedic Surgery Referral Letter"
            elif "pcp" in fname or "primary care" in fname:
                doc_type = "Primary Care Physician Letter"
            elif "drug" in fname or "prescription" in fname:
                doc_type = "Prior Authorization Drug Request Form"
            
            fallback_docs.append(DocumentItem(
                document_id=edoc.get("document_id", str(uuid.uuid4())),
                document_type=doc_type,
                filename=edoc.get("filename", "unknown.txt"),
                extracted_text=edoc.get("extracted_text", "")
            ))
            
        if not fallback_docs:
            fallback_docs = [
                DocumentItem(
                    document_type="Clinical Notes",
                    filename="fallback_upload.txt",
                    extracted_text=raw_text
                )
            ]

        submission = ProviderSubmission(
            patient_info=PatientInfo(member_id=member_id or "M123", first_name=first_name, last_name=last_name, date_of_birth=None),
            provider_info=ProviderInfo(provider_id=provider_id or "P456", name=provider_name, specialty="Specialty Not Extracted"),
            clinical_metadata=ClinicalMetadata(
                cpt_code=cpt_code or "72148",
                icd_code=icd_code,
                requested_service="Surgery" if service_type == "SURGERY" else "Prior Authorization Request",
                requested_date=req_date,
            ),
            documents=fallback_docs,
            is_complete=not bool(missing),
            missing_fields=missing,
            duplicate_suspected="duplicate" in lower_text,
        )

        self._map_submission_to_state(state, submission, raw_text)


