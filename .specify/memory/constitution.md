<!--
Sync Impact Report
- Version change: 0.0.0 -> 1.0.0
- Modified principles: none (initial constitution created)
- Added sections: Core Principles, Technical Constraints, Development Workflow
- Removed sections: none
- Templates requiring updates: ✅ .specify/templates/plan-template.md, ✅ .specify/templates/spec-template.md, ✅ .specify/templates/tasks-template.md
- Follow-up TODOs: none
-->

# Prior Authorization Evidence Assistant Constitution

## Core Principles

### I. Agent-Oriented Architecture

All features MUST be implemented as a clearly separated multi-agent workflow. Each agent MUST have one responsibility, explicit inputs and outputs, and MUST exchange state through a shared typed structure rather than hidden globals.

### II. Streamlit-First Human-in-the-Loop UI

Any user-facing workflow MUST be delivered through a Streamlit application with a single-page dashboard experience. The UI MUST expose the current pipeline state, show generated artifacts, and reflect the underlying session state without requiring hidden backend steps.

### III. Language Model Routing Through LangChain

Where multi-agent orchestration is required, the implementation MUST use LangChain patterns for agent routing, prompt composition, and tool integration. Routing logic MUST be explicit and testable rather than embedded in ad hoc conditionals.

### IV. Strict Type Safety for Python

All Python files MUST include explicit type hints for functions, methods, class attributes, and container types. Public interfaces MUST use typed data models or dataclasses where appropriate, and type annotations MUST be applied consistently across the codebase.

### V. Prototype Scope Discipline

Prototype work MUST use the available local evidence source and in-memory state unless a feature explicitly requires persistence. New dependencies MUST be justified by the prototype scope and MUST NOT introduce unnecessary complexity.

## Technical Constraints

- The project MUST use Python as the implementation language.
- The project MUST provide a Streamlit-based UI for human review and interaction.
- The project MUST use LangChain for multi-agent routing and orchestration.
- All Python files MUST include explicit type hints.
- The prototype MUST use the available local policy PDF as its primary evidence source.
- The prototype MUST keep session state in memory unless persistence is explicitly added in a later phase.

## Development Workflow

- Feature work MUST be captured in the specification, implementation plan, and task artifacts before code is built.
- Implementation changes MUST be verified by running the app locally and confirming the relevant workflow path.
- Any deviation from the required Streamlit, LangChain, or strict typing constraints MUST be documented and approved before implementation proceeds.

## Governance

This constitution supersedes ad-hoc implementation practices for this project. Amendments MUST update this document, keep dependent templates aligned, and require a version bump before the change is treated as accepted.

**Version**: 1.0.0 | **Ratified**: 2026-07-05 | **Last Amended**: 2026-07-05
