from __future__ import annotations

import os
import json
from pathlib import Path
import streamlit as st

from agents.intake_agent import IntakeAgent
from agents.evidence_agent import EvidenceAgent
from agents.gap_agent import GapAgent
from agents.summary_agent import SummaryAgent
from agents.audit_agent import AuditAgent
from state.session_state import SessionState
from utils.pdf_utils import extract_text_from_pdf

# Setup path for guidelines PDF (kept for fallback compatibility)
PDF_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "guidelines"
    / "prior-authorization-and-step-therapy-guidelines.pdf"
)

# Page Configuration
st.set_page_config(
    page_title="Prior Authorization Operations Center",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Sleek Dark Styling
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: #0b0d13;
        color: #f1f5f9;
    }
    
    [data-testid="stHeader"] {
        background: rgba(11, 13, 19, 0.6);
        backdrop-filter: blur(12px);
    }
    
    [data-testid="stSidebar"] {
        background-color: #0f121d !important;
        border-right: 1px solid rgba(255, 255, 255, 0.04);
    }
    
    /* Title Gradient styling */
    .app-title-container {
        padding: 1rem 0 1.5rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 1.5rem;
    }
    .app-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #c084fc, #818cf8, #38bdf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.03em;
        margin-bottom: 0.2rem;
    }
    .app-subtitle {
        color: #94a3b8;
        font-size: 0.95rem;
        font-weight: 400;
    }
    
    /* Modern Glassmorphic Dashboard Cards */
    .dashboard-card {
        background: rgba(30, 41, 59, 0.25);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        box-shadow: 0 4px 20px 0 rgba(0, 0, 0, 0.2);
        transition: border-color 0.2s ease;
    }
    
    .dashboard-card:hover {
        border-color: rgba(129, 140, 248, 0.2);
    }
    
    .card-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 0.8rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* Status Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.25rem 0.75rem;
        font-size: 0.75rem;
        font-weight: 700;
        border-radius: 9999px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .badge-present { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-absent { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); }
    .badge-unclear { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); }
    
    /* Queue specific badges */
    .badge-imaging { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
    .badge-drug { background: rgba(192, 132, 252, 0.15); color: #c084fc; border: 1px solid rgba(192, 132, 252, 0.3); }
    .badge-surgery { background: rgba(244, 63, 94, 0.15); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.3); }
    
    /* Timeline items */
    .timeline-item {
        position: relative;
        padding-left: 1.8rem;
        margin-bottom: 0.8rem;
        font-size: 0.85rem;
        color: #cbd5e1;
    }
    .timeline-item::before {
        content: "";
        position: absolute;
        left: 0.4rem;
        top: 0.3rem;
        width: 8px;
        height: 8px;
        background: #818cf8;
        border-radius: 50%;
        box-shadow: 0 0 8px #818cf8;
    }
    
    /* Evidence segment card */
    .evidence-card {
        background: rgba(255, 255, 255, 0.015);
        border: 1px solid rgba(255, 255, 255, 0.03);
        padding: 0.8rem;
        border-radius: 8px;
        margin-bottom: 0.6rem;
    }
    
    .stButton>button {
        border-radius: 8px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header Section
st.markdown(
    """
    <div class="app-title-container">
        <div class="app-title">Prior Authorization Operations Center</div>
        <div class="app-subtitle">Stepper-Based Prior Auth Assistant & Locked Context Sidebar</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Initialize Simulated Cases in Session State if missing
if "cases" not in st.session_state:
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
    c1.audit_trail = ["[2026-07-09T23:27:13Z] Ingested Case PA-72148-A", "[2026-07-09T23:27:13Z] Gap Agent evaluated compliance: APPROVED"]

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
    c2.audit_trail = ["[2026-07-09T23:27:13Z] Ingested Case PA-96372-I", "[2026-07-09T23:27:13Z] Core demographics missing. Route to Intake."]

    st.session_state["cases"] = {
        "PA-72148-A (Approved MRI)": c1,
        "PA-96372-I (Incomplete Drug)": c2,
    }

if "draft_communication" not in st.session_state:
    st.session_state["draft_communication"] = ""

# Sidebar - Settings & Selector
st.sidebar.header("System Settings")
api_key_input = st.sidebar.text_input(
    "OpenAI API Key Override",
    type="password",
    value=st.session_state.get("openai_api_key", ""),
    placeholder="sk-...",
)
if api_key_input:
    st.session_state["openai_api_key"] = api_key_input
    os.environ["OPENAI_API_KEY"] = api_key_input

has_key = bool(os.getenv("OPENAI_API_KEY"))
if has_key:
    st.sidebar.success("✅ OpenAI API Connected")
else:
    st.sidebar.warning("⚠️ Using Local Heuristic Fallbacks (API Key not set)")

st.sidebar.subheader("Case Navigation")
selected_case_id = st.sidebar.selectbox(
    "Select Active Case Session",
    options=list(st.session_state["cases"].keys()) + ["+ Create New Case"],
)

# Active state resolution
if selected_case_id == "+ Create New Case":
    if "temp_new_case" not in st.session_state:
        st.session_state["temp_new_case"] = SessionState()
    active_state = st.session_state["temp_new_case"]
else:
    active_state = st.session_state["cases"][selected_case_id]

# Maintain stepper current step progress
if "current_step" not in st.session_state:
    st.session_state["current_step"] = 1

if "current_case_id" not in st.session_state or st.session_state["current_case_id"] != selected_case_id:
    st.session_state["current_case_id"] = selected_case_id
    if selected_case_id == "+ Create New Case":
        st.session_state["draft_communication"] = ""
        st.session_state["current_step"] = 1
        st.session_state["current_policy_rules"] = []
        st.session_state["current_required_docs"] = []
    else:
        st.session_state["draft_communication"] = active_state.artifacts.get("communication_draft", "")
        # Set dynamic stepper step based on case status
        if active_state.review_status in ("APPROVED", "REJECTED", "REQUEST MORE INFO"):
            st.session_state["current_step"] = 3
        elif active_state.patient_data.get("cpt_code", ""):
            st.session_state["current_step"] = 2
        else:
            st.session_state["current_step"] = 1
        st.session_state["current_policy_rules"] = active_state.current_policy_rules
        st.session_state["current_required_docs"] = active_state.current_required_docs

# Update draft letter cached in session state when case details are present
def update_draft_cache():
    if "draft_communication" in st.session_state:
        active_state.artifacts["communication_draft"] = st.session_state["draft_communication"]

# ==================== PERSISTENT CONTEXT SIDEBAR ====================
if active_state.request_id or active_state.patient_data.get("raw_text", ""):
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Locked Case Context")
    st.sidebar.markdown(f"**Request ID:** `{active_state.request_id or 'Ingesting...'}`")
    st.sidebar.markdown(f"**Review Status:** `{active_state.review_status}`")
    st.sidebar.markdown(f"**Target Queue:** `{active_state.routing_queue}`")
    
    st.sidebar.markdown("### Patient Demographics")
    st.sidebar.markdown(f"**Member ID:** `{active_state.patient_data.get('member_id') or 'N/A'}`")
    st.sidebar.markdown(f"**Provider ID:** `{active_state.patient_data.get('provider_id') or 'N/A'}`")
    st.sidebar.markdown(f"**CPT Code:** `{active_state.patient_data.get('cpt_code') or 'N/A'}`")
    st.sidebar.markdown(f"**ICD-10 Code:** `{active_state.patient_data.get('icd_code') or 'N/A'}`")
    
    badge_type = f"badge-{active_state.classification.get('type', '').lower()}"
    st.sidebar.markdown(
        f"**Service Type:** <span class='badge {badge_type}'>{active_state.classification.get('type') or 'N/A'}</span>",
        unsafe_allow_html=True
    )
    
    # Raw clinical notes expander
    with st.sidebar.expander("📄 Submitted Clinical Notes", expanded=True):
        st.write(active_state.patient_data.get("raw_text", "No notes uploaded."))

# ==================== STEPPER PROGRESS HEADER ====================
step_cols = st.columns(3)
step_names = ["Step 1: Ingest Docs", "Step 2: RAG & Gap Analysis", "Step 3: Summary & Route"]
for idx, name in enumerate(step_names):
    step_num = idx + 1
    with step_cols[idx]:
        if st.session_state["current_step"] == step_num:
            st.markdown(f"<div style='border-bottom: 3px solid #818cf8; padding-bottom: 4px; text-align:center; font-weight:bold; color:#818cf8;'>{name}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 4px; text-align:center; color:#94a3b8;'>{name}</div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)


# ==================== STEP 1: INGESTION & UPLOAD ZONE ====================
if st.session_state["current_step"] == 1:
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">📥 Step 1: Ingest Case Documents & Demographics</div>', unsafe_allow_html=True)

    ing_col1, ing_col2 = st.columns([1, 1])

    with ing_col1:
        memb_id = st.text_input("Member ID", value=active_state.patient_data.get("member_id", ""))
        prov_id = st.text_input("Provider ID", value=active_state.patient_data.get("provider_id", ""))
        cpt_val = st.text_input("CPT / HCPCS Code", value=active_state.patient_data.get("cpt_code", ""))
        icd_val = st.text_input("ICD-10 Diagnosis Code", value=active_state.patient_data.get("icd_code", ""))

    panel_1_complete = True
    with ing_col2:
        uploaded_file = st.file_uploader(
            "Upload Provider Submission (JSON) or Clinical Notes (PDF/TXT)", type=["json", "pdf", "txt"]
        )
        
        extracted_text_val = ""
        if uploaded_file is not None:
            filename = uploaded_file.name
            if filename.endswith(".json"):
                try:
                    raw_json = uploaded_file.read().decode("utf-8")
                    extracted_text_val = raw_json
                    st.success("Loaded structured JSON payload successfully.")
                except Exception as e:
                    st.error(f"Error reading JSON: {str(e)}")
            elif filename.endswith(".pdf"):
                try:
                    temp_file = Path("scratch") / filename
                    temp_file.parent.mkdir(exist_ok=True)
                    with open(temp_file, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    extracted_text_val = extract_text_from_pdf(temp_file)
                    st.success(f"Extracted {len(extracted_text_val)} characters from PDF.")
                except Exception as e:
                    st.error(f"Error parsing PDF: {str(e)}")
            else:
                extracted_text_val = uploaded_file.read().decode("utf-8")
                st.success("Loaded plain text file successfully.")

        clinical_notes = st.text_area(
            "Clinical Documentation Notes",
            value=extracted_text_val if extracted_text_val else active_state.patient_data.get("raw_text", ""),
            height=150,
            placeholder="Type or paste the clinical narrative details here..."
        )

    run_pipeline = st.button("🚀 Run AI Evidence Pipeline", use_container_width=True)

    if run_pipeline:
        with st.spinner("Running Intake & Evidence Extraction Agents..."):
            active_state.patient_data.update({
                "member_id": memb_id,
                "provider_id": prov_id,
                "cpt_code": cpt_val,
                "icd_code": icd_val,
                "raw_text": clinical_notes
            })
            active_state.audit_trail = ["Pipeline execution triggered by user."]

            # Execute Step 1 agents
            active_state = IntakeAgent().run(active_state)
            active_state = EvidenceAgent().run(active_state)

            # Move to Step 2
            st.session_state["current_step"] = 2
            st.session_state["current_policy_rules"] = active_state.current_policy_rules
            st.session_state["current_required_docs"] = active_state.current_required_docs
            
            # Save progress back to session list
            cid = active_state.patient_data.get("member_id", "TEMP")
            label = f"PA-{cpt_val or 'UNKNOWN'}-{cid[:4]} ({active_state.review_status})"
            st.session_state["cases"][label] = active_state
            
            st.success("Intake & Evidence Agents complete. Transitioning to Step 2...")
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ==================== STEP 2: RAG VERIFICATION & GAP ANALYSIS ====================
elif st.session_state["current_step"] == 2:
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🔍 Step 2: Policy RAG Verification & Gap Analysis</div>', unsafe_allow_html=True)

    rag_col1, rag_col2 = st.columns([1, 1])

    with rag_col1:
        st.markdown("#### Extracted Clinical Ingestion Details")
        st.markdown(f"**Member ID:** `{active_state.patient_data.get('member_id') or '🚨 MISSING'}`")
        st.markdown(f"**Provider ID:** `{active_state.patient_data.get('provider_id') or '🚨 MISSING'}`")
        st.markdown(f"**CPT Code:** `{active_state.patient_data.get('cpt_code') or '🚨 MISSING'}`")
        st.markdown(f"**ICD-10 Code:** `{active_state.patient_data.get('icd_code') or '🚨 MISSING'}`")
        
        badge_type = f"badge-{active_state.classification.get('type', '').lower()}"
        st.markdown(
            f"**Service Type:** <span class='badge {badge_type}'>{active_state.classification.get('type') or 'N/A'}</span>",
            unsafe_allow_html=True
        )

    with rag_col2:
        st.markdown("#### Retrieved Medical Policy Prerequisites")
        
        policies_path = Path(__file__).resolve().parent / "data" / "mock_policies.json"
        policies = []
        if policies_path.exists():
            try:
                with open(policies_path, "r") as f:
                    policies = json.load(f).get("policies", [])
            except Exception:
                pass
                
        cpt = str(active_state.patient_data.get("cpt_code", "")).strip()
        active_policy = next((p for p in policies if p["cpt_code"] == cpt), None)

        if active_policy:
            st.markdown(f"**Policy Guideline:** `{active_policy['service_name']} (CPT {active_policy['cpt_code']})`")
            st.markdown(f"**Specialty Requirement:** `{active_policy['specialty_requirement']}`")
            st.markdown("**Clinical Criteria Checklist Guidelines:**")
            for prereq in active_policy.get("clinical_prerequisites", []):
                st.markdown(f"- {prereq}")
        elif cpt:
            st.warning(f"⚠️ No structured mock policy found in database for CPT code '{cpt}'. Human routing required.")
        else:
            st.info("No policy retrieved yet.")

        # Display retrieved PDF guidelines search passages if available
        if hasattr(active_state, "retrieved_policy_passages") and active_state.retrieved_policy_passages:
            st.markdown("---")
            st.markdown("📖 **Retrieved PDF Guideline Passages (Hybrid Search):**")
            for passage in active_state.retrieved_policy_passages:
                with st.expander(f"📄 {passage['source']} (Page {passage['page']}) - Score: {passage['score']}", expanded=False):
                    st.write(passage["text"])

    st.markdown("</div>", unsafe_allow_html=True)

    # Gap Checklist (Requirements checklist)
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">⚠️ Criteria Gap Verification Checklist</div>', unsafe_allow_html=True)

    # If the checklist is empty, run the Gap Agent on the fly
    if not active_state.gap_analysis.get("checklist_items"):
        with st.spinner("Analyzing guideline gaps..."):
            active_state = GapAgent().run(active_state)
            for k, v in st.session_state["cases"].items():
                if v.request_id == active_state.request_id:
                    st.session_state["cases"][k] = active_state

    gap_status = active_state.gap_analysis.get("status", "PENDING")
    st.markdown(f"**Overall Compliance Assessment:** `{gap_status}`")

    items = active_state.gap_analysis.get("checklist_items", [])
    if items:
        for item in items:
            status = item.get("status", "UNCLEAR").upper()
            if status == "PRESENT":
                badge_style = "badge-present"
                icon = "✅"
            elif status == "ABSENT":
                badge_style = "badge-absent"
                icon = "❌"
            else:
                badge_style = "badge-unclear"
                icon = "⚠️"

            st.markdown(
                f"""
                <div class="evidence-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-weight:600;">{icon} {item.get('criterion')}</span>
                        <span class="badge {badge_style}">{status}</span>
                    </div>
                    <div style="font-size:0.85rem; color:#94a3b8; margin-top:0.4rem;">
                        <strong>Rationale:</strong> {item.get('rationale')}
                    </div>
                    <div style="font-size:0.8rem; color:#818cf8; margin-top:0.2rem;">
                        <strong>Evidence Passage:</strong> "{active_state.patient_data.get('raw_text', '')[:100]}..." | <strong>Source:</strong> {item.get('citation')}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info("No checklist evaluation results available.")

    missing = active_state.gap_analysis.get("missing_info", [])
    if missing:
        st.markdown("##### 🚨 Highlighted Gaps (Request Prerequisite Details)")
        for m in missing:
            st.markdown(f"<li style='color:#fbbf24; font-size:0.85rem;'>{m}</li>", unsafe_allow_html=True)

    st.markdown("---")
    
    # Navigation controls
    col_nav1, col_nav2 = st.columns([1, 1])
    with col_nav1:
        if st.button("⬅️ Back to Upload", use_container_width=True):
            st.session_state["current_step"] = 1
            st.rerun()
            
    with col_nav2:
        if st.button("Generate Summary & Route ➡️", use_container_width=True):
            with st.spinner("Generating clinical summary & correspondence..."):
                active_state = SummaryAgent().run(active_state)
                active_state = AuditAgent().run(active_state)
                
                st.session_state["draft_communication"] = active_state.artifacts.get("communication_draft", "")
                st.session_state["current_step"] = 3
                
                for k, v in st.session_state["cases"].items():
                    if v.request_id == active_state.request_id:
                        st.session_state["cases"][k] = active_state
                        
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


# ==================== STEP 3: ACTIONABLE DECISION DASHBOARD & SUMMARY ====================
elif st.session_state["current_step"] == 3:
    st.markdown('<div class="dashboard-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">🎯 Step 3: Human-in-the-Loop Action & Summary</div>', unsafe_allow_html=True)

    hitl_col1, hitl_col2 = st.columns([1, 1])

    with hitl_col1:
        st.markdown("#### Clinical Case Summary Brief")
        st.markdown(active_state.artifacts.get("summary", "*No summary generated yet.*"))

    with hitl_col2:
        st.markdown("#### Provider Communication Letter Draft")
        st.text_area(
            "Editable Draft Correspondence",
            key="draft_communication",
            on_change=update_draft_cache,
            height=200
        )

    st.markdown("---")
    st.markdown("#### Operational Triage Route Decision")
    dec_col1, dec_col2, dec_col3 = st.columns(3)

    with dec_col1:
        if st.button("✅ Proceed / Route to Nurse", use_container_width=True):
            active_state.routing_queue = "Nurse Review"
            active_state.review_status = "PENDING"
            active_state.audit_trail.append(f"[{active_state.artifacts.get('audit_timestamp', '')}] Manually routed case to Nurse Review Queue.")
            st.success("Routed successfully to Nurse Review.")
            st.rerun()

    with dec_col2:
        if st.button("❌ Reject / Request Docs", use_container_width=True):
            active_state.routing_queue = "Information Request"
            active_state.review_status = "REQUEST MORE INFO"
            active_state.artifacts["communication_draft"] = st.session_state["draft_communication"]
            active_state.audit_trail.append(f"[{active_state.artifacts.get('audit_timestamp', '')}] Manually requested additional evidence from provider.")
            st.warning("Case set to Request Info queue. Correspondence saved.")
            st.rerun()

    with dec_col3:
        if st.button("⚠️ Escalate to Medical Director", use_container_width=True):
            active_state.routing_queue = "Medical Director"
            active_state.review_status = "PENDING"
            active_state.audit_trail.append(f"[{active_state.artifacts.get('audit_timestamp', '')}] Case escalated to Medical Director.")
            st.error("Case escalated to Medical Director.")
            st.rerun()

    st.markdown("---")
    
    col_nav1, _ = st.columns([1, 1])
    with col_nav1:
        if st.button("⬅️ Back to Evidence", use_container_width=True):
            st.session_state["current_step"] = 2
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # Log Panel
    with st.expander("🛡️ Compliance Audit & Operational Telemetry", expanded=False):
        aud_col1, aud_col2 = st.columns([2, 1])
        
        with aud_col1:
            st.markdown("#### Chronological Audit Trail Log")
            if active_state.audit_trail:
                for log in active_state.audit_trail:
                    st.markdown(f"<div class='timeline-item'>{log}</div>", unsafe_allow_html=True)
            else:
                st.write("No telemetry logs found.")
                
        with aud_col2:
            st.markdown("#### Cryptographic Signatures")
            st.markdown(f"**Verification Model:** `{active_state.artifacts.get('audit_model', 'N/A')}`")
            st.markdown(f"**Audited Timestamp:** `{active_state.artifacts.get('audit_timestamp', 'N/A')}`")
            
            c_hash = active_state.artifacts.get("compliance_hash", "N/A")
            st.markdown("**Tamper-Evident SHA-256 Hash:**")
            st.code(c_hash, language="text")
            
            st.markdown("#### Operational Metrics Summary")
            total_cnt = len(st.session_state["cases"])
            st.metric(label="Total Tracked Sessions", value=total_cnt)
