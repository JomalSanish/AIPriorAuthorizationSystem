# Data Model

## Core Entities

### SessionState

Represents the shared state passed between agents.

- request_id: str
- patient_data: dict[str, object]
- classification: dict[str, str]
- evidence: list[dict[str, object]]
- gap_analysis: dict[str, object]
- artifacts: dict[str, str]
- audit_trail: list[str]

### RequestPayload

Represents the user-submitted PA request input.

- raw_text: str
- source: str

### ClassificationResult

Represents the output of the intake and classification step.

- request_type: DRUG | IMAGING | SURGERY
- urgency: ROUTINE | URGENT
- rationale: str

### EvidenceItem

Represents one retrieved policy passage.

- text: str
- citation: str
- score: float

### GapAnalysis

Represents the reasoning result for policy fit.

- status: APPROVED | DENIED | PENDING
- missing_info: list[str]
- reasoning: str

### Artifacts

Represents the review content generated for the UI.

- summary: str
- communication_draft: str
