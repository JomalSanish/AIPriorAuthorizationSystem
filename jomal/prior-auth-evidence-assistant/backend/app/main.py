"""
FastAPI application entry point.

Startup sequence (T091 — Phase 11):
  1. Load settings from SecretsProvider (validates all env vars)
  2. Infrastructure health checks with retry (Postgres → Qdrant → TEI → MinIO → Ollama)
  3. Run Alembic migrations to ensure schema is current
  4. Ensure MinIO buckets exist
  5. Ensure Qdrant collection exists
  6. Start APScheduler (lock auto-release, T059)
  7. Log startup complete with service summary

If any step fails after retries the process exits with a non-zero code so
container orchestrators (Docker Compose / systemd) can restart the service.

CORS: localhost-only origins in dev. Do NOT open to wildcard (*).
"""

from __future__ import annotations

import asyncio
import logging
import logging.config
import sys
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, admin, policies, cases, nurse_review
from app.config import get_settings

logger = logging.getLogger("pa.main")

# ---------------------------------------------------------------------------
# Startup retry configuration
# ---------------------------------------------------------------------------

_RETRY_ATTEMPTS = 3
_RETRY_INTERVAL_SECONDS = 5


# ---------------------------------------------------------------------------
# Logging configuration (structured, goes to stdout for Docker/systemd)
# ---------------------------------------------------------------------------

def _configure_logging() -> None:
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s %(name)s — %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["console"],
            },
            # Security-specific logger — separate handler in production
            "loggers": {
                "pa.security.secrets": {"level": "INFO", "propagate": True},
                "pa.auth": {"level": "INFO", "propagate": True},
            },
        }
    )


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

async def _with_retry(name: str, coro_fn, attempts: int = _RETRY_ATTEMPTS, interval: float = _RETRY_INTERVAL_SECONDS):
    """
    Retry ``coro_fn()`` up to ``attempts`` times with ``interval``-second pauses.

    Raises the last exception if all attempts fail, with a clear log line
    identifying which service blocked startup.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await coro_fn()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning(
                "startup service=%s attempt=%d/%d failed: %s",
                name,
                attempt,
                attempts,
                exc,
            )
            if attempt < attempts:
                await asyncio.sleep(interval)

    logger.error(
        "startup service=%s FAILED after %d attempts — cannot continue",
        name,
        attempts,
    )
    raise RuntimeError(f"Service '{name}' failed to become healthy after {attempts} attempts") from last_exc


# ---------------------------------------------------------------------------
# Startup steps
# ---------------------------------------------------------------------------

async def _check_infrastructure() -> None:
    """Run all five health checks with retry in the required order (T091)."""
    from app.core.healthcheck import (
        check_postgres,
        check_qdrant,
        check_tei,
        check_minio,
        check_ollama,
        HealthResult,
    )

    async def _check_and_raise(check_fn) -> None:
        result: HealthResult = await check_fn()
        if not result.ok:
            raise RuntimeError(result.detail)
        logger.info("health_check service=%s ok=True detail=%s", result.service, result.detail)

    # Ordered boot: Postgres first (DB is required by migrations), then the rest
    await _with_retry("postgres", lambda: _check_and_raise(check_postgres))
    await _with_retry("qdrant",   lambda: _check_and_raise(check_qdrant))
    await _with_retry("tei",      lambda: _check_and_raise(check_tei))
    await _with_retry("minio",    lambda: _check_and_raise(check_minio))
    await _with_retry("ollama",   lambda: _check_and_raise(check_ollama))


async def _run_migrations() -> None:
    """Run Alembic migrations to ensure the schema is current (T091 step 4)."""
    import asyncio as _asyncio
    from alembic import command as alembic_cmd
    from alembic.config import Config as AlembicConfig

    def _sync_migrate() -> None:
        # Alembic config is relative to the backend/ directory (where alembic.ini lives)
        cfg = AlembicConfig("alembic.ini")
        alembic_cmd.upgrade(cfg, "head")

    loop = _asyncio.get_event_loop()
    await loop.run_in_executor(None, _sync_migrate)
    logger.info("startup alembic=migrations status=current")


async def _ensure_minio_buckets() -> None:
    """Ensure required MinIO buckets exist (T091 step 5 / T018)."""
    from app.services.minio import MinioService
    import asyncio as _asyncio

    svc = MinioService()
    loop = _asyncio.get_event_loop()

    for bucket in ("pa-case-documents", "pa-policy-documents"):
        await loop.run_in_executor(None, svc.ensure_bucket, bucket)
        logger.info("startup minio bucket=%s status=ready", bucket)


async def _ensure_qdrant_collection() -> None:
    """Ensure the Qdrant collection exists with correct vector configs (T091 step 6 / T029)."""
    from app.services.qdrant import QdrantService

    svc = QdrantService()
    await svc.ensure_collection()
    logger.info("startup qdrant collection=%s status=ready", QdrantService.COLLECTION_NAME)


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup order (T091):
      1. Load settings (validated at import time via Pydantic)
      2. Infrastructure health checks with retry (Postgres → Qdrant → TEI → MinIO → Ollama)
      3. Alembic migrations
      4. MinIO bucket initialisation
      5. Qdrant collection initialisation
      6. APScheduler start
      7. Startup complete log

    On any failure: logs the error and exits with code 1 so the process
    manager restarts the container / service.

    Shutdown:
      - Stop APScheduler
      - Close DB connection pool
    """
    _configure_logging()
    settings = get_settings()  # noqa: F841 — validates env vars; raises on bad config

    logger.info("PA Evidence Assistant starting up — version=0.1.0")

    try:
        # Step 2: Infrastructure health checks
        logger.info("startup step=2 action=infrastructure_health_checks")
        await _check_infrastructure()

        # Step 3: Alembic migrations
        logger.info("startup step=3 action=alembic_migrations")
        try:
            await _run_migrations()
        except Exception as exc:  # noqa: BLE001
            # Migration failures are fatal in production but should not block
            # the dev feedback loop. Log as error and continue.
            logger.error("startup alembic migrations failed (non-fatal in dev): %s", exc)

        # Step 4: MinIO buckets
        logger.info("startup step=4 action=ensure_minio_buckets")
        try:
            await _ensure_minio_buckets()
        except Exception as exc:  # noqa: BLE001
            logger.error("startup minio bucket initialisation failed: %s", exc)

        # Step 5: Qdrant collection
        logger.info("startup step=5 action=ensure_qdrant_collection")
        try:
            await _ensure_qdrant_collection()
        except Exception as exc:  # noqa: BLE001
            logger.error("startup qdrant collection initialisation failed: %s", exc)

        # Step 6: APScheduler (lock auto-release, T059)
        logger.info("startup step=6 action=start_apscheduler")
        try:
            from app.services.scheduler import start_scheduler
            start_scheduler()
        except Exception as exc:
            logger.error("APScheduler failed to start: %s", exc)

        # Step 7: Startup complete
        logger.info(
            "startup step=7 status=READY "
            "services=postgres,qdrant,tei,minio,ollama "
            "version=0.1.0"
        )

    except RuntimeError as exc:
        # A required service is down after all retries — fail fast.
        logger.critical(
            "startup FATAL: %s — exiting with code 1 so process manager can restart", exc
        )
        sys.exit(1)

    yield

    # Shutdown
    logger.info("PA Evidence Assistant shutting down...")
    try:
        from app.services.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception as exc:  # noqa: BLE001
        logger.warning("APScheduler shutdown error: %s", exc)

    try:
        from app.db.database import get_engine
        await get_engine().dispose()
    except Exception as exc:  # noqa: BLE001
        logger.warning("DB connection pool dispose error: %s", exc)

    logger.info("PA Evidence Assistant shut down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Prior Authorization Evidence Assistant",
        description=(
            "On-prem payer-side PA assistant. "
            "All inference runs locally — zero external data egress."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — localhost-only origins (FR-043, Constitution P2)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(auth.router)
    app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
    app.include_router(policies.router, prefix="/api/policies", tags=["policies"])
    app.include_router(cases.router, prefix="/api/cases", tags=["cases"])
    app.include_router(nurse_review.router, prefix="/api/nurse-review", tags=["nurse-review"])

    # ---------------------------------------------------------------------------
    # Health endpoint — external monitoring (T091)
    # ---------------------------------------------------------------------------
    @app.get("/api/health", tags=["system"], summary="Infrastructure health probe")
    async def health() -> dict[str, Any]:
        """
        Returns the live status of all five infrastructure services.

        Response shape::

            {
              "status": "ok" | "degraded",
              "services": {
                "postgres": {"ok": true,  "detail": "OK"},
                "qdrant":   {"ok": true,  "detail": "OK"},
                "tei":      {"ok": false, "detail": "<error message>"},
                "minio":    {"ok": true,  "detail": "OK"},
                "ollama":   {"ok": true,  "detail": "OK — llama3.2:3b present"}
              }
            }

        HTTP 200 is always returned — inspect ``status`` and per-service
        ``ok`` fields for the actual health signal.  This matches the
        convention expected by Docker Compose health checks and Kubernetes
        liveness probes.
        """
        from app.core.healthcheck import run_all_checks
        results = await run_all_checks(raise_on_failure=False)
        return {
            "status": "ok" if all(r.ok for r in results) else "degraded",
            "services": {r.service: {"ok": r.ok, "detail": r.detail} for r in results},
        }

    return app


# Module-level app instance (used by uvicorn)
app = create_app()
