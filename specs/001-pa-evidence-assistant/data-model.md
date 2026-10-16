# Data Model Specification

This document defines the schema for the Prior Authorization Evidence Assistant, extracted from [spec.md](../spec.md) and [tasks.md](../tasks.md).

## Core Entities

### User (T006)
- **id**: UUID, PK
- **username**: String, unique
- **hashed_password**: String
- **role**: Enum (Intake, Nurse, Admin) (FR-002)
- **is_active**: Boolean (default True)

### Policy (T007)
- **id**: UUID, PK
- **name**: String
- **is_active**: Boolean (FR-009a)

### PolicyRequirement (T007)
- **id**: UUID, PK
- **policy_id**: UUID, FK to Policy
- **requirement_text**: String
- **requirement_category**: String

### Case (T007)
- **id**: UUID, PK
- **policy_id**: UUID, FK to Policy
- **member_id**, **provider_id**, **cpt_code**, **icd_code**, **service_type**: Strings (nullable)
- **status**: Enum (`draft`, `processing`, `pending_nurse_review`, `accepted`, `rejected`, `error`, `re_verification_required`)
- **sla_start_at**: DateTime
- **decided_by**: UUID (nullable, denormalized for convenience)
- **decision_comment**: String (nullable, denormalized for convenience)

> **Note**: `queue` is derived from `status` (e.g., `pending_nurse_review` means the case is in the Nurse Review queue). `decided_by` and `decision_comment` are denormalized from `NurseDecision` for query convenience. On re-verification (FR-032), both are nulled. The `NurseDecision` record is retained for audit history.

### CaseDocument (T007)
- **id**: UUID, PK
- **case_id**: UUID, FK to Case
- **filename**: String
- **file_type**: String
- **minio_path**: String
- **sha256_hash**: String
- **ocr_status**: Enum (`pending`, `completed`, `failed`)

### PolicyDocument (T007)
- **id**: UUID, PK
- **policy_id**: UUID, FK to Policy
- **original_filename**: String
- **file_type**: String
- **minio_object_key**: String
- **sha256_hash**: String
- **created_at**: DateTime

### CaseLock (T007)
- **case_id**: UUID, PK, FK to Case
- **nurse_id**: UUID, FK to User
- **locked_at**: DateTime
- **lock_expires_at**: DateTime (FR-026)

### NurseDecision (T007)
- **id**: UUID, PK
- **case_id**: UUID, FK to Case
- **nurse_id**: UUID, FK to User
- **decision**: Enum (`accepted`, `rejected`)
- **comment**: String
- **decided_at**: DateTime

### AuditLog (T007)
- **id**: UUID, PK
- **trace_id**: String
- **case_id**: UUID (nullable), FK to Case
- **timestamp**: DateTime
- **actor_type**: String (`user`, `agent`, `system`)
- **actor_id**: String
- **action**: String
- **model_name**, **model_version**: Strings (nullable)
- **input_summary**, **output_summary**: Strings (nullable)
- **confidence_score**, **retrieval_score**, **llm_confidence**: Floats (nullable)
- **metadata**: JSON (nullable)
- *Append-only table* (FR-040e)
