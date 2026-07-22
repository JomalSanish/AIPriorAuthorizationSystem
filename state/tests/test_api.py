from fastapi.testclient import TestClient
from api import app, cases

client = TestClient(app)

def test_get_cases() -> None:
    response = client.get("/api/cases")
    assert response.status_code == 200
    data = response.json()
    assert "cases" in data
    assert "PA-72148-A (Approved MRI)" in data["cases"]
    assert "PA-96372-I (Incomplete Drug)" in data["cases"]

def test_get_case_detail() -> None:
    response = client.get("/api/cases/PA-72148-A (Approved MRI)")
    assert response.status_code == 200
    data = response.json()
    assert data["request_id"] == "PA-72148-A"
    assert data["review_status"] == "APPROVED"
    assert data["routing_queue"] == "Nurse Review"

def test_get_case_not_found() -> None:
    response = client.get("/api/cases/PA-UNKNOWN-CASE")
    assert response.status_code == 404

def test_post_triage_decision() -> None:
    payload = {
        "case_key": "PA-72148-A (Approved MRI)",
        "route": "Medical Director",
        "status": "PENDING",
        "communication_draft": "Updated outreach correspondence letter text."
    }
    response = client.post("/api/cases/triage", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    
    # Verify in-memory state updated
    case_state = cases["PA-72148-A (Approved MRI)"]
    assert case_state.routing_queue == "Medical Director"
    assert case_state.review_status == "PENDING"
    assert case_state.artifacts["communication_draft"] == "Updated outreach correspondence letter text."
    assert any("updated review queue to Medical Director" in log for log in case_state.audit_trail)
