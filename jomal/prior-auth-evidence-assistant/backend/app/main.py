"""
FastAPI application entry point.

Startup sequence:
  1. Load settings (validates env vars)
  2. Run infrastructure health checks (fail fast if any service is down)
  3. Start APScheduler (Phase 7 — lock auto-release)

CORS: localhost-only origins in dev. Do NOT open to wildcard (*).
"""

from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, admin, policies
from app.config import get_settings

logger = logging.getLogger("pa.main")


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
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.

    Startup:
      - Validate infrastructure (fail fast)
      - (Future) Start APScheduler

    Shutdown:
      - Close DB connection pool
      - (Future) Shutdown APScheduler
    """
    _configure_logging()
    settings = get_settings()

    logger.info("PA Evidence Assistant starting up...")

    # Infrastructure health checks — non-fatal in development (log only)
    # In production, set raise_on_failure=True to fail hard if any service
    # is not reachable.
    try:
        from app.core.healthcheck import run_all_checks
        await run_all_checks(raise_on_failure=False)
    except Exception as exc:  # noqa: BLE001
        logger.error("Health check error during startup: %s", exc)

    logger.info("PA Evidence Assistant ready.")

    yield

    # Shutdown
    from app.db.database import get_engine
    await get_engine().dispose()
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
    app.include_router(admin.router)
    app.include_router(policies.router, prefix="/api/policies", tags=["policies"])

    # Root health endpoint
    @app.get("/health", tags=["system"], summary="Application health probe")
    async def health() -> dict[str, Any]:
        from app.core.healthcheck import run_all_checks
        results = await run_all_checks(raise_on_failure=False)
        return {
            "status": "ok" if all(r.ok for r in results) else "degraded",
            "services": {r.service: {"ok": r.ok, "detail": r.detail} for r in results},
        }

    return app


# Module-level app instance (used by uvicorn)
app = create_app()
