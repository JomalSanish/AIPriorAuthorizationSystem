"""
Async SQLAlchemy engine, session factory, and FastAPI dependency.

Uses asyncpg driver for full async support. Connection pool defaults are
conservative for a single-instance deployment; tune via DATABASE_URL params
if needed.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def _build_engine():
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,       # detect stale connections
        pool_size=10,
        max_overflow=20,
    )


# Lazily created so tests can override before first use.
_engine = None
_session_factory = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = _build_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a database session for the duration of a request.

    Usage::

        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...

    Commit behaviour on error
    --------------------------
    A raised ``HTTPException`` represents a *controlled* application-level
    rejection (bad credentials, role denial, validation failure, etc.),
    not a crash. Several endpoints intentionally write an audit-log row
    (e.g. FR-040b failed-auth, FR-040c cross-role denial) and then raise
    such an exception in the same request — the audit trail is only
    useful if that row survives the rejection. So we still COMMIT on
    ``HTTPException``. Any other, unexpected exception still triggers a
    full rollback so a genuine bug can never leave partial writes behind.
    """
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except HTTPException:
            await session.commit()
            raise
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
