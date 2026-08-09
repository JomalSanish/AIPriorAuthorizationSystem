"""
FastAPI authentication dependencies and role-based access control.

Usage::

    @router.get("/cases")
    async def list_cases(
        current_user: User = Depends(get_current_active_user),
        _: None = Depends(require_role("intake", "admin")),
    ):
        ...

Scope enumeration per role (FR-003a):
    Intake  → case:create, case:read, document:upload, policy:read
    Nurse   → case:read, case:lock, case:decide, history:read
    Admin   → case:*, policy:*, user:manage, audit:read, history:read
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenDecodeError, decode_token
from app.db.database import get_db
from app.db.models import ActorType, User
from app.services.audit import audit_service

logger = logging.getLogger("pa.auth")

# OAuth2 scheme — points at our login endpoint
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ---------------------------------------------------------------------------
# Core dependency: get_current_user
# ---------------------------------------------------------------------------

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Decode the bearer token and return the authenticated User.

    Raises
    ------
    401 Unauthorized
        If the token is missing, malformed, expired, or the user doesn't exist.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
    except TokenDecodeError as exc:
        logger.warning("JWT decode failure: %s", exc)
        raise credentials_exception from exc

    if payload.type != "access":
        logger.warning("Non-access token used in Bearer header")
        raise credentials_exception

    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception

    return user


# ---------------------------------------------------------------------------
# Active-user guard
# ---------------------------------------------------------------------------

async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Like :func:`get_current_user` but additionally rejects deactivated users.

    Raises
    ------
    403 Forbidden
        If the user's ``is_active`` flag is False.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return current_user


# ---------------------------------------------------------------------------
# Role guard factory
# ---------------------------------------------------------------------------

def require_role(*roles: str) -> Callable:
    """
    Return a FastAPI dependency that enforces role membership.

    Parameters
    ----------
    *roles
        One or more role strings (e.g. ``"admin"``, ``"nurse"``).

    Usage::

        @router.post("/admin/users")
        async def create_user(
            _: User = Depends(require_role("admin")),
        ): ...

    Raises
    ------
    403 Forbidden
        If the current user's role is not in *roles*.
    """
    async def _dependency(
        current_user: User = Depends(get_current_active_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.role.value not in roles:
            logger.warning(
                "Role access denied: user=%s role=%s required=%s",
                current_user.id,
                current_user.role,
                roles,
            )
            # FR-040c: denied cross-role access attempts must be recorded
            # in the audit trail (actor identity, attempted resource,
            # timestamp) — not just the application log. get_db() commits
            # on HTTPException specifically so this row survives the
            # 403 raised immediately below.
            await audit_service.log(
                db,
                trace_id=uuid.uuid4(),
                case_id=None,
                actor_type=ActorType.user,
                actor_id=str(current_user.id),
                action="access_denial",
                input_summary=f"Attempted access requiring role(s): {list(roles)}",
                output_summary=f"Denied — actual role: {current_user.role.value}",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(roles)}",
            )
        return current_user

    return _dependency
