from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from state.session_state import SessionState


class AuditAgent:
    """Finalize the prior authorization review session and compile a compliance verification package."""

    def run(self, state: SessionState) -> SessionState:
        # Determine model metadata based on configuration
        import os
        has_api = bool(os.getenv("OPENAI_API_KEY"))
        model_name = "gpt-4o-mini" if has_api else "heuristic-rule-engine"

        timestamp = datetime.now(timezone.utc).isoformat()

        # Build payload package for hashing
        payload = {
            "request_id": state.request_id,
            "classification": state.classification,
            "evidence": [
                {"citation": ev.get("citation"), "score": ev.get("score")}
                for ev in state.evidence
            ],
            "gap_status": state.gap_analysis.get("status"),
            "review_status": state.review_status,
            "routing_queue": state.routing_queue,
            "timestamp": timestamp,
            "model": model_name,
        }

        # Generate SHA-256 signature hash
        payload_str = json.dumps(payload, sort_keys=True)
        compliance_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        # Append audit trail entries
        state.audit_trail.append(f"[{timestamp}] Audit finalization started using model: {model_name}")
        state.audit_trail.append(f"[{timestamp}] Target Queue routing set to: {state.routing_queue}")
        state.audit_trail.append(f"[{timestamp}] Compliance signature hash generated: {compliance_hash[:16]}")
        state.audit_trail.append(f"[{timestamp}] Session Audit Finalized. SHA256: {compliance_hash}")

        # Store hash in session state artifacts for UI retrieval
        state.artifacts["compliance_hash"] = compliance_hash
        state.artifacts["audit_timestamp"] = timestamp
        state.artifacts["audit_model"] = model_name

        return state
