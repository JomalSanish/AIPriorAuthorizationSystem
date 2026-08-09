"""
Workflow Agent (Phase 7 — T054, T055, T056).

Responsibilities:
  T054 — plan_next_action(): LLM-driven planner that selects the next action
          from a whitelist; validates output; applies hard guardrails.
  T055 — run_pipeline(case_id): Main execution loop that drives the planner
          and dispatches to worker agents until finalize_to_nurse_review.
  T056 — transition_status(): Validated case state machine.

Governance constraints (IMMUTABLE — see spec):
  FR-015  — audit entry written BEFORE each action execution.
  FR-016  — turn budget (default 10); forces finalize once reached.
  FR-017  — accept/reject action does not exist in the whitelist.
  FR-018  — finalize_to_nurse_review only allowed if Summary has run.
  FR-040e — all AuditLog writes are INSERT-only (via AuditService).
  FR-040a — planner_decision and agent_invocation events must be logged.
  Constitution P1 — planner can NEVER emit accept / reject.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session_factory
from app.db.models import (
    ActorType, AuditLog, Case, CaseDocument, CaseStatus, PolicyRequirement,
)
from app.services.audit import audit_service
from app.services.ollama import ollama_client

logger = logging.getLogger("pa.agents.workflow")

# ---------------------------------------------------------------------------
# Action whitelist (FR-017: accept/reject is absent by design)
# ---------------------------------------------------------------------------

class WorkflowAction(str, Enum):
    call_intake_agent       = "call_intake_agent"
    call_retrieval_agent    = "call_retrieval_agent"   # reserved for explicit re-retrieval
    call_reasoning_agent    = "call_reasoning_agent"
    call_summary_agent      = "call_summary_agent"
    request_additional_evidence = "request_additional_evidence"
    finalize_to_nurse_review = "finalize_to_nurse_review"


# ---------------------------------------------------------------------------
# Status transition table (T056)
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: Dict[CaseStatus, List[CaseStatus]] = {
    CaseStatus.draft:                   [CaseStatus.processing],
    CaseStatus.processing:              [CaseStatus.pending_nurse_review, CaseStatus.error],
    CaseStatus.pending_nurse_review:    [CaseStatus.accepted, CaseStatus.rejected],
    CaseStatus.accepted:                [CaseStatus.re_verification_required],
    CaseStatus.rejected:                [CaseStatus.re_verification_required],
    CaseStatus.re_verification_required: [CaseStatus.processing],
    CaseStatus.error:                   [CaseStatus.pending_nurse_review],
}


class InvalidStatusTransitionError(Exception):
    """Raised when an invalid case status transition is attempted."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PlannedAction:
    action: WorkflowAction
    reasoning: str
    turn_number: int


@dataclass
class PipelineResult:
    case_id: str
    final_status: str
    turn_count: int
    summary_generated: bool
    agent_call_history: List[str] = field(default_factory=list)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Workflow Agent
# ---------------------------------------------------------------------------

class WorkflowAgent:
    """
    Workflow Agent — Phase 7 (T054, T055, T056).

    Coordinates the four worker agents:
        Intake → Retrieval → Reasoning → Summary → Nurse Review

    The planner loop is LLM-driven but bounded by hard deterministic
    guardrails that cannot be overridden by the LLM output.
    """

    DEFAULT_TURN_BUDGET: int = 10
    MAX_PLANNER_RETRIES: int = 3

    # -----------------------------------------------------------------------
    # T056 — Case Status State Machine
    # -----------------------------------------------------------------------

    async def transition_status(
        self,
        db: AsyncSession,
        case_id: uuid.UUID,
        from_status: CaseStatus,
        to_status: CaseStatus,
        trace_id: uuid.UUID,
        actor_id: str = "workflow_agent",
    ) -> bool:
        """
        Transition case status with validation.

        Validates that the transition is in VALID_TRANSITIONS, updates Postgres,
        and writes an audit entry.

        Raises InvalidStatusTransitionError for illegal transitions.
        Returns True on success.
        """
        allowed = VALID_TRANSITIONS.get(from_status, [])
        if to_status not in allowed:
            raise InvalidStatusTransitionError(
                f"Invalid transition {from_status.value} → {to_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        case = await db.get(Case, case_id)
        if not case:
            raise ValueError(f"Case {case_id} not found")

        case.status = to_status
        await db.flush()

        await audit_service.log_agent(
            db,
            trace_id=trace_id,
            case_id=case_id,
            action="case_status_transitioned",
            input_summary=f"{from_status.value} → {to_status.value}",
            output_summary=f"New status: {to_status.value}",
        )

        logger.info(
            "transition_status | case=%s %s → %s",
            case_id, from_status.value, to_status.value,
        )
        return True

    # -----------------------------------------------------------------------
    # T054 — Planner
    # -----------------------------------------------------------------------

    async def plan_next_action(
        self,
        case_id: str,
        case_state: Dict[str, Any],
        action_history: List[str],
        turn_number: int,
    ) -> PlannedAction:
        """
        Ask the LLM to select the next action from the whitelist.

        Hard guardrails applied BEFORE returning:
          - Turn budget exhaustion: force finalize_to_nurse_review (FR-016).
          - finalize_to_nurse_review blocked if summary hasn't run (FR-018).
          - Output not in whitelist: re-prompt (up to MAX_PLANNER_RETRIES),
            then default to finalize_to_nurse_review.

        Args:
            case_id:        UUID string of the case.
            case_state:     Dict summarising current case state (status, docs,
                            existing verdicts, summary available).
            action_history: Ordered list of actions already executed this run.
            turn_number:    1-based turn counter.

        Returns:
            PlannedAction with action and reasoning.
        """
        logger.info(
            "plan_next_action | case=%s turn=%d history=%s",
            case_id, turn_number, action_history,
        )

        # Hard guardrail: turn budget (FR-016)
        if turn_number > self.DEFAULT_TURN_BUDGET:
            logger.warning(
                "plan_next_action | case=%s turn budget exhausted at turn %d",
                case_id, turn_number,
            )
            return PlannedAction(
                action=WorkflowAction.finalize_to_nurse_review,
                reasoning=f"Turn budget ({self.DEFAULT_TURN_BUDGET}) exhausted. Forcing finalize.",
                turn_number=turn_number,
            )

        system_prompt = (
            "You are a prior-authorization pipeline orchestrator. "
            "Your ONLY task is to select the next action for processing a case. "
            "You MUST choose from the provided whitelist. "
            "You MUST NOT recommend accept or reject — those decisions belong to the Nurse. "
            "Return structured JSON only."
        )

        action_list = "\n".join(f"  - {a.value}" for a in WorkflowAction)
        history_str = (
            "\n".join(f"  Turn {i+1}: {a}" for i, a in enumerate(action_history))
            if action_history
            else "  (none yet)"
        )

        prompt = (
            f"Prior Authorization Pipeline — Turn {turn_number}\n\n"
            f"Case State:\n{json.dumps(case_state, indent=2, default=str)}\n\n"
            f"Actions already executed this run:\n{history_str}\n\n"
            f"Allowed actions (choose exactly one):\n{action_list}\n\n"
            "Select the most appropriate next action and explain why. "
            "Return JSON with keys 'action' and 'reasoning'."
        )

        format_schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [a.value for a in WorkflowAction],
                    "description": "The next action to execute.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation (1-3 sentences).",
                },
            },
            "required": ["action", "reasoning"],
        }

        # Planner LLM call with up to MAX_PLANNER_RETRIES retries
        chosen_action: Optional[WorkflowAction] = None
        reasoning: str = ""

        for attempt in range(1, self.MAX_PLANNER_RETRIES + 1):
            try:
                raw = await ollama_client.generate(prompt, system_prompt, format_schema)
                parsed = json.loads(raw)
                raw_action = parsed.get("action", "")
                chosen_action = WorkflowAction(raw_action)
                reasoning = str(parsed.get("reasoning", "")).strip() or "No reasoning provided."
                break
            except Exception as exc:
                logger.warning(
                    "plan_next_action | case=%s attempt=%d/%d failed: %s",
                    case_id, attempt, self.MAX_PLANNER_RETRIES, exc,
                )
                if attempt == self.MAX_PLANNER_RETRIES:
                    chosen_action = None

        # Default on repeated failure
        if chosen_action is None:
            logger.error(
                "plan_next_action | case=%s all retries failed, defaulting to finalize.",
                case_id,
            )
            summary_done = "call_summary_agent" in action_history
            chosen_action = (
                WorkflowAction.finalize_to_nurse_review
                if summary_done
                else WorkflowAction.call_summary_agent
            )
            reasoning = "Planner failed after retries — safe default chosen."

        # Hard guardrail FR-018: cannot finalize before summary
        if chosen_action == WorkflowAction.finalize_to_nurse_review:
            if "call_summary_agent" not in action_history:
                logger.info(
                    "plan_next_action | case=%s finalize blocked — summary not yet run. "
                    "Overriding to call_summary_agent (FR-018).",
                    case_id,
                )
                chosen_action = WorkflowAction.call_summary_agent
                reasoning = (
                    "FR-018: Cannot finalize before summary is generated. "
                    "Overriding to call_summary_agent."
                )

        return PlannedAction(
            action=chosen_action,
            reasoning=reasoning,
            turn_number=turn_number,
        )

    # -----------------------------------------------------------------------
    # T055 — Pipeline Execution Loop
    # -----------------------------------------------------------------------

    async def run_pipeline(self, case_id: str) -> PipelineResult:
        """
        Main pipeline execution loop.

        Acquires its own DB session (runs as a background task — cannot
        share the request session). Drives the planner loop until
        finalize_to_nurse_review or the turn budget is exhausted.

        Writes audit entries BEFORE each action execution (FR-015).

        Args:
            case_id: UUID string of the case to process.

        Returns:
            PipelineResult with final status, turn count, and call history.
        """
        trace_id = uuid.uuid4()
        case_uuid = uuid.UUID(case_id)
        action_history: List[str] = []
        turn_number = 0
        summary_generated = False
        final_status = CaseStatus.error.value
        error_detail: Optional[str] = None

        logger.info("run_pipeline | case=%s trace=%s", case_id, trace_id)

        try:
            async with get_session_factory()() as db:
                # Load case
                case = await db.get(Case, case_uuid)
                if not case:
                    raise ValueError(f"Case {case_id} not found")

                # Load policy requirements
                req_result = await db.execute(
                    select(PolicyRequirement)
                    .where(PolicyRequirement.policy_id == case.policy_id)
                    .order_by(PolicyRequirement.ordinal)
                )
                requirements = req_result.scalars().all()

                # Load documents
                doc_result = await db.execute(
                    select(CaseDocument).where(CaseDocument.case_id == case_uuid)
                )
                documents = doc_result.scalars().all()

                all_docs_failed = bool(documents) and all(
                    d.ocr_status.value == "failed" for d in documents
                )

                # Log pipeline start
                await audit_service.log_agent(
                    db,
                    trace_id=trace_id,
                    case_id=case_uuid,
                    action="pipeline_started",
                    input_summary=f"case={case_id} policy={case.policy_id} docs={len(documents)} reqs={len(requirements)}",
                )
                await db.commit()

                # -------------------------------------------------------
                # Planner loop
                # -------------------------------------------------------
                verdicts = []

                while True:
                    turn_number += 1

                    # Build current case state snapshot for planner
                    case_state = {
                        "case_id":           case_id,
                        "status":            case.status.value,
                        "document_count":    len(documents),
                        "all_docs_failed":   all_docs_failed,
                        "requirement_count": len(requirements),
                        "verdicts_done":     len(verdicts),
                        "summary_generated": summary_generated,
                        "actions_so_far":    action_history,
                    }

                    # Planner decision — audit BEFORE execution (FR-015)
                    planned = await self.plan_next_action(
                        case_id=case_id,
                        case_state=case_state,
                        action_history=action_history,
                        turn_number=turn_number,
                    )

                    async with get_session_factory()() as audit_db:
                        await audit_service.log_agent(
                            audit_db,
                            trace_id=trace_id,
                            case_id=case_uuid,
                            action="planner_decision",
                            input_summary=json.dumps(case_state, default=str)[:2000],
                            output_summary=(
                                f"action={planned.action.value} | {planned.reasoning[:300]}"
                            ),
                        )
                        await audit_db.commit()

                    logger.info(
                        "run_pipeline | case=%s turn=%d action=%s",
                        case_id, turn_number, planned.action.value,
                    )

                    # -------------------------------------------------------
                    # Execute planned action
                    # -------------------------------------------------------
                    action_history.append(planned.action.value)

                    if planned.action == WorkflowAction.call_intake_agent:
                        from app.agents.intake import intake_agent
                        from app.services.minio import minio_service
                        async with get_session_factory()() as exec_db:
                            exec_docs = (await exec_db.execute(
                                select(CaseDocument).where(CaseDocument.case_id == case_uuid)
                            )).scalars().all()
                            doc_files = {}
                            bucket = "pa-case-documents"
                            for d in exec_docs:
                                try:
                                    doc_files[str(d.id)] = minio_service.download_file(bucket, d.minio_object_key)
                                except Exception as e:
                                    logger.warning("run_pipeline | could not download doc %s: %s", d.id, e)
                            await intake_agent.process_case_documents(exec_db, case_id, exec_docs, doc_files)
                            await intake_agent.generate_case_profile(exec_db, case_id)
                            await exec_db.commit()

                        async with get_session_factory()() as audit_db:
                            await audit_service.log_agent(
                                audit_db,
                                trace_id=trace_id,
                                case_id=case_uuid,
                                action="agent_invocation",
                                input_summary="call_intake_agent",
                                output_summary=f"Processed {len(documents)} docs, generated case_profile.",
                            )
                            await audit_db.commit()

                    elif planned.action == WorkflowAction.call_reasoning_agent:
                        from app.agents.reasoning import reasoning_agent
                        verdicts = await reasoning_agent.classify_all_requirements(
                            case_id=case_id,
                            policy_requirements=list(requirements),
                        )
                        present  = sum(1 for v in verdicts if v.classification.value == "Present")
                        absent   = sum(1 for v in verdicts if v.classification.value == "Absent")
                        unclear  = sum(1 for v in verdicts if v.classification.value == "Unclear")

                        async with get_session_factory()() as audit_db:
                            await audit_service.log_agent(
                                audit_db,
                                trace_id=trace_id,
                                case_id=case_uuid,
                                action="reasoning_verdict",
                                input_summary=f"{len(requirements)} requirements",
                                output_summary=(
                                    f"present={present} absent={absent} unclear={unclear}"
                                ),
                            )
                            await audit_db.commit()

                    elif planned.action == WorkflowAction.call_summary_agent:
                        from app.agents.summary import summary_agent
                        turn_budget_hit = turn_number >= self.DEFAULT_TURN_BUDGET
                        summary = await summary_agent.generate_summary(
                            case_id=case_id,
                            verdicts=verdicts,
                            partial=turn_budget_hit,
                            all_documents_failed=all_docs_failed,
                        )
                        summary_generated = True

                        async with get_session_factory()() as audit_db:
                            await audit_service.log_agent(
                                audit_db,
                                trace_id=trace_id,
                                case_id=case_uuid,
                                action="summary_generated",
                                input_summary=f"{len(verdicts)} verdicts",
                                output_summary=summary.summary_text[:500],
                                metadata={
                                    "gap_count": len(summary.gap_checklist),
                                    "flags": summary.flags,
                                },
                            )
                            await audit_db.commit()

                    elif planned.action == WorkflowAction.request_additional_evidence:
                        async with get_session_factory()() as audit_db:
                            await audit_service.log_agent(
                                audit_db,
                                trace_id=trace_id,
                                case_id=case_uuid,
                                action="agent_invocation",
                                input_summary="request_additional_evidence",
                                output_summary="Flagged for additional evidence — Nurse will be notified.",
                            )
                            await audit_db.commit()

                    elif planned.action == WorkflowAction.finalize_to_nurse_review:
                        # Transition status: processing → pending_nurse_review (T056)
                        async with get_session_factory()() as trans_db:
                            fin_case = await trans_db.get(Case, case_uuid)
                            if fin_case:
                                await self.transition_status(
                                    trans_db,
                                    case_id=case_uuid,
                                    from_status=fin_case.status,
                                    to_status=CaseStatus.pending_nurse_review,
                                    trace_id=trace_id,
                                )
                                await trans_db.commit()
                        final_status = CaseStatus.pending_nurse_review.value

                        async with get_session_factory()() as audit_db:
                            await audit_service.log_agent(
                                audit_db,
                                trace_id=trace_id,
                                case_id=case_uuid,
                                action="pipeline_completed",
                                output_summary=f"Case finalized to nurse_review in {turn_number} turns.",
                                metadata={"turn_count": turn_number, "action_history": action_history},
                            )
                            await audit_db.commit()

                        break   # Pipeline done

                    # Turn-budget check after each action (FR-016)
                    if turn_number >= self.DEFAULT_TURN_BUDGET:
                        async with get_session_factory()() as audit_db:
                            await audit_service.log_agent(
                                audit_db,
                                trace_id=trace_id,
                                case_id=case_uuid,
                                action="turn_budget_exhausted",
                                input_summary=f"Turn budget ({self.DEFAULT_TURN_BUDGET}) reached",
                                output_summary="Will force finalize on next planner tick.",
                            )
                            await audit_db.commit()

        except Exception as exc:
            error_detail = str(exc)
            logger.exception("run_pipeline | case=%s FAILED: %s", case_id, exc)

            # Mark case as error (FR-040a — pipeline_error event)
            try:
                async with get_session_factory()() as err_db:
                    err_case = await err_db.get(Case, case_uuid)
                    if err_case and err_case.status == CaseStatus.processing:
                        err_case.status = CaseStatus.error
                    await audit_service.log_agent(
                        err_db,
                        trace_id=trace_id,
                        case_id=case_uuid,
                        action="pipeline_error",
                        output_summary=error_detail[:500],
                    )
                    await err_db.commit()
            except Exception as inner:
                logger.error("run_pipeline | failed to write error audit: %s", inner)

        return PipelineResult(
            case_id=case_id,
            final_status=final_status,
            turn_count=turn_number,
            summary_generated=summary_generated,
            agent_call_history=action_history,
            error=error_detail,
        )


workflow_agent = WorkflowAgent()
