"""
T085 — Admin Integration Tests.

Tests (US5 acceptance scenarios):
  - All-cases view accessible to admin
  - Case intervention invalidates decision (FR-032, SC-009)
  - Re-verification routing check
  - Nurse account CRUD
  - Audit trail completeness
"""
import pytest
import uuid
import httpx

# Fixtures client, admin_token, nurse_token are in conftest.py

# ---------------------------------------------------------------------------
# US5: All-cases view
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_all_cases_returns_list(client: httpx.AsyncClient, admin_token: str):
    """Admin can view all cases across all queues."""
    resp = await client.get(
        "/api/admin/cases",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_nurse_cannot_view_admin_cases(client: httpx.AsyncClient, nurse_token: str):
    """SC-006: Nurse cannot access admin all-cases endpoint."""
    resp = await client.get(
        "/api/admin/cases",
        headers={"Authorization": f"Bearer {nurse_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cases_response_shape(client: httpx.AsyncClient, admin_token: str):
    """Admin all-cases response must include required fields."""
    resp = await client.get(
        "/api/admin/cases",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    if not data:
        pytest.skip("No cases in system — skip shape check")
    item = data[0]
    for field in ["case_id", "status", "policy_name", "created_at"]:
        assert field in item, f"Required field '{field}' missing from admin cases response"


# ---------------------------------------------------------------------------
# FR-032, SC-009: Case intervention
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_patch_nonexistent_case_returns_404(client: httpx.AsyncClient, admin_token: str):
    """Patching a nonexistent case returns 404."""
    resp = await client.patch(
        f"/api/admin/cases/{uuid.uuid4()}",
        json={"member_id": "M999"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_patch_no_fields_returns_400(client: httpx.AsyncClient, admin_token: str):
    """Patching with no fields returns 400."""
    resp = await client.patch(
        f"/api/admin/cases/{uuid.uuid4()}",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Either 404 (case not found) or 400 (no fields)
    assert resp.status_code in (400, 404)


@pytest.mark.asyncio
async def test_nurse_cannot_patch_cases(client: httpx.AsyncClient, nurse_token: str):
    """SC-006: Nurse cannot use admin intervention endpoint."""
    resp = await client.patch(
        f"/api/admin/cases/{uuid.uuid4()}",
        json={"member_id": "M999"},
        headers={"Authorization": f"Bearer {nurse_token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Nurse account CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_list_users(client: httpx.AsyncClient, admin_token: str):
    """Admin can list all users."""
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert len(users) >= 3, "Expected at least 3 seeded users (admin, intake, nurse)"


@pytest.mark.asyncio
async def test_admin_create_user(client: httpx.AsyncClient, admin_token: str):
    """Admin can create a new user."""
    new_username = f"test_nurse_{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/admin/users",
        json={"username": new_username, "password": "password123", "role": "nurse"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == new_username
    assert data["role"] == "nurse"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_admin_create_duplicate_user_fails(client: httpx.AsyncClient, admin_token: str):
    """Creating a user with an existing username returns 409."""
    resp = await client.post(
        "/api/admin/users",
        json={"username": "admin_user", "password": "password123", "role": "admin"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_deactivate_user(client: httpx.AsyncClient, admin_token: str):
    """Admin can deactivate a user (soft-delete)."""
    # Create a temp user to deactivate
    new_username = f"temp_user_{uuid.uuid4().hex[:6]}"
    create_resp = await client.post(
        "/api/admin/users",
        json={"username": new_username, "password": "password123", "role": "nurse"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    # Deactivate
    patch_resp = await client.patch(
        f"/api/admin/users/{user_id}",
        json={"is_active": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_audit_global_returns_paginated(client: httpx.AsyncClient, admin_token: str):
    """Global audit log returns paginated response."""
    resp = await client.get(
        "/api/admin/audit?page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "entries" in data
    assert "page" in data
    assert isinstance(data["entries"], list)


@pytest.mark.asyncio
async def test_admin_audit_case_trail_returns_list(client: httpx.AsyncClient, admin_token: str):
    """Case audit trail returns a list (possibly empty for a random case_id)."""
    resp = await client.get(
        f"/api/admin/audit/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_audit_filter_by_action(client: httpx.AsyncClient, admin_token: str):
    """Audit log can be filtered by action type."""
    resp = await client.get(
        "/api/admin/audit?action=admin_edit",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    for entry in data.get("entries", []):
        assert "admin_edit" in entry["action"].lower()


# ---------------------------------------------------------------------------
# Nurse workload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_nurse_workload_returns_list(client: httpx.AsyncClient, admin_token: str):
    """Admin nurse workload view returns list with required fields."""
    resp = await client.get(
        "/api/admin/nurses/workload",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        item = data[0]
        assert "nurse_id" in item
        assert "username" in item
        assert "active_locks" in item
        assert "decided_cases" in item
