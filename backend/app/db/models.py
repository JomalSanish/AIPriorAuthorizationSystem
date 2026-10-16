"""
SQLAlchemy ORM models for the PA Evidence Assistant.

Invariant (FR-040e): AuditLog rows are APPEND-ONLY from application code.
There must be no UPDATE or DELETE calls against AuditLog anywhere in the
codebase. Enforce at the application layer; the DB constraint is the
docstring plus code review.

All UUIDs use Python's uuid.uuid4() as the default factory so that IDs are
generated in Python, not the DB — this makes them available before flush.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class UserRole(str, PyEnum):
    intake = "intake"
    nurse = "nurse"
    admin = "admin"


class CaseStatus(str, PyEnum):
    draft = "draft"
    processing = "processing"
    pending_nurse_review = "pending_nurse_review"
    accepted = "accepted"
    rejected = "rejected"
    error = "error"
    re_verification_required = "re_verification_required"


class OcrStatus(str, PyEnum):
    not_needed = "not_needed"
    completed = "completed"
    failed = "failed"


class NurseDecisionEnum(str, PyEnum):
    accepted = "accepted"
    rejected = "rejected"


class ActorType(str, PyEnum):
    user = "user"
    agent = "agent"
    system = "system"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    """Application user — Intake, Nurse, or Admin role."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    username: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    # relationships
    created_cases: Mapped[list["Case"]] = relationship(
        "Case", back_populates="creator", foreign_keys="Case.created_by"
    )
    decided_cases: Mapped[list["Case"]] = relationship(
        "Case", back_populates="decider", foreign_keys="Case.decided_by"
    )
    nurse_decisions: Mapped[list["NurseDecision"]] = relationship(
        "NurseDecision", back_populates="nurse"
    )
    created_policies: Mapped[list["Policy"]] = relationship(
        "Policy", back_populates="creator"
    )
    case_lock: Mapped["CaseLock | None"] = relationship(
        "CaseLock", back_populates="nurse", uselist=False
    )


class Policy(Base):
    """Named insurance policy that cases are evaluated against."""

    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # relationships
    creator: Mapped["User"] = relationship("User", back_populates="created_policies")
    requirements: Mapped[list["PolicyRequirement"]] = relationship(
        "PolicyRequirement", back_populates="policy", cascade="all, delete-orphan"
    )
    documents: Mapped[list["PolicyDocument"]] = relationship(
        "PolicyDocument", back_populates="policy", cascade="all, delete-orphan"
    )
    cases: Mapped[list["Case"]] = relationship("Case", back_populates="policy")


class PolicyRequirement(Base):
    """Individual evidence requirement extracted from a policy document."""

    __tablename__ = "policy_requirements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requirement_text: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    policy: Mapped["Policy"] = relationship("Policy", back_populates="requirements")


class Case(Base):
    """Prior authorization case submitted by an Intake user."""

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    cpt_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    icd_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    service_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="case_status"), default=CaseStatus.draft, nullable=False, index=True
    )
    sla_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    decision_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # relationships
    policy: Mapped["Policy"] = relationship("Policy", back_populates="cases")
    creator: Mapped["User"] = relationship(
        "User", back_populates="created_cases", foreign_keys=[created_by]
    )
    decider: Mapped["User | None"] = relationship(
        "User", back_populates="decided_cases", foreign_keys=[decided_by]
    )
    documents: Mapped[list["CaseDocument"]] = relationship(
        "CaseDocument", back_populates="case", cascade="all, delete-orphan"
    )
    nurse_decisions: Mapped[list["NurseDecision"]] = relationship(
        "NurseDecision", back_populates="case"
    )
    lock: Mapped["CaseLock | None"] = relationship(
        "CaseLock", back_populates="case", uselist=False, cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="case"
    )


class CaseDocument(Base):
    """Document submitted as part of a PA case."""

    __tablename__ = "case_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # pdf, docx, txt, etc.
    minio_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), default="case_document", nullable=False)
    ocr_status: Mapped[OcrStatus] = mapped_column(
        Enum(OcrStatus, name="ocr_status"), default=OcrStatus.not_needed, nullable=False
    )
    extracted_text_length: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    case: Mapped["Case"] = relationship("Case", back_populates="documents")


class PolicyDocument(Base):
    """Document uploaded as part of a policy definition."""

    __tablename__ = "policy_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    minio_object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    policy: Mapped["Policy"] = relationship("Policy", back_populates="documents")


class NurseDecision(Base):
    """Nurse Reviewer's accept/reject decision on a case."""

    __tablename__ = "nurse_decisions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True
    )
    nurse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    decision: Mapped[NurseDecisionEnum] = mapped_column(
        Enum(NurseDecisionEnum, name="nurse_decision"), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    case: Mapped["Case"] = relationship("Case", back_populates="nurse_decisions")
    nurse: Mapped["User"] = relationship("User", back_populates="nurse_decisions")


class CaseLock(Base):
    """
    Optimistic lock held by a Nurse while reviewing a case.

    One lock per case (unique constraint on case_id). Lock expires at
    lock_expires_at; APScheduler releases stale locks.
    """

    __tablename__ = "case_locks"
    __table_args__ = (UniqueConstraint("case_id", name="uq_case_lock_case_id"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    nurse_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    locked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    lock_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    case: Mapped["Case"] = relationship("Case", back_populates="lock")
    nurse: Mapped["User"] = relationship("User", back_populates="case_lock")


class AuditLog(Base):
    """
    Append-only audit trail for all system events.

    INVARIANT (FR-040e): Application code MUST NOT issue UPDATE or DELETE
    against this table. Rows are immutable once written. Enforce via code
    review; enforce at DB layer with a BEFORE UPDATE/DELETE trigger in
    production.

    Covers: user actions, agent actions, system events (FR-040a–f).
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_new_uuid
    )
    trace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=_new_uuid, nullable=False, index=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id"), nullable=True, index=True
    )
    actor_type: Mapped[ActorType] = mapped_column(
        Enum(ActorType, name="actor_type"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)  # user_id or agent name
    action: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    retrieval_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    llm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSONB, nullable=True  # column name is "metadata" in DB
    )

    case: Mapped["Case | None"] = relationship("Case", back_populates="audit_logs")
