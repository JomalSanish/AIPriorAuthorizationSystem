"""
Integration test conftest — provides a shared async HTTP client
against the real FastAPI ASGI app using httpx.ASGITransport.

Works with httpx >= 0.20 which removed the legacy `app=` argument.
"""
import sys
import os
import pytest
import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app.main import app


@pytest.fixture
def client():
    """Async HTTPX client wired directly to the ASGI app (no network needed)."""
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def _login(client: httpx.AsyncClient, username: str, password: str = "password123") -> str:
    resp = await client.post("/api/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
async def admin_token(client):
    return await _login(client, "admin_user")


@pytest.fixture
async def nurse_token(client):
    return await _login(client, "nurse_user")


@pytest.fixture
async def intake_token(client):
    return await _login(client, "intake_user")
