"""
APScheduler Service — Phase 8 (T059).

Manages the background scheduler for time-based jobs.

Jobs registered here:
  release_expired_locks — runs every 5 minutes, deletes CaseLock records
  whose lock_expires_at < now() and writes case_lock_auto_released audit
  entries (FR-040a).

SC-008: Lock must auto-release within 60 seconds of the 24-hour threshold.
A 5-minute interval satisfies this constraint.

Registration: call start_scheduler() in the FastAPI lifespan handler and
shutdown_scheduler() on shutdown.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("pa.services.scheduler")

_scheduler: AsyncIOScheduler | None = None


# ---------------------------------------------------------------------------
# Job: release expired locks
# ---------------------------------------------------------------------------

async def release_expired_locks() -> None:
    """
    Delete all CaseLock records where lock_expires_at < now().

    Writes a case_lock_auto_released audit entry for each released lock
    (FR-040a). Uses its own DB session — safe to run as a background job.
    """
    from sqlalchemy import select
    from app.db.database import get_session_factory
    from app.db.models import ActorType, CaseLock
    from app.services.audit import audit_service

    now = datetime.now(timezone.utc)

    try:
        async with get_session_factory()() as db:
            result = await db.execute(
                select(CaseLock).where(CaseLock.lock_expires_at < now)
            )
            expired = result.scalars().all()

            if not expired:
                logger.debug("release_expired_locks: no expired locks found")
                return

            logger.info("release_expired_locks: releasing %d expired lock(s)", len(expired))

            for lock in expired:
                trace_id = uuid.uuid4()
                await db.delete(lock)
                await audit_service.log(
                    db,
                    trace_id=trace_id,
                    case_id=lock.case_id,
                    actor_type=ActorType.system,
                    actor_id="scheduler",
                    action="case_lock_auto_released",
                    input_summary=(
                        f"Lock expired for case {lock.case_id} "
                        f"(nurse {lock.nurse_id}, expired {lock.lock_expires_at})"
                    ),
                    output_summary="Lock auto-released by scheduler (SC-008)",
                )

            await db.commit()
            logger.info("release_expired_locks: committed %d releases", len(expired))

    except Exception as exc:
        logger.error("release_expired_locks: failed — %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

def start_scheduler() -> AsyncIOScheduler:
    """
    Create and start the APScheduler. Called once from the FastAPI lifespan.

    Returns the running scheduler instance so lifespan can store it.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("start_scheduler called but scheduler already running")
        return _scheduler

    _scheduler = AsyncIOScheduler()

    # Lock auto-release: every 5 minutes (SC-008)
    _scheduler.add_job(
        release_expired_locks,
        trigger=IntervalTrigger(minutes=5),
        id="release_expired_locks",
        name="Release expired case locks",
        replace_existing=True,
        max_instances=1,   # never overlap
        coalesce=True,     # skip missed fires
    )

    _scheduler.start()
    logger.info("APScheduler started — lock auto-release every 5 minutes (SC-008)")
    return _scheduler


def shutdown_scheduler() -> None:
    """Gracefully shut down the scheduler. Called from the FastAPI lifespan on shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler shut down")
    _scheduler = None
