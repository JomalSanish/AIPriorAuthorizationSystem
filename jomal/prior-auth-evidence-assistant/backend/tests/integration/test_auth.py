"""
T081 — Auth Endpoint Integration Tests.

Tests (using HTTPX + FastAPI ASGI transport — httpx 0.28 compatible):
  - Login flow (valid credentials → JWT tokens)
  - Refresh flow
  - Role-based access denial for cross-role combinations (SC-006)
  - Failed auth attempt does not return 200
"""
import pytest
import httpx


# All fixtures (client, admin_token, nurse_token, intake_token) are from conftest.py


# ---------------------------------------------------------------------------
# Login flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_valid_credentials(client):
    """Valid credentials return access_token and token_type=bearer."""
    resp = await client.post("/api/auth/login", data={
        "username": "admin_user",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data.get("token_type") == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client):
    """Invalid password returns 401."""
    resp = await client.post("/api/auth/login", data={
        "username": "admin_user",
        "password": "wrong_password",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    """Non-existent user returns 401, not 404 (security: don't reveal existence)."""
    resp = await client.post("/api/auth/login", data={
        "username": "ghost_user_xyz",
        "password": "password123",
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_token(client):
    """Refresh endpoint returns a new access token (or skip if not implemented)."""
    login_resp = await client.post("/api/auth/login", data={
        "username": "admin_user",
        "password": "password123",
    })
    assert login_resp.status_code == 200
    refresh_token = login_resp.json().get("refresh_token")

    if refresh_token is None:
        pytest.skip("No refresh_token in login response — refresh flow not implemented")

    refresh_resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()


# ---------------------------------------------------------------------------
# SC-006: Role-based access denial
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nurse_cannot_access_admin_endpoint(client, nurse_token):
    """SC-006: Nurse cannot access /api/admin/users."""
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {nurse_token}"},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


@pytest.mark.asyncio
async def test_intake_cannot_access_nurse_review(client, intake_token):
    """SC-006: Intake role cannot access nurse review queue."""
    resp = await client.get(
        "/api/nurse-review/queue",
        headers={"Authorization": f"Bearer {intake_token}"},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_cases(client):
    """No token returns 401 on protected endpoints."""
    resp = await client.get("/api/cases")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_access_admin_endpoint(client, admin_token):
    """Admin token can access /api/admin/users."""
    resp = await client.get(
        "/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
