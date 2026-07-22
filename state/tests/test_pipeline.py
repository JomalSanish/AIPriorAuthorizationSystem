from __future__ import annotations

import json
from pathlib import Path
import pytest

from agents.intake_agent import IntakeAgent
from agents.evidence_agent import EvidenceAgent
from agents.gap_agent import GapAgent
from agents.summary_agent import SummaryAgent
from agents.audit_agent import AuditAgent
from state.session_state import SessionState


def test_pipeline_lumbar_spine_mri() -> None:
    # Load MRI mock payload
    payload_path = Path(__file__).resolve().parents[2] / "data" / "sample_requests" / "mri_request.json"
    with open(payload_path, "r") as f:
        raw_payload = f.read()

    state = SessionState()
    state.patient_data = {"raw_text": raw_payload}

    # Run pipeline
    state = IntakeAgent().run(state)
    state = EvidenceAgent().run(state)
    state = GapAgent().run(state)
    state = SummaryAgent().run(state)
    state = AuditAgent().run(state)

    # Assertions
    assert state.classification["type"] == "IMAGING"
    assert state.patient_data["member_id"] == "M88231"
    assert state.patient_data["provider_id"] == "P-9004"
    assert state.patient_data["cpt_code"] == "72148"
    assert len(state.evidence) == 5
    assert state.gap_analysis["status"] == "APPROVED"
    assert len(state.gap_analysis["checklist_items"]) == 5
    assert all(item["status"] == "PRESENT" for item in state.gap_analysis["checklist_items"])
    assert state.review_status == "APPROVED"
    assert state.routing_queue == "Nurse Review"
    assert "compliance_hash" in state.artifacts


def test_pipeline_adalimumab_drug() -> None:
    # Load Adalimumab mock payload
    payload_path = Path(__file__).resolve().parents[2] / "data" / "sample_requests" / "adalimumab_request.json"
    with open(payload_path, "r") as f:
        raw_payload = f.read()

    state = SessionState()
    state.patient_data = {"raw_text": raw_payload}

    # Run pipeline
    state = IntakeAgent().run(state)
    state = EvidenceAgent().run(state)
    state = GapAgent().run(state)
    state = SummaryAgent().run(state)
    state = AuditAgent().run(state)

    # Assertions
    assert state.classification["type"] == "DRUG"
    assert state.patient_data["member_id"] == "M78231"
    assert state.patient_data["cpt_code"] == "96372"
    assert len(state.evidence) == 4
    assert state.gap_analysis["status"] == "PENDING"
    assert any(item["status"] == "ABSENT" for item in state.gap_analysis["checklist_items"])
    assert state.review_status == "REQUEST MORE INFO"
    assert "compliance_hash" in state.artifacts


def test_pipeline_knee_replacement() -> None:
    # Load Knee Replacement mock payload
    payload_path = Path(__file__).resolve().parents[2] / "data" / "sample_requests" / "knee_request.json"
    with open(payload_path, "r") as f:
        raw_payload = f.read()

    state = SessionState()
    state.patient_data = {"raw_text": raw_payload}

    # Run pipeline
    state = IntakeAgent().run(state)
    state = EvidenceAgent().run(state)
    state = GapAgent().run(state)
    state = SummaryAgent().run(state)
    state = AuditAgent().run(state)

    # Assertions
    assert state.classification["type"] == "SURGERY"
    assert state.patient_data["member_id"] == "M55421"
    assert state.patient_data["cpt_code"] == "27447"
    assert len(state.evidence) == 9
    assert state.gap_analysis["status"] == "PENDING"
    assert state.review_status == "REQUEST MORE INFO"
    assert "compliance_hash" in state.artifacts


def test_unregistered_cpt_fallback() -> None:
    state = SessionState()
    state.patient_data = {"raw_text": "Requesting service with unknown CPT 99999 for patient M789."}

    # Run pipeline
    state = IntakeAgent().run(state)
    state = EvidenceAgent().run(state)
    state = GapAgent().run(state)

    # Assert that no policy matching occurs and evidence array remains empty
    assert state.patient_data["cpt_code"] == "99999"
    assert len(state.evidence) == 0
    assert state.gap_analysis["status"] == "PENDING"


def test_missing_conservative_therapy_is_absent() -> None:
    # A clinical note that does NOT mention physical therapy or conservative treatment for CPT 72148
    raw_payload = {
        "submission_id": "SUB-72148-FAIL",
        "patient_info": {
            "member_id": "M00000",
            "first_name": "Test",
            "last_name": "Patient",
            "date_of_birth": "1990-01-01"
        },
        "provider_info": {
            "provider_id": "P-9004",
            "name": "Dr. Test",
            "specialty": "Internal Medicine"
        },
        "clinical_metadata": {
            "cpt_code": "72148",
            "icd_code": "M54.5",
            "requested_service": "Lumbar Spine MRI",
            "requested_date": "2026-07-09"
        },
        "documents": [
            {
                "document_id": "doc-test",
                "document_type": "Clinical Note",
                "filename": "clinical_note.txt",
                "extracted_text": "Patient reports lower back pain radiating down the left leg for 3 months. Neurological check is normal."
            }
        ],
        "is_complete": True,
        "missing_fields": [],
        "duplicate_suspected": False
    }

    state = SessionState()
    state.patient_data = {"raw_text": json.dumps(raw_payload)}

    # Run pipeline
    state = IntakeAgent().run(state)
    state = EvidenceAgent().run(state)
    state = GapAgent().run(state)

    # Assertions
    assert state.patient_data["cpt_code"] == "72148"
    pt_checklist_item = next((item for item in state.gap_analysis["checklist_items"] if "physical therapy" in item["criterion"].lower()), None)
    assert pt_checklist_item is not None
    assert pt_checklist_item["status"] in ("ABSENT", "UNCLEAR")


def test_pipeline_bariatric_gastric_bypass() -> None:
    # A bariatric surgery request (CPT 43644)
    raw_payload = {
        "submission_id": "SUB-43644",
        "patient_info": {
            "member_id": "M99999",
            "first_name": "Bob",
            "last_name": "Williams",
            "date_of_birth": "1985-11-30"
        },
        "provider_info": {
            "provider_id": "P-3003",
            "name": "Dr. Miller",
            "specialty": "Bariatric Surgery"
        },
        "clinical_metadata": {
            "cpt_code": "43644",
            "icd_code": "E66.01",
            "requested_service": "Laparoscopic Gastric Bypass",
            "requested_date": "2026-07-09"
        },
        "documents": [
            {
                "document_id": "doc-bariatric",
                "document_type": "Clinical Notes",
                "filename": "clinical_note.txt",
                "extracted_text": "Patient has BMI of 44. Documented participation in medically supervised weight loss program for 6 consecutive months is present. Has psychological clearance from Dr. Smith."
            }
        ],
        "is_complete": True,
        "missing_fields": [],
        "duplicate_suspected": False
    }

    state = SessionState()
    state.patient_data = {"raw_text": json.dumps(raw_payload)}

    # Run pipeline
    state = IntakeAgent().run(state)
    state = EvidenceAgent().run(state)
    state = GapAgent().run(state)

    # Assertions
    assert state.patient_data["cpt_code"] == "43644"
    assert state.classification["type"] == "SURGERY"
    
    # Assert that bariatric criteria are checked, NOT lumbar MRI or physical therapy rules
    checklist = state.gap_analysis["checklist_items"]
    assert len(checklist) == 6 # 3 prerequisites + 3 required documents
    
    # Verify specific criteria are evaluated
    assert any("BMI greater than 40" in item["criterion"] for item in checklist)
    assert any("supervised weight loss" in item["criterion"] for item in checklist)
    assert any("Psychological" in item["criterion"] or "psychologist" in item["criterion"] for item in checklist)
    
    # Assert physical therapy or back pain is NOT evaluated
    assert not any("physical therapy" in item["criterion"].lower() for item in checklist)
    assert not any("back pain" in item["criterion"].lower() for item in checklist)
