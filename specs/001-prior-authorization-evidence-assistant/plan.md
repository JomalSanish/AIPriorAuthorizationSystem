# Implementation Plan: Prior Authorization Evidence Assistant

**Branch**: 001-prior-authorization-evidence-assistant | **Date**: 2026-07-05 | **Spec**: [assistant.spec](../../assistant.spec)

**Input**: Feature specification from /assistant.spec

## Summary

Build a single-page Python Streamlit prototype that runs a five-agent workflow over the local policy PDF. The app will classify incoming requests, retrieve policy evidence from the PDF, perform gap analysis, draft reviewer-facing content, and update a review status in the UI. The implementation will use typed dataclasses and LangChain-style orchestration patterns while keeping all state in memory.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: Streamlit, LangChain, LangChain Core, Pydantic, PyPDF, python-dotenv (optional)

**Storage**: In-memory only for the prototype

**Testing**: pytest (recommended for core pipeline behavior)

**Target Platform**: Local Windows desktop / Python environment

**Project Type**: Web application / prototype dashboard

**Performance Goals**: Fast local execution for single-request demos

**Constraints**: Single local PDF evidence source, no persistence, offline-friendly prototype, strict type hints required

**Scale/Scope**: Single-user HITL workflow with one policy document

## Constitution Check

- Pass: The implementation will use Python and a Streamlit-based UI.
- Pass: The implementation will use LangChain-based orchestration patterns for the multi-agent pipeline.
- Pass: All Python files will include explicit type hints.
- Pass: The prototype will use the local policy PDF and in-memory state only.

## Project Structure

```text
specs/001-prior-authorization-evidence-assistant/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/

app.py
agents/
├── __init__.py
├── intake_agent.py
├── evidence_agent.py
├── gap_agent.py
├── summary_agent.py
├── audit_agent.py
state/
├── __init__.py
└── session_state.py
utils/
├── pdf_utils.py
└── text_utils.py
requirements.txt
tests/
└── test_pipeline.py
```

**Structure Decision**: Use a single Python application with a modular agent package, shared typed state, and utility helpers. The Streamlit entry point will live at the repository root.

## Implementation Sequence

1. Create the project skeleton and install dependencies.
2. Implement typed state models and the shared SessionState dataclass.
3. Build the Intake & Classification agent to parse request text and determine category and urgency.
4. Build PDF extraction and lightweight evidence retrieval over the policy PDF.
5. Build the policy reasoning and gap analysis agent.
6. Build the summary and audit agents.
7. Implement the Streamlit UI and wire the agents into the run pipeline.
8. Validate the end-to-end flow with a sample request and confirm the UI updates status correctly.

## Build Order

1. Shared state and data models
2. Intake and classification agent
3. Evidence retrieval agent over the local PDF
4. Gap analysis agent
5. Summary and audit agents
6. Streamlit UI wiring

## Complexity Tracking

No special exceptions are required for this prototype.
