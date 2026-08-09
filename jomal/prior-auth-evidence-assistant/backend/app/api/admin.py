"""
Admin user-management endpoints.

All routes require the ``admin`` role (FR-003).

    POST   /api/admin/users                       — Create user
    GET    /api/admin/users                        — List all users
    PATCH  /api/admin/users/{user_id}               — Update username/role/is_active
    POST   /api/admin/users/{user_id}/reset-password — Admin-issued password reset

Both PATCH and reset-password are blocked from targeting the caller's own account when
the change would remove their own admin access or deactivate themselves — see
``_guard_against_self_lockout`` — to prevent an Admin from accidentally locking
themselves out with no other Admin account to recover through.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, require_role
from app.core.security import hash_password
from app.db.database import get_db
from app.db.models import AuditLog, ActorType, User, UserRole

logger = logging.getLogger("pa.admin")
router = APIRouter(tags=["admin"])

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
    """
    Partial update. Every field is optional so a caller can update just one
    attribute (e.g. only `role`) without resending the others. At least one
    field must be provided.
    """
    username: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# Helper: block an Admin from locking themselves out
# ---------------------------------------------------------------------------

def _guard_against_self_lockout(
    admin: User,
    target_user_id: uuid.UUID,
    *,
    new_role: Optional[UserRole] = None,
    new_is_active: Optional[bool] = None,
) -> None:
    """
    Prevent an Admin from deactivating their own account or demoting themselves
    out of the admin role. Both would leave the account with no way to undo the
    change through the same API (no self-service reactivation/role-change path
    exists by design — see the "no self-service" note in this project's spec).
    """
    if target_user_id != admin.id:
        return
    if new_is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account.",
        )
    if new_role is not None and new_role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role away from admin.",
        )


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
    summary="Update a user's username, role, and/or active status (Admin only)",
)
async def patch_user(
    user_id: uuid.UUID,
    body: PatchUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_admin_guard),
) -> UserOut:
    """
    Partially update a user account: username, role, and/or is_active.
    Any combination of fields may be provided; at least one is required.

    Blocked from letting an Admin deactivate their own account or change their
    own role away from admin (see ``_guard_against_self_lockout``).
    """
    if body.username is None and body.role is None and body.is_active is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of username, role, or is_active must be provided.",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    _guard_against_self_lockout(
        admin, user_id, new_role=body.role, new_is_active=body.is_active,
    )

    changes: dict[str, dict[str, object]] = {}

    if body.username is not None and body.username != user.username:
        existing = await db.execute(
            select(User).where(User.username == body.username, User.id != user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username '{body.username}' already exists",
            )
        changes["username"] = {"old": user.username, "new": body.username}
        user.username = body.username

    if body.role is not None and body.role != user.role:
        changes["role"] = {"old": user.role.value, "new": body.role.value}
        user.role = body.role

    if body.is_active is not None and body.is_active != user.is_active:
        changes["is_active"] = {"old": user.is_active, "new": body.is_active}
        user.is_active = body.is_active

    if changes:
        # Distinguish activate/deactivate as its own action for easy audit filtering,
        # everything else (username/role) rolls up under a general update action.
        if set(changes.keys()) == {"is_active"}:
            action = "admin.user.activate" if body.is_active else "admin.user.deactivate"
        else:
            action = "admin.user.update"

        db.add(AuditLog(
            trace_id=uuid.uuid4(),
            actor_type=ActorType.user,
            actor_id=str(admin.id),
            action=action,
            timestamp=datetime.now(timezone.utc),
            metadata_={"target_user_id": str(user_id), "changes": changes},
        ))
        logger.info("Admin %s updated user %s: %s", admin.id, user_id, changes)

    return UserOut.model_validate(user)


# ---------------------------------------------------------------------------
# POST /api/admin/users/{user_id}/reset-password
# ---------------------------------------------------------------------------

@router.post(
    "/users/{user_id}/reset-password",
    response_model=MessageResponse,
    summary="Reset a user's password (Admin only)",
)
async def reset_password(
    user_id: uuid.UUID,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_admin_guard),
) -> MessageResponse:
    """
    Admin-issued password reset. The new password is never logged or echoed
    back — only the fact that a reset occurred, consistent with FR-040f's
    "log access, never the value" pattern already used for secrets access.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.hashed_password = hash_password(body.new_password)

    db.add(AuditLog(
        trace_id=uuid.uuid4(),
        actor_type=ActorType.user,
        actor_id=str(admin.id),
        action="admin.user.password_reset",
        timestamp=datetime.now(timezone.utc),
        metadata_={"target_user_id": str(user_id)},  # never the password itself
    ))

    logger.info("Admin %s reset password for user %s", admin.id, user_id)
    return MessageResponse(message=f"Password reset for user {user.username}.")
