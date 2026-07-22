from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionState:
    """Shared state passed between the agents in the prototype pipeline."""

    request_id: str = ""
    patient_data: dict[str, Any] = field(default_factory=dict)
    classification: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    gap_analysis: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    audit_trail: list[str] = field(default_factory=list)
    review_status: str = "PENDING"
    routing_queue: str = "Intake"

    # Dynamic policy specifications resolved for CPT code
    current_policy_rules: list[str] = field(default_factory=list)
    current_required_docs: list[str] = field(default_factory=list)
    retrieved_policy_passages: list[dict[str, Any]] = field(default_factory=list)
