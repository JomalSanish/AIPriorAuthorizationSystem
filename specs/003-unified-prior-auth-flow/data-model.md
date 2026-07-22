# Data Model: Unified Prior Auth Flow & Mock Policy Ground Truth

This document defines the schemas used by the multi-agent system and the user interface.

## 1. Mock Policy Ground Truth Schema (`data/mock_policies.json`)

```json
{
  "policies": [
    {
      "cpt_code": "72148",
      "service_name": "Lumbar Spine MRI",
      "specialty_requirement": "Orthopedic Surgery, Neurosurgery, or Neurology referral",
      "required_documents": [
        "Primary Care Clinical Assessment Notes",
        "Conservative Physical Therapy Logs"
      ],
      "clinical_prerequisites": [
        "Lower back pain radiating down the leg or signs of radiculopathy",
        "Trial of conservative physical therapy for at least 6 weeks",
        "Trial of conservative drug therapy (NSAIDs or analgesics) for at least 4 weeks"
      ]
    }
  ]
}
```

## 2. Provider Ingestion Payload Schema (`ProviderSubmission`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class PatientInfo(BaseModel):
    member_id: str
    first_name: str
    last_name: str
    date_of_birth: str

class ProviderInfo(BaseModel):
    provider_id: str
    name: str
    specialty: str

class ClinicalMetadata(BaseModel):
    cpt_code: str
    icd_code: str
    requested_service: str
    requested_date: str

class DocumentItem(BaseModel):
    document_id: str
    document_type: str
    filename: str
    extracted_text: str

class ProviderSubmission(BaseModel):
    submission_id: str
    patient_info: PatientInfo
    provider_info: ProviderInfo
    clinical_metadata: ClinicalMetadata
    documents: List[DocumentItem]
    
    # Fields required by the Intake Agent for initial classification and routing
    is_complete: bool = Field(..., description="True if member_id, provider_id, and cpt_code are present")
    missing_fields: List[str] = Field(default_factory=list, description="Fields missing from: Member ID, Provider ID, CPT Code")
    duplicate_suspected: bool = Field(False, description="True if text indicates duplicate request history")
```

## 3. Policy Gap Evaluation Schema (`GapChecklist`)

```python
class ChecklistItemModel(BaseModel):
    criterion: str
    status: str  # PRESENT, ABSENT, or UNCLEAR
    rationale: str
    citation: Optional[str] = None

class GapExtraction(BaseModel):
    status: str  # APPROVED, PENDING, or REJECTED
    reasoning: str
    checklist_items: List[ChecklistItemModel]
    missing_info: List[str]
```

## 4. Central Session State (`SessionState`)

The state contains:
- `request_id`: Unique tracking ID
- `patient_data`: Dictionary mapping demographics, ICD-10, CPT, and raw text
- `classification`: Target type and urgency
- `evidence`: Retrieved passages and citations from documents
- `gap_analysis`: Checklist evaluations and gaps
- `artifacts`: Summary, draft correspondence, and audit hash
- `routing_queue`: Target review queue (`Intake`, `Nurse Review`, `Medical Director`, `Auditor`, `Information Request`)
- `audit_trail`: Chronological trace of actions
