import os
import json
import logging
from pathlib import Path
from dataclasses import asdict
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables on startup
load_dotenv()

from state.session_state import SessionState
from agents.intake_agent import IntakeAgent
from agents.evidence_agent import EvidenceAgent
from agents.gap_agent import GapAgent
from agents.summary_agent import SummaryAgent
from agents.audit_agent import AuditAgent
from utils.pdf_utils import extract_text_from_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(title="Prior Auth Operations Center API")

# Enable CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cases DB (same as app.py Streamlit defaults)
cases: Dict[str, SessionState] = {}

def initialize_default_cases():
    # 1. Setup a default completed MRI case
    c1 = SessionState()
    c1.request_id = "PA-72148-A"
    c1.patient_data = {
        "member_id": "M88231",
        "provider_id": "P-9004",
        "cpt_code": "72148",
        "icd_code": "M54.5",
        "requested_date": "2026-07-09",
        "raw_text": "Patient reports severe lower back pain radiating down the left leg for 3 months. Has completed 8 weeks of physical therapy and failed NSAIDs trial.",
        "missing_fields": [],
        "duplicate_suspected": False,
        "documents": [{"document_id": "d1", "document_type": "Clinical Evaluation Notes", "filename": "pcp_notes.txt", "extracted_text": "Back pain radiating down left leg for 3 months. Trial of physical therapy for 8 weeks completed. NSAIDs failed."}]
    }
    c1.classification = {
        "type": "IMAGING",
        "urgency": "ROUTINE",
        "reason": "CPT code 72148 mapped to IMAGING service type.",
    }
    c1.evidence = [
        {
            "prerequisite": "Lower back pain radiating down the leg or signs of radiculopathy",
            "text": "Patient reports severe lower back pain radiating down the left leg for 3 months.",
            "citation": "Clinical Documents (FAISS Match)",
            "score": 0.88,
        },
        {
            "prerequisite": "Trial of conservative physical therapy for at least 6 weeks",
            "text": "Has completed 8 weeks of physical therapy.",
            "citation": "Clinical Documents (FAISS Match)",
            "score": 0.89,
        },
        {
            "prerequisite": "Trial of conservative drug therapy (NSAIDs or analgesics) for at least 4 weeks",
            "text": "failed NSAIDs trial.",
            "citation": "Clinical Documents (FAISS Match)",
            "score": 0.82,
        }
    ]
    c1.gap_analysis = {
        "status": "APPROVED",
        "reasoning": "All clinical guidelines prerequisites satisfied. Evidence of physical therapy and drug trials verified.",
        "checklist_items": [
            {"criterion": "Lower back pain radiating down the leg or signs of radiculopathy", "status": "PRESENT", "rationale": "Notes document pain radiating down left leg for 3 months.", "citation": "Clinical Documents"},
            {"criterion": "Trial of conservative physical therapy for at least 6 weeks", "status": "PRESENT", "rationale": "Completed 8 weeks of physical therapy.", "citation": "Clinical Documents"},
            {"criterion": "Trial of conservative drug therapy (NSAIDs or analgesics) for at least 4 weeks", "status": "PRESENT", "rationale": "Failed NSAIDs trial.", "citation": "Clinical Documents"}
        ],
        "missing_info": [],
    }
    c1.artifacts = {
        "summary": "### Clinical Case Summary\n- **Case ID:** PA-72148-A\n- **Patient:** Member M88231\n- **Determination:** Guidelines satisfied. Recommended action: Route to Nurse Reviewer.",
        "communication_draft": "Date: 2026-07-09\n\nTo: Provider P-9004\nRe: Prior Authorization Approval for CPT 72148 (Member M88231)\n\nDear Provider,\n\nWe have completed our clinical review for CPT 72148. The criteria for Lumbar Spine MRI are fully met. The case has been routed to final triage.",
        "compliance_hash": "a4d3e5b6c7a8b9f0a2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5",
        "audit_timestamp": "2026-07-09T23:27:13Z",
        "audit_model": "gpt-4o-mini"
    }
    c1.review_status = "APPROVED"
    c1.routing_queue = "Nurse Review"
    c1.audit_trail = [
        "[2026-07-09T23:27:13Z] Ingested Case PA-72148-A",
        "[2026-07-09T23:27:13Z] Gap Agent evaluated compliance: APPROVED"
    ]
    
    # 2. Setup an incomplete Drug case
    c2 = SessionState()
    c2.request_id = "PA-96372-I"
    c2.patient_data = {
        "member_id": "",
        "provider_id": "P-4001",
        "cpt_code": "96372",
        "icd_code": "",
        "requested_date": "2026-07-09",
        "raw_text": "Requesting Humira for Plaque Psoriasis.",
        "missing_fields": ["Member ID", "ICD-10 Code"],
        "duplicate_suspected": False,
        "documents": []
    }
    c2.classification = {
        "type": "DRUG",
        "urgency": "ROUTINE",
        "reason": "CPT code 96372 mapped to DRUG service type.",
    }
    c2.evidence = []
    c2.gap_analysis = {
        "status": "PENDING",
        "reasoning": "Missing critical Member ID and ICD-10 demographics.",
        "checklist_items": [],
        "missing_info": ["Member ID", "ICD-10 Code"],
    }
    c2.artifacts = {
        "summary": "### Clinical Case Summary\n- Case is incomplete. Critical demographics (Member ID) missing.",
        "communication_draft": "Date: 2026-07-09\n\nTo: Provider P-4001\nRe: Incomplete Information for Humira request\n\nDear Provider,\n\nWe received your request for Humira. However, the submission is missing the Member ID. Please submit this detail.",
    }
    c2.review_status = "PENDING"
    c2.routing_queue = "Intake"
    c2.audit_trail = [
        "[2026-07-09T23:27:13Z] Ingested Case PA-96372-I",
        "[2026-07-09T23:27:13Z] Core demographics missing. Route to Intake."
    ]

    cases["PA-72148-A (Approved MRI)"] = c1
    cases["PA-96372-I (Incomplete Drug)"] = c2

initialize_default_cases()

@app.get("/api/cases")
def get_cases():
    """Retrieve list of available case summaries for navbar navigation."""
    result = {}
    for label, case_state in cases.items():
        result[label] = {
            "request_id": case_state.request_id,
            "review_status": case_state.review_status,
            "routing_queue": case_state.routing_queue,
            "patient_data": {
                "member_id": case_state.patient_data.get("member_id", ""),
                "cpt_code": case_state.patient_data.get("cpt_code", ""),
            }
        }
    return {"cases": result}

@app.get("/api/cases/{case_key}")
def get_case(case_key: str):
    """Retrieve full case details by case label key."""
    if case_key not in cases:
        raise HTTPException(status_code=404, detail="Case session not found.")
    return asdict(cases[case_key])

@app.post("/api/cases/ingest")
async def ingest_case(
    member_id: Optional[str] = Form(None),
    provider_id: Optional[str] = Form(None),
    cpt_code: Optional[str] = Form(None),
    icd_code: Optional[str] = Form(None),
    files: List[UploadFile] = File([])
):
    """Ingest notes/json/pdfs, run Intake & Evidence agents, and create a new session state."""
    
    active_state = SessionState()
    active_state.patient_data = {
        "member_id": member_id or "",
        "provider_id": provider_id or "",
        "cpt_code": cpt_code or "",
        "icd_code": icd_code or "",
        "raw_text": "",
        "missing_fields": [],
        "duplicate_suspected": False,
        "documents": []
    }

    combined_text = []

    for file in files:
        if not file.filename:
            continue
            
        filename = file.filename
        content = await file.read()
        extracted_text = ""
        
        if filename.endswith(".json"):
            try:
                extracted_text = content.decode("utf-8")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON payload in {filename}: {str(e)}")
        elif filename.endswith(".pdf"):
            try:
                # Save temp pdf to extract text
                temp_dir = Path("scratch")
                temp_dir.mkdir(exist_ok=True)
                temp_file = temp_dir / filename
                with open(temp_file, "wb") as f:
                    f.write(content)
                extracted_text = extract_text_from_pdf(temp_file)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to parse PDF document {filename}: {str(e)}")
        else:
            extracted_text = content.decode("utf-8")

        combined_text.append(extracted_text)
        
        active_state.patient_data["documents"].append({
            "document_id": f"d_{len(active_state.patient_data['documents'])}",
            "document_type": "Unknown Document", # Will be classified by IntakeAgent
            "filename": filename,
            "extracted_text": extracted_text
        })
        
    active_state.patient_data["raw_text"] = "\n\n".join(combined_text)

    active_state.audit_trail = ["Pipeline execution triggered via React API."]

    # Run Ingestion pipelines
    try:
        active_state = IntakeAgent().run(active_state)
        active_state = EvidenceAgent().run(active_state)
    except Exception as e:
        logger.error(f"Error in Intake/Evidence pipelines: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    # Add to list with safe fallbacks
    resolved_cpt = active_state.patient_data.get("cpt_code")
    if not resolved_cpt or resolved_cpt == "UNKNOWN":
        resolved_cpt = cpt_code
    if not resolved_cpt or resolved_cpt == "UNKNOWN":
        resolved_cpt = "27447"
        
    c_id = active_state.patient_data.get("member_id") or "M98765"
    
    # Format and save structured case label
    label = f"PA-{resolved_cpt}-{c_id[:4]} ({active_state.review_status})"
    active_state.request_id = f"PA-{resolved_cpt}-{c_id[:4]}"
    cases[label] = active_state

    # Return key label along with case data
    return {"key": label, "data": asdict(active_state)}

class CaseQuery(BaseModel):
    case_key: str

@app.post("/api/cases/gap-analysis")
def gap_analysis(query: CaseQuery):
    """Run Gap analysis agent on selected case."""
    if query.case_key not in cases:
        raise HTTPException(status_code=404, detail="Case session not found.")
    
    active_state = cases[query.case_key]
    try:
        active_state = GapAgent().run(active_state)
        cases[query.case_key] = active_state
    except Exception as e:
        logger.error(f"Error in GapAgent execution: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"GapAgent error: {str(e)}")
        
    return asdict(active_state)

@app.post("/api/cases/summarize")
def summarize_case(query: CaseQuery):
    """Run Summary and Audit agents to generate correspondence letter and audit hash."""
    if query.case_key not in cases:
        raise HTTPException(status_code=404, detail="Case session not found.")

    active_state = cases[query.case_key]
    try:
        active_state = SummaryAgent().run(active_state)
        active_state = AuditAgent().run(active_state)
        cases[query.case_key] = active_state
    except Exception as e:
        logger.error(f"Error in Summary/Audit execution: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Summary/Audit error: {str(e)}")

    return asdict(active_state)

class TriageQuery(BaseModel):
    case_key: str
    route: str
    status: str
    communication_draft: str

@app.post("/api/cases/triage")
def triage_case(query: TriageQuery):
    """Record manual decision route, saving correspondence logs and updating queues."""
    if query.case_key not in cases:
        raise HTTPException(status_code=404, detail="Case session not found.")

    active_state = cases[query.case_key]
    active_state.routing_queue = query.route
    active_state.review_status = query.status
    active_state.artifacts["communication_draft"] = query.communication_draft
    
    timestamp = active_state.artifacts.get("audit_timestamp", "2026-07-13T15:13:00Z")
    log_msg = f"[{timestamp}] Manually updated review queue to {query.route}."
    active_state.audit_trail.append(log_msg)
    
    cases[query.case_key] = active_state
    return {"status": "SUCCESS", "data": asdict(active_state)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
