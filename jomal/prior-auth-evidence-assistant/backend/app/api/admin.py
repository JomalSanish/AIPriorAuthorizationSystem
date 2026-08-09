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
from app.db.models import (
    AuditLog, ActorType, Case, CaseLock, CaseStatus,
    NurseDecision, User, UserRole,
)
from app.services.audit import audit_service

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


# ===========================================================================
# Phase 9 — T068: Admin Case Intervention + All-Cases View
# ===========================================================================

class PatchCaseRequest(BaseModel):
    member_id:    Optional[str] = None
    provider_id:  Optional[str] = None
    cpt_code:     Optional[str] = None
    icd_code:     Optional[str] = None
    service_type: Optional[str] = None


@router.get(
    "/cases",
    summary="All cases — admin overview (Admin only)",
)
async def admin_list_cases(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_guard),
):
    """
    Return every case in the system with status, lock holder, SLA, and policy name.
    Admin oversight view (FR-033).
    """
    from sqlalchemy import outerjoin
    from app.db.models import Policy

    result = await db.execute(
        select(Case, Policy.name.label("policy_name"))
        .join(Policy, Case.policy_id == Policy.id)
        .order_by(Case.created_at.desc())
    )
    rows = result.all()

    items = []
    for case_obj, policy_name in rows:
        # Resolve lock info
        lock_result = await db.execute(
            select(CaseLock, User.username.label("nurse_name"))
            .join(User, CaseLock.nurse_id == User.id)
            .where(CaseLock.case_id == case_obj.id)
        )
        lock_row = lock_result.first()

        items.append({
            "case_id":       str(case_obj.id),
            "policy_name":   policy_name,
            "member_id":     case_obj.member_id,
            "provider_id":   case_obj.provider_id,
            "service_type":  case_obj.service_type,
            "cpt_code":      case_obj.cpt_code,
            "icd_code":      case_obj.icd_code,
            "status":        case_obj.status.value,
            "sla_start_at":  case_obj.sla_start_at,
            "decided_at":    case_obj.decided_at,
            "created_at":    case_obj.created_at,
            "lock_holder":   lock_row.nurse_name if lock_row else None,
            "lock_expires_at": lock_row[0].lock_expires_at if lock_row else None,
        })

    return items


@router.patch(
    "/cases/{case_id}",
    summary="Admin case intervention — edit fields, trigger re-verification (Admin only)",
)
async def admin_patch_case(
    case_id: uuid.UUID,
    body: PatchCaseRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(_admin_guard),
):
    """
    Admin can edit case fields. If case status is accepted/rejected:
      1. Invalidate the NurseDecision (FR-032)
      2. Release any active lock
      3. Transition to re_verification_required
      4. Write audit entries for admin_edit + case_re_verification
    SC-009: All DB changes in a single transaction (fast, < 5s).
    """
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if all(v is None for v in [body.member_id, body.provider_id, body.cpt_code, body.icd_code, body.service_type]):
        raise HTTPException(status_code=400, detail="No fields provided to update")

    trace_id = uuid.uuid4()
    changes: dict = {}

    if body.member_id is not None and body.member_id != case.member_id:
        changes["member_id"] = {"old": case.member_id, "new": body.member_id}
        case.member_id = body.member_id
    if body.provider_id is not None and body.provider_id != case.provider_id:
        changes["provider_id"] = {"old": case.provider_id, "new": body.provider_id}
        case.provider_id = body.provider_id
    if body.cpt_code is not None and body.cpt_code != case.cpt_code:
        changes["cpt_code"] = {"old": case.cpt_code, "new": body.cpt_code}
        case.cpt_code = body.cpt_code
    if body.icd_code is not None and body.icd_code != case.icd_code:
        changes["icd_code"] = {"old": case.icd_code, "new": body.icd_code}
        case.icd_code = body.icd_code
    if body.service_type is not None and body.service_type != case.service_type:
        changes["service_type"] = {"old": case.service_type, "new": body.service_type}
        case.service_type = body.service_type

    re_verified = False

    # If decided — invalidate decision, release lock, re-queue (FR-032, SC-009)
    if case.status in (CaseStatus.accepted, CaseStatus.rejected):
        # Invalidate NurseDecision
        decision_result = await db.execute(
            select(NurseDecision).where(NurseDecision.case_id == case_id)
            .order_by(NurseDecision.decided_at.desc()).limit(1)
        )
        decision = decision_result.scalar_one_or_none()
        if decision:
            # Mark the decision as invalidated via audit (FR-032)
            await audit_service.log(
                db,
                trace_id=trace_id,
                case_id=case_id,
                actor_type=ActorType.user,
                actor_id=str(admin.id),
                action="nurse_decision_invalidated",
                input_summary=f"Decision {decision.decision.value} by nurse {decision.nurse_id} invalidated by admin edit",
                metadata={"decision_id": str(decision.id), "original_decision": decision.decision.value},
            )

        # Release any active lock
        lock_result = await db.execute(
            select(CaseLock).where(CaseLock.case_id == case_id)
        )
        lock = lock_result.scalar_one_or_none()
        if lock:
            await db.delete(lock)

        # Transition to re_verification_required
        case.status = CaseStatus.re_verification_required
        case.decided_at = None
        case.decided_by = None
        case.decision_comment = None
        re_verified = True

    # Audit admin_edit
    await audit_service.log(
        db,
        trace_id=trace_id,
        case_id=case_id,
        actor_type=ActorType.user,
        actor_id=str(admin.id),
        action="admin_edit",
        input_summary=f"Admin {admin.username} edited case fields",
        output_summary=f"Changes: {list(changes.keys())}",
        metadata=changes,
    )

    if re_verified:
        await audit_service.log(
            db,
            trace_id=trace_id,
            case_id=case_id,
            actor_type=ActorType.user,
            actor_id=str(admin.id),
            action="case_re_verification",
            input_summary="Case returned to re_verification_required after admin edit (FR-032)",
        )

    await db.commit()

    return {
        "detail": "Case updated",
        "case_id": str(case_id),
        "status": case.status.value,
        "re_verification_triggered": re_verified,
        "changes": list(changes.keys()),
    }


@router.get(
    "/nurses/workload",
    summary="Per-nurse workload view (Admin only)",
)
async def admin_nurse_workload(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_guard),
):
    """Return each nurse with their currently locked case count and total decided count (FR-033)."""
    from sqlalchemy import func

    nurses_result = await db.execute(
        select(User).where(User.role == UserRole.nurse)
    )
    nurses = nurses_result.scalars().all()

    workload = []
    for nurse in nurses:
        # Active lock count
        lock_result = await db.execute(
            select(func.count()).where(CaseLock.nurse_id == nurse.id)
        )
        active_locks = lock_result.scalar() or 0

        # Total decided cases
        decided_result = await db.execute(
            select(func.count()).where(NurseDecision.nurse_id == nurse.id)
        )
        decided_count = decided_result.scalar() or 0

        workload.append({
            "nurse_id":      str(nurse.id),
            "username":      nurse.username,
            "is_active":     nurse.is_active,
            "active_locks":  active_locks,
            "decided_cases": decided_count,
        })

    return workload


@router.get(
    "/nurses/{nurse_id}/history",
    summary="View any nurse's decision history (Admin only)",
)
async def admin_nurse_history(
    nurse_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_guard),
):
    """Return full decision history for a specific nurse (FR-029a)."""
    from app.db.models import Policy

    result = await db.execute(
        select(NurseDecision, Case, Policy.name.label("policy_name"))
        .join(Case, NurseDecision.case_id == Case.id)
        .join(Policy, Case.policy_id == Policy.id)
        .where(NurseDecision.nurse_id == nurse_id)
        .order_by(NurseDecision.decided_at.desc())
    )

    history = []
    for decision, case_obj, policy_name in result.all():
        history.append({
            "decision_id":  str(decision.id),
            "case_id":      str(case_obj.id),
            "policy_name":  policy_name,
            "service_type": case_obj.service_type,
            "member_id":    case_obj.member_id,
            "decision":     decision.decision.value,
            "comment":      decision.comment,
            "decided_at":   decision.decided_at,
        })

    return history


# ===========================================================================
# Phase 9 — T069: Audit Trail Viewer
# ===========================================================================

@router.get(
    "/audit/{case_id}",
    summary="Chronological audit trail for a case (Admin only)",
)
async def get_case_audit(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_guard),
):
    """Return complete chronological audit trail for a case (FR-041, FR-041a)."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.case_id == case_id)
        .order_by(AuditLog.timestamp.asc())
    )
    logs = result.scalars().all()

    return [
        {
            "id":             str(log.id),
            "trace_id":       str(log.trace_id),
            "timestamp":      log.timestamp,
            "actor_type":     log.actor_type.value,
            "actor_id":       log.actor_id,
            "action":         log.action,
            "model_name":     log.model_name,
            "model_version":  log.model_version,
            "confidence_score": log.confidence_score,
            "retrieval_score":  log.retrieval_score,
            "llm_confidence":   log.llm_confidence,
            "input_summary":  log.input_summary,
            "output_summary": log.output_summary,
            "metadata":       log.metadata_,
        }
        for log in logs
    ]


@router.get(
    "/audit",
    summary="Global audit log with optional filtering (Admin only)",
)
async def get_global_audit(
    action: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_type: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_guard),
):
    """Global audit log. Optional filters: action, actor_id, actor_type, date range."""
    from sqlalchemy import and_

    conditions = []
    if action:
        conditions.append(AuditLog.action.ilike(f"%{action}%"))
    if actor_id:
        conditions.append(AuditLog.actor_id == actor_id)
    if actor_type:
        conditions.append(AuditLog.actor_type == actor_type)
    if from_date:
        conditions.append(AuditLog.timestamp >= from_date)
    if to_date:
        conditions.append(AuditLog.timestamp <= to_date)

    offset = (page - 1) * page_size
    query = (
        select(AuditLog)
        .where(and_(*conditions) if conditions else True)
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    logs = result.scalars().all()

    return {
        "page": page,
        "page_size": page_size,
        "entries": [
            {
                "id":             str(log.id),
                "trace_id":       str(log.trace_id),
                "case_id":        str(log.case_id) if log.case_id else None,
                "timestamp":      log.timestamp,
                "actor_type":     log.actor_type.value,
                "actor_id":       log.actor_id,
                "action":         log.action,
                "model_name":     log.model_name,
                "confidence_score": log.confidence_score,
                "input_summary":  log.input_summary,
                "output_summary": log.output_summary,
            }
            for log in logs
        ],
    }
