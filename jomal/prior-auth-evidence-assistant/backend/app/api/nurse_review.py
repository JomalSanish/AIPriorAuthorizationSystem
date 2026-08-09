"""
Nurse Review API — Phase 8 (T058, T060).

Endpoints:
  GET  /api/nurse-review/queue       — metadata-only queue (no summary/docs before lock) FR-023
  POST /api/nurse-review/{case_id}/lock   — claim a case for review (FR-025)
  DELETE /api/nurse-review/{case_id}/lock — release a case lock
  POST /api/nurse-review/{case_id}/decide — accept/reject with mandatory comment (FR-028)
  GET  /api/nurse-review/history          — decided cases for this nurse (or any nurse for Admin)

Governance:
  FR-023 — summary/evidence/documents are NEVER returned to a nurse before she locks the case.
  FR-025 — 409 if case already locked by another nurse.
  FR-028 — comment is mandatory; empty comment is rejected.
  FR-029a — nurses see own history; admin can specify ?nurse_id= to see any nurse's history.
  FR-040a / FR-040d — audit entries written for lock, unlock, and nurse_decision events.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import (
    ActorType, AuditLog, Case, CaseLock, CaseStatus,
    NurseDecision, NurseDecisionEnum, Policy, User,
)
from app.api.deps import get_current_user, require_role
from app.agents.workflow import workflow_agent
from app.services.audit import audit_service

logger = logging.getLogger("pa.api.nurse_review")

router = APIRouter()

LOCK_DURATION_HOURS = 24


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# T058a — GET /queue  (metadata-only, FR-023)
# ---------------------------------------------------------------------------

@router.get("/queue", dependencies=[Depends(require_role("nurse", "admin"))])
async def get_review_queue(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return cases awaiting nurse review.

    Metadata only — no AI summaries or document content (FR-023).
    Statuses included: pending_nurse_review, error, re_verification_required
    (FR-032 — admin-edited cases are routed straight back to the queue).
    """
    result = await db.execute(
        select(Case, Policy.name.label("policy_name"))
        .join(Policy, Case.policy_id == Policy.id)
        .where(Case.status.in_([
            CaseStatus.pending_nurse_review,
            CaseStatus.error,
            CaseStatus.re_verification_required,
        ]))
        .order_by(Case.sla_start_at.asc().nullslast())
    )
    rows = result.all()

    queue = []
    for case_obj, policy_name in rows:
        # Resolve lock info
        lock_result = await db.execute(
            select(CaseLock).where(CaseLock.case_id == case_obj.id)
        )
        lock = lock_result.scalar_one_or_none()

        locked_by_me = lock and lock.nurse_id == current_user.id
        locked_by_other = lock and lock.nurse_id != current_user.id

        queue.append({
            "case_id":            str(case_obj.id),
            "policy_name":        policy_name,
            "member_id":          case_obj.member_id,
            "provider_id":        case_obj.provider_id,
            "service_type":       case_obj.service_type,
            "cpt_code":           case_obj.cpt_code,
            "icd_code":           case_obj.icd_code,
            "status":             case_obj.status.value,
            "sla_start_at":       case_obj.sla_start_at,
            "created_at":         case_obj.created_at,
            "is_locked_by_me":    locked_by_me,
            "is_locked_by_other": locked_by_other,
            "lock_expires_at":    lock.lock_expires_at if lock else None,
        })

    return queue


# ---------------------------------------------------------------------------
# T058b — POST /lock  (claim case, FR-025)
# ---------------------------------------------------------------------------

@router.post("/{case_id}/lock", dependencies=[Depends(require_role("nurse", "admin"))])
async def lock_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Claim a case for review. 409 if already locked by another nurse (FR-025).
    """
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status not in (
        CaseStatus.pending_nurse_review,
        CaseStatus.error,
        CaseStatus.re_verification_required,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Case is not in a reviewable state (status={case.status.value})"
        )

    # Check for existing lock
    lock_result = await db.execute(
        select(CaseLock).where(CaseLock.case_id == case_id)
    )
    existing_lock = lock_result.scalar_one_or_none()

    if existing_lock:
        if existing_lock.nurse_id == current_user.id:
            # Re-locking own case — extend expiry
            existing_lock.lock_expires_at = _utcnow() + timedelta(hours=LOCK_DURATION_HOURS)
            await db.commit()
            return {"detail": "Lock extended", "lock_expires_at": existing_lock.lock_expires_at}
        else:
            raise HTTPException(status_code=409, detail="Case is already locked by another nurse (FR-025)")

    # Create new lock
    lock = CaseLock(
        case_id=case_id,
        nurse_id=current_user.id,
        locked_at=_utcnow(),
        lock_expires_at=_utcnow() + timedelta(hours=LOCK_DURATION_HOURS),
    )
    db.add(lock)

    trace_id = uuid.uuid4()
    await audit_service.log(
        db,
        trace_id=trace_id,
        case_id=case_id,
        actor_type=ActorType.user,
        actor_id=str(current_user.id),
        action="case_locked",
        input_summary=f"Nurse {current_user.username} locked case {case_id}",
        output_summary=f"Lock expires at {lock.lock_expires_at}",
    )

    await db.commit()
    return {
        "detail": "Case locked",
        "case_id": str(case_id),
        "lock_expires_at": lock.lock_expires_at,
    }


# ---------------------------------------------------------------------------
# T058c — DELETE /lock  (release)
# ---------------------------------------------------------------------------

@router.delete("/{case_id}/lock", dependencies=[Depends(require_role("nurse", "admin"))])
async def release_lock(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Release a case lock. Nurse must be the lock owner, or Admin."""
    lock_result = await db.execute(
        select(CaseLock).where(CaseLock.case_id == case_id)
    )
    lock = lock_result.scalar_one_or_none()

    if not lock:
        raise HTTPException(status_code=404, detail="No active lock on this case")

    is_owner = lock.nurse_id == current_user.id
    is_admin = current_user.role.value == "admin"

    if not (is_owner or is_admin):
        raise HTTPException(status_code=403, detail="You do not own this lock")

    await db.delete(lock)

    trace_id = uuid.uuid4()
    await audit_service.log(
        db,
        trace_id=trace_id,
        case_id=case_id,
        actor_type=ActorType.user,
        actor_id=str(current_user.id),
        action="case_lock_released",
        input_summary=f"Lock released by {current_user.username}",
    )

    await db.commit()
    return {"detail": "Lock released"}


# ---------------------------------------------------------------------------
# T060a — GET /history
# ---------------------------------------------------------------------------

@router.get("/history", dependencies=[Depends(require_role("nurse", "admin"))])
async def get_history(
    nurse_id: Optional[str] = Query(None, description="Admin: filter by nurse_id UUID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return decided cases.
    Nurses see only their own decisions (FR-029a).
    Admin can pass ?nurse_id= to view any nurse's history.
    """
    is_admin = current_user.role.value == "admin"

    if nurse_id:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only admin can filter by nurse_id")
        try:
            target_nurse_uuid = uuid.UUID(nurse_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid nurse_id UUID")
    else:
        target_nurse_uuid = current_user.id

    result = await db.execute(
        select(NurseDecision, Case, Policy.name.label("policy_name"))
        .join(Case, NurseDecision.case_id == Case.id)
        .join(Policy, Case.policy_id == Policy.id)
        .where(NurseDecision.nurse_id == target_nurse_uuid)
        .order_by(NurseDecision.decided_at.desc())
    )
    rows = result.all()

    history = []
    for decision, case_obj, policy_name in rows:
        history.append({
            "decision_id":    str(decision.id),
            "case_id":        str(case_obj.id),
            "policy_name":    policy_name,
            "service_type":   case_obj.service_type,
            "member_id":      case_obj.member_id,
            "decision":       decision.decision.value,
            "comment":        decision.comment,
            "decided_at":     decision.decided_at,
            "case_status":    case_obj.status.value,
        })

    return history


# ---------------------------------------------------------------------------
# T060b — POST /decide
# ---------------------------------------------------------------------------

class DecisionRequest(BaseModel):
    decision: str   # "accepted" | "rejected"
    comment: str

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, v: str) -> str:
        if v not in ("accepted", "rejected"):
            raise ValueError("decision must be 'accepted' or 'rejected'")
        return v

    @field_validator("comment")
    @classmethod
    def non_empty_comment(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("comment is required (FR-028)")
        return v.strip()


@router.post("/{case_id}/decide", dependencies=[Depends(require_role("nurse"))])
async def decide_case(
    case_id: uuid.UUID,
    request: DecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit accept/reject decision. Requires:
      - Case is locked by this nurse.
      - Non-empty comment (FR-028).
    Transitions status, records decision, releases lock, writes audit (FR-040d).
    """
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Verify lock ownership
    lock_result = await db.execute(
        select(CaseLock).where(CaseLock.case_id == case_id)
    )
    lock = lock_result.scalar_one_or_none()

    if not lock:
        raise HTTPException(status_code=403, detail="Case is not locked. Lock the case before deciding.")
    if lock.nurse_id != current_user.id:
        raise HTTPException(status_code=403, detail="Case is locked by another nurse")

    # Determine target status
    to_status = (
        CaseStatus.accepted if request.decision == "accepted" else CaseStatus.rejected
    )

    trace_id = uuid.uuid4()

    # Validate and perform status transition
    try:
        await workflow_agent.transition_status(
            db=db,
            case_id=case_id,
            from_status=case.status,
            to_status=to_status,
            trace_id=trace_id,
            actor_id=str(current_user.id),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Set decision fields on Case
    case.decided_at = _utcnow()
    case.decided_by = current_user.id
    case.decision_comment = request.comment

    # Record NurseDecision
    nurse_decision = NurseDecision(
        case_id=case_id,
        nurse_id=current_user.id,
        decision=NurseDecisionEnum(request.decision),
        comment=request.comment,
        decided_at=_utcnow(),
    )
    db.add(nurse_decision)

    # Release the lock
    await db.delete(lock)

    # Audit entry (FR-040d)
    await audit_service.log(
        db,
        trace_id=trace_id,
        case_id=case_id,
        actor_type=ActorType.user,
        actor_id=str(current_user.id),
        action="nurse_decision",
        input_summary=f"decision={request.decision}",
        output_summary=f"comment={request.comment[:200]}",
        metadata={"decision": request.decision, "comment": request.comment},
    )

    await db.commit()

    return {
        "detail": f"Case {request.decision}",
        "case_id": str(case_id),
        "decision": request.decision,
        "status": to_status.value,
    }
