"""
Startup health-check utilities.

Checks all infrastructure dependencies:
  - PostgreSQL  (asyncpg connection test)
  - Qdrant      (HTTP GET /healthz)
  - TEI         (HTTP GET /health + test embedding call)
  - MinIO       (boto3 list_buckets)
  - Ollama      (HTTP GET /api/tags — verifies llama3.2:3b is present)

⚠️ Ollama health check verifies the model is ALREADY pulled — it must NOT
trigger a `ollama pull`. Model weights must be pre-installed on the host.
See docker/README.md for setup instructions.

run_all_checks() raises on any failure; the FastAPI lifespan handler calls
this at startup so the server won't accept traffic if infrastructure is down.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import get_settings

logger = logging.getLogger("pa.healthcheck")


class HealthResult(NamedTuple):
    service: str
    ok: bool
    detail: str


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

async def check_postgres() -> HealthResult:
    """Verify PostgreSQL is reachable with the configured credentials."""
    from app.db.database import get_engine

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return HealthResult("postgres", True, "OK")
    except OperationalError as exc:
        return HealthResult("postgres", False, str(exc))
    except Exception as exc:  # noqa: BLE001
        return HealthResult("postgres", False, f"Unexpected error: {exc}")


async def check_qdrant() -> HealthResult:
    """Verify Qdrant health endpoint responds 200."""
    settings = get_settings()
    url = f"{settings.QDRANT_URL}/healthz"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        return HealthResult("qdrant", True, "OK")
    except httpx.HTTPError as exc:
        return HealthResult("qdrant", False, str(exc))
    except Exception as exc:  # noqa: BLE001
        return HealthResult("qdrant", False, f"Unexpected error: {exc}")


async def check_tei() -> HealthResult:
    """
    Verify TEI health endpoint responds 200 and run a test embedding call.
    """
    settings = get_settings()
    health_url = f"{settings.TEI_URL}/health"
    embed_url = f"{settings.TEI_URL}/embed"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Health check
            resp = await client.get(health_url)
            resp.raise_for_status()

            # Test embedding (single short string)
            embed_resp = await client.post(
                embed_url,
                json={"inputs": "health check"},
            )
            embed_resp.raise_for_status()
            data = embed_resp.json()
            if not data or not isinstance(data, list):
                return HealthResult("tei", False, "Unexpected embedding response shape")

        return HealthResult("tei", True, "OK")
    except httpx.HTTPError as exc:
        return HealthResult("tei", False, str(exc))
    except Exception as exc:  # noqa: BLE001
        return HealthResult("tei", False, f"Unexpected error: {exc}")


async def check_minio() -> HealthResult:
    """
    Verify MinIO is reachable via boto3 (S3-compatible).

    ⚠️ endpoint_url MUST be set to the local MinIO URL — never falls back
    to s3.amazonaws.com (FR-043, external network prohibition).
    """
    settings = get_settings()
    try:
        import asyncio

        loop = asyncio.get_event_loop()

        def _sync_check():
            s3 = boto3.client(
                "s3",
                endpoint_url=settings.MINIO_ENDPOINT,
                aws_access_key_id=settings.MINIO_ACCESS_KEY,
                aws_secret_access_key=settings.MINIO_SECRET_KEY,
                region_name="us-east-1",  # required by boto3; ignored by MinIO
            )
            s3.list_buckets()

        await loop.run_in_executor(None, _sync_check)
        return HealthResult("minio", True, "OK")
    except (BotoCoreError, ClientError) as exc:
        return HealthResult("minio", False, str(exc))
    except Exception as exc:  # noqa: BLE001
        return HealthResult("minio", False, f"Unexpected error: {exc}")


async def check_ollama() -> HealthResult:
    """
    Verify Ollama is running on the host and llama3.2:3b is available.

    This check ONLY reads /api/tags — it does NOT trigger a model pull.
    If the model is absent, returns a descriptive failure so the operator
    knows to run `ollama pull llama3.2:3b` manually.
    """
    settings = get_settings()
    url = f"{settings.OLLAMA_URL}/api/tags"
    required_model = "llama3.2:3b"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        models = [m.get("name", "") for m in data.get("models", [])]
        # Model names in Ollama can be "llama3.2:3b" or "llama3.2:3b-instruct-q4_K_M"
        found = any(required_model in m for m in models)
        if not found:
            return HealthResult(
                "ollama",
                False,
                f"Model '{required_model}' not found. Available: {models}. "
                "Run: ollama pull llama3.2:3b",
            )
        return HealthResult("ollama", True, f"OK — {required_model} present")
    except httpx.HTTPError as exc:
        return HealthResult(
            "ollama",
            False,
            f"Ollama unreachable at {settings.OLLAMA_URL}: {exc}. "
            "Is Ollama running natively on the host?",
        )
    except Exception as exc:  # noqa: BLE001
        return HealthResult("ollama", False, f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

async def run_all_checks(raise_on_failure: bool = True) -> list[HealthResult]:
    """
    Run all five health checks and return results.

    Parameters
    ----------
    raise_on_failure
        If True (default), raises ``RuntimeError`` listing failed services.

    Returns
    -------
    list[HealthResult]
        Results for all five services.
    """
    import asyncio

    results = await asyncio.gather(
        check_postgres(),
        check_qdrant(),
        check_tei(),
        check_minio(),
        check_ollama(),
    )

    for r in results:
        level = logging.INFO if r.ok else logging.ERROR
        logger.log(level, "health_check service=%s ok=%s detail=%s", r.service, r.ok, r.detail)

    if raise_on_failure:
        failures = [r for r in results if not r.ok]
        if failures:
            names = ", ".join(r.service for r in failures)
            raise RuntimeError(
                f"Infrastructure health check failed for: {names}. "
                "Check logs for details."
            )

    return list(results)
