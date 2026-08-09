"""
Shared pytest fixtures for unit and integration tests.
Uses pytest-asyncio with asyncio_mode = "auto".
"""
import asyncio
import sys
import os
import uuid
import pytest
import pytest_asyncio

# Ensure backend/ is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Async event loop fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Single session-scoped event loop."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
