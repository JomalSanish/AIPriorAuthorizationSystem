"""
Authentication endpoints.

    POST /api/auth/login    — OAuth2 password flow → access + refresh tokens
    POST /api/auth/refresh  — Refresh token → new access token
    GET  /api/auth/me       — Current user profile

Audit events per FR-040b (failed auth) and FR-040c (cross-role denial) are
logged here and in deps.py.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    TokenDecodeError,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.db.database import get_db
from app.db.models import AuditLog, ActorType, User
from app.api.deps import get_current_active_user

logger = logging.getLogger("pa.auth")
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Helper: write audit log row (fire-and-forget, non-blocking)
# ---------------------------------------------------------------------------

async def _audit(
    db: AsyncSession,
    *,
    action: str,
    actor_id: str,
    metadata: dict | None = None,
) -> None:
    entry = AuditLog(
        trace_id=uuid.uuid4(),
        case_id=None,
        actor_type=ActorType.user,
        actor_id=actor_id,
        action=action,
        timestamp=datetime.now(timezone.utc),
        metadata_=metadata,
    )
    db.add(entry)
    # Commit happens in get_db session cleanup


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse, summary="OAuth2 password login")
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Exchange username + password for access and refresh tokens.

    Logs failed attempts to the audit log (FR-040b).
    """
    result = await db.execute(select(User).where(User.username == form.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form.password, user.hashed_password):
        # Log failed attempt (FR-040b)
        await _audit(
            db,
            action="auth.login.failed",
            actor_id=form.username,
            metadata={"reason": "invalid_credentials"},
        )
        logger.warning("Failed login attempt for username='%s'", form.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        await _audit(
            db,
            action="auth.login.failed",
            actor_id=str(user.id),
            metadata={"reason": "account_deactivated"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    access_token = create_access_token(subject=str(user.id), role=user.role.value)
    refresh_token = create_refresh_token(subject=str(user.id))

    await _audit(db, action="auth.login.success", actor_id=str(user.id))
    logger.info("User %s (%s) logged in", user.username, user.role)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


# ---------------------------------------------------------------------------
# POST /api/auth/refresh
# ---------------------------------------------------------------------------

@router.post("/refresh", response_model=AccessTokenResponse, summary="Refresh access token")
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """
    Exchange a valid refresh token for a new access token.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(body.refresh_token)
    except TokenDecodeError:
        raise credentials_exception

    if payload.type != "refresh":
        raise credentials_exception

    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_exception

    new_access = create_access_token(subject=str(user.id), role=user.role.value)
    return AccessTokenResponse(access_token=new_access)


# ---------------------------------------------------------------------------
# GET /api/auth/me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserProfile, summary="Current user profile")
async def get_me(
    current_user: User = Depends(get_current_active_user),
) -> UserProfile:
    """Return the authenticated user's profile."""
    return UserProfile.model_validate(current_user)
