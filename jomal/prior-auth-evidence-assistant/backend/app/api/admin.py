"""
Admin user-management endpoints.

All routes require the ``admin`` role (FR-003).

    POST   /api/admin/users             — Create user
    GET    /api/admin/users             — List all users
    PATCH  /api/admin/users/{user_id}   — Deactivate / re-activate user
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, require_role
from app.core.security import hash_password
from app.db.database import get_db
from app.db.models import AuditLog, ActorType, User, UserRole

logger = logging.getLogger("pa.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])

# Shared guard: Admin only
_admin_guard = require_role("admin")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: UserRole


class PatchUserRequest(BaseModel):
    is_active: bool


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# POST /api/admin/users
# ---------------------------------------------------------------------------

@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user (Admin only)",
)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_admin_guard),
) -> UserOut:
    """Create a new Intake, Nurse, or Admin account."""
    # Check username uniqueness
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{body.username}' already exists",
        )

    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()  # populate user.id before audit log

    # Audit (FR-040a)
    db.add(AuditLog(
        trace_id=uuid.uuid4(),
        actor_type=ActorType.user,
        actor_id=str(admin.id),
        action="admin.user.create",
        timestamp=datetime.now(timezone.utc),
        metadata_={"new_user_id": str(user.id), "role": body.role.value},
    ))

    logger.info("Admin %s created user %s (%s)", admin.id, user.username, user.role)
    return UserOut.model_validate(user)


# ---------------------------------------------------------------------------
# GET /api/admin/users
# ---------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=list[UserOut],
    summary="List all users (Admin only)",
)
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_guard),
) -> list[UserOut]:
    """Return all users in the system."""
    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()
    return [UserOut.model_validate(u) for u in users]


# ---------------------------------------------------------------------------
# PATCH /api/admin/users/{user_id}
# ---------------------------------------------------------------------------

@router.patch(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Activate or deactivate a user (Admin only)",
)
async def patch_user(
    user_id: uuid.UUID,
    body: PatchUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_admin_guard),
) -> UserOut:
    """Deactivate or reactivate a user account."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    old_status = user.is_active
    user.is_active = body.is_active

    action = "admin.user.activate" if body.is_active else "admin.user.deactivate"
    db.add(AuditLog(
        trace_id=uuid.uuid4(),
        actor_type=ActorType.user,
        actor_id=str(admin.id),
        action=action,
        timestamp=datetime.now(timezone.utc),
        metadata_={"target_user_id": str(user_id), "old_status": old_status, "new_status": body.is_active},
    ))

    logger.info("Admin %s set user %s is_active=%s", admin.id, user_id, body.is_active)
    return UserOut.model_validate(user)
