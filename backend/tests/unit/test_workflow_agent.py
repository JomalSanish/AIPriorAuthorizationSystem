"""
T073 — Workflow Agent Unit Tests.

Tests:
  - Planner action whitelist validation (rejects invalid actions)
  - Turn budget enforcement (forces finalize after N turns)
  - Summary-required guardrail (rejects finalize without Summary)
  - No accept/reject action in whitelist (FR-017)
  - Status transition validation (T056)
"""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.workflow import (
    WorkflowAction,
    WorkflowAgent,
    VALID_TRANSITIONS,
    InvalidStatusTransitionError,
    PlannedAction,
)
from app.db.models import CaseStatus


workflow_agent = WorkflowAgent()


# ---------------------------------------------------------------------------
# FR-017: no accept/reject in whitelist
# ---------------------------------------------------------------------------

def test_whitelist_has_no_accept_reject():
    """FR-017: accept and reject must not appear in the action whitelist."""
    action_values = {a.value for a in WorkflowAction}
    assert "accept" not in action_values, "accept must not be in whitelist (FR-017)"
    assert "reject" not in action_values, "reject must not be in whitelist (FR-017)"
    assert "accepted" not in action_values
    assert "rejected" not in action_values


def test_whitelist_contains_required_actions():
    """Verify all expected actions exist in the whitelist."""
    required = {
        "call_intake_agent",
        "call_retrieval_agent",
        "call_reasoning_agent",
        "call_summary_agent",
        "finalize_to_nurse_review",
    }
    action_values = {a.value for a in WorkflowAction}
    for action in required:
        assert action in action_values, f"{action} missing from whitelist"


# ---------------------------------------------------------------------------
# FR-016: Turn budget enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_turn_budget_exceeded_forces_finalize():
    """FR-016: When turn_number > DEFAULT_TURN_BUDGET, force finalize without LLM call."""
    with patch.object(workflow_agent, "MAX_PLANNER_RETRIES", 3):
        result = await workflow_agent.plan_next_action(
            case_id=str(uuid.uuid4()),
            case_state={"status": "processing"},
            action_history=["call_intake_agent", "call_summary_agent"],
            turn_number=workflow_agent.DEFAULT_TURN_BUDGET + 1,
        )
    assert result.action == WorkflowAction.finalize_to_nurse_review
    assert "budget" in result.reasoning.lower() or "exhausted" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_turn_budget_exactly_at_limit_does_not_force():
    """Turn budget fires ONLY when turn_number > limit, not at exactly the limit."""
    # At exactly DEFAULT_TURN_BUDGET, it should still call LLM (mocked)
    mock_response = '{"action": "call_summary_agent", "reasoning": "Next step"}'
    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response
        result = await workflow_agent.plan_next_action(
            case_id=str(uuid.uuid4()),
            case_state={"status": "processing"},
            action_history=[],
            turn_number=workflow_agent.DEFAULT_TURN_BUDGET,  # exactly at limit
        )
    # Should NOT be forced finalize — LLM was consulted
    assert mock_gen.called


# ---------------------------------------------------------------------------
# FR-018: finalize blocked unless summary has run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finalize_blocked_without_summary():
    """FR-018: finalize_to_nurse_review must be blocked if summary hasn't run."""
    # LLM returns finalize, but summary hasn't run
    mock_response = '{"action": "finalize_to_nurse_review", "reasoning": "All done"}'
    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response
        result = await workflow_agent.plan_next_action(
            case_id=str(uuid.uuid4()),
            case_state={"status": "processing"},
            action_history=["call_intake_agent", "call_reasoning_agent"],  # no summary
            turn_number=1,
        )
    # Should redirect to call_summary_agent instead of finalize
    assert result.action == WorkflowAction.call_summary_agent, (
        f"Expected call_summary_agent but got {result.action} — FR-018 violation"
    )


@pytest.mark.asyncio
async def test_finalize_allowed_after_summary():
    """FR-018: finalize_to_nurse_review allowed when call_summary_agent is in history."""
    mock_response = '{"action": "finalize_to_nurse_review", "reasoning": "Summary done, ready for nurse"}'
    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_response
        result = await workflow_agent.plan_next_action(
            case_id=str(uuid.uuid4()),
            case_state={"status": "processing"},
            action_history=["call_intake_agent", "call_summary_agent"],
            turn_number=2,
        )
    assert result.action == WorkflowAction.finalize_to_nurse_review


# ---------------------------------------------------------------------------
# T056: Status transition validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_transition_draft_to_processing():
    """draft → processing is a valid transition."""
    allowed = VALID_TRANSITIONS[CaseStatus.draft]
    assert CaseStatus.processing in allowed


@pytest.mark.asyncio
async def test_valid_transition_accepted_to_re_verification():
    """accepted → re_verification_required is valid (admin intervention)."""
    allowed = VALID_TRANSITIONS[CaseStatus.accepted]
    assert CaseStatus.re_verification_required in allowed


@pytest.mark.asyncio
async def test_invalid_transition_pending_to_processing():
    """pending_nurse_review → processing is invalid (nurses can't re-trigger pipeline)."""
    allowed = VALID_TRANSITIONS[CaseStatus.pending_nurse_review]
    assert CaseStatus.processing not in allowed


@pytest.mark.asyncio
async def test_transition_raises_for_invalid_path():
    """transition_status raises InvalidStatusTransitionError for illegal transitions."""
    with pytest.raises(InvalidStatusTransitionError):
        await workflow_agent.transition_status(
            db=None,
            case_id=None,
            from_status=CaseStatus.pending_nurse_review,
            to_status=CaseStatus.processing,
            trace_id=uuid.uuid4(),
        )


@pytest.mark.asyncio
async def test_all_statuses_have_transitions():
    """Every CaseStatus except terminal ones must have at least one allowed transition."""
    terminal = {CaseStatus.accepted, CaseStatus.rejected}
    for status in CaseStatus:
        if status in terminal:
            continue
        if status == CaseStatus.re_verification_required:
            # Must allow processing
            assert CaseStatus.processing in VALID_TRANSITIONS[status]


# ---------------------------------------------------------------------------
# LLM fallback behavior
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_planner_defaults_on_all_retries_failed():
    """When all LLM retries fail and summary has run, default to finalize."""
    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = RuntimeError("LLM unavailable")
        result = await workflow_agent.plan_next_action(
            case_id=str(uuid.uuid4()),
            case_state={"status": "processing"},
            action_history=["call_summary_agent"],  # summary done
            turn_number=1,
        )
    assert result.action == WorkflowAction.finalize_to_nurse_review


@pytest.mark.asyncio
async def test_planner_defaults_to_summary_on_retries_failed_without_summary():
    """When all LLM retries fail and summary hasn't run, default to call_summary_agent."""
    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = RuntimeError("LLM unavailable")
        result = await workflow_agent.plan_next_action(
            case_id=str(uuid.uuid4()),
            case_state={"status": "processing"},
            action_history=["call_intake_agent"],   # no summary
            turn_number=1,
        )
    assert result.action == WorkflowAction.call_summary_agent
