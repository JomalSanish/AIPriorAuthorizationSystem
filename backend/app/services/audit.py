"""
Audit Log Service (Phase 7 — T053).

Provides a thin, intent-revealing wrapper around direct AuditLog inserts so
that callers never need to import the ORM model or remember the append-only
rule.

Invariant (FR-040e): AuditLog rows are APPEND-ONLY.
  — This service NEVER issues UPDATE or DELETE against AuditLog.
  — Every public method adds exactly one row (or a small batch).

Covered event actions (FR-040a):
    case_created, policy_uploaded, policy_deactivated,
    user_created, user_deactivated,
    case_locked, case_lock_auto_released,
    case_re_verification, pipeline_cancelled_restarted,
    all_documents_failed_confirmed, turn_budget_exhausted,
    pipeline_error, planner_decision, agent_invocation,
    retrieval_query, reasoning_verdict, summary_generated,
    nurse_decision, admin_edit,
    auth_event, access_denial
"""

from __future__ import annotations

import uuid
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActorType, AuditLog

logger = logging.getLogger("pa.services.audit")


# ---------------------------------------------------------------------------
# Data transfer object (returned to callers — avoids leaking ORM model)
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    """Read-side view of a single audit log row."""
    id: str
    trace_id: str
    case_id: Optional[str]
    actor_type: str
    actor_id: str
    action: str
    model_name: Optional[str]
    model_version: Optional[str]
    input_summary: Optional[str]
    output_summary: Optional[str]
    confidence_score: Optional[float]
    retrieval_score: Optional[float]
    llm_confidence: Optional[float]
    timestamp: datetime
    metadata: Optional[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AuditService:
    """
    Insert-only audit log service.

    All public methods accept an ``AsyncSession`` that the caller controls.
    The service flushes (making the row visible in the current transaction)
    but never commits — the caller commits at an appropriate transaction
    boundary.
    """

    # ------------------------------------------------------------------
    # Core write
    # ------------------------------------------------------------------

    async def log(
        self,
        db: AsyncSession,
        *,
        trace_id: uuid.UUID,
        case_id: Optional[uuid.UUID] = None,
        actor_type: ActorType,
        actor_id: str,
        action: str,
        model_name: Optional[str] = None,
        model_version: Optional[str] = None,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        confidence_score: Optional[float] = None,
        retrieval_score: Optional[float] = None,
        llm_confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> uuid.UUID:
        """
        Insert one audit log entry (FR-040e: INSERT only, never UPDATE/DELETE).

        Returns the new AuditLog row's primary key UUID.
        """
        row = AuditLog(
            trace_id=trace_id,
            case_id=case_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            model_name=model_name,
            model_version=model_version,
            input_summary=input_summary[:4000] if input_summary else None,
            output_summary=output_summary[:4000] if output_summary else None,
            confidence_score=confidence_score,
            retrieval_score=retrieval_score,
            llm_confidence=llm_confidence,
            metadata_=metadata,
        )
        db.add(row)
        await db.flush()

        logger.debug(
            "audit | action=%s case=%s actor=%s",
            action, case_id, actor_id,
        )
        return row.id

    # ------------------------------------------------------------------
    # Convenience writers (keep callsites terse)
    # ------------------------------------------------------------------

    async def log_agent(
        self,
        db: AsyncSession,
        *,
        trace_id: uuid.UUID,
        case_id: Optional[uuid.UUID],
        action: str,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        confidence_score: Optional[float] = None,
        retrieval_score: Optional[float] = None,
        llm_confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> uuid.UUID:
        """Short-hand for agent-originated audit entries."""
        return await self.log(
            db,
            trace_id=trace_id,
            case_id=case_id,
            actor_type=ActorType.agent,
            actor_id="workflow_agent",
            action=action,
            model_name="llama3.2:3b",
            model_version="ollama",
            input_summary=input_summary,
            output_summary=output_summary,
            confidence_score=confidence_score,
            retrieval_score=retrieval_score,
            llm_confidence=llm_confidence,
            metadata=metadata,
        )

    async def log_auth_event(
        self,
        db: AsyncSession,
        *,
        username: str,
        outcome: str,         # "success" | "failed"
        ip_address: Optional[str] = None,
    ) -> uuid.UUID:
        """Log authentication event (FR-040b)."""
        return await self.log(
            db,
            trace_id=uuid.uuid4(),
            case_id=None,
            actor_type=ActorType.user,
            actor_id=username,
            action="auth_event",
            input_summary=f"Auth attempt: outcome={outcome} ip={ip_address}",
            metadata={"outcome": outcome, "ip_address": ip_address},
        )

    async def log_access_denial(
        self,
        db: AsyncSession,
        *,
        user_id: str,
        resource: str,
        method: str,
    ) -> uuid.UUID:
        """Log authorization denial (FR-040c)."""
        return await self.log(
            db,
            trace_id=uuid.uuid4(),
            case_id=None,
            actor_type=ActorType.user,
            actor_id=user_id,
            action="access_denial",
            input_summary=f"{method} {resource}",
            metadata={"resource": resource, "method": method},
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_case_audit_trail(
        self,
        db: AsyncSession,
        case_id: uuid.UUID,
    ) -> List[AuditEntry]:
        """
        Return the complete chronological audit trail for a case.

        Only reads — never modifies (FR-040e).
        """
        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.case_id == case_id)
            .order_by(AuditLog.timestamp.asc())
        )
        rows = result.scalars().all()

        return [
            AuditEntry(
                id=str(row.id),
                trace_id=str(row.trace_id),
                case_id=str(row.case_id) if row.case_id else None,
                actor_type=row.actor_type.value,
                actor_id=row.actor_id,
                action=row.action,
                model_name=row.model_name,
                model_version=row.model_version,
                input_summary=row.input_summary,
                output_summary=row.output_summary,
                confidence_score=row.confidence_score,
                retrieval_score=row.retrieval_score,
                llm_confidence=row.llm_confidence,
                timestamp=row.timestamp,
                metadata=row.metadata_,
            )
            for row in rows
        ]


audit_service = AuditService()
