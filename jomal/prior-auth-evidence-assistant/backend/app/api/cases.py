"""
Case Management API Endpoints.
"""

import uuid
import hashlib
import json
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Case, CaseDocument, CaseStatus, User, AuditLog, Policy
from app.api.deps import get_current_user, require_role
from app.agents.intake import intake_agent
from app.agents.retrieval import retrieval_agent
from app.agents.workflow import workflow_agent
from app.services.minio import minio_service

router = APIRouter()

class CreateCaseRequest(BaseModel):
    policy_id: str

@router.post("", dependencies=[Depends(require_role("intake", "admin"))])
@router.post("/", dependencies=[Depends(require_role("intake", "admin"))], include_in_schema=False)
async def create_case(
    request: CreateCaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Intake only: create case draft with policy_id."""
    try:
        policy_uuid = uuid.UUID(request.policy_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="policy_id must be a valid UUID.")

    policy = await db.get(Policy, policy_uuid)
    if not policy or not policy.is_active:
        raise HTTPException(status_code=400, detail="Invalid or inactive policy.")

    case = Case(
        policy_id=policy.id,
        member_id="",
        provider_id="",
        status=CaseStatus.draft,
        created_by=current_user.id
    )
    db.add(case)
    await db.flush()

    audit = AuditLog(
        trace_id=uuid.uuid4(),
        case_id=case.id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="case_created",
        input_summary=f"Created case draft for policy {policy.name}"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(case)

    return {"id": case.id, "status": case.status.value, "policy_id": case.policy_id}


@router.post("/{case_id}/documents", dependencies=[Depends(require_role("intake", "admin"))])
async def upload_case_documents(
    case_id: uuid.UUID,
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Intake only: upload one or more documents (multi-file)."""
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case.status != CaseStatus.draft:
        raise HTTPException(status_code=400, detail="Can only upload documents to a draft case.")

    bucket = "pa-case-documents"
    minio_service.ensure_bucket(bucket)

    doc_records = []
    for file in files:
        file_bytes = await file.read()
        object_key = f"{case.id}/{uuid.uuid4()}_{file.filename}"
        
        minio_service.upload_file(bucket, object_key, file_bytes, file.content_type or "application/octet-stream")
        
        sha256_hash = hashlib.sha256(file_bytes).hexdigest()
        doc = CaseDocument(
            case_id=case.id,
            original_filename=file.filename or "unknown",
            file_type=file.content_type or "application/octet-stream",
            minio_object_key=object_key,
            sha256_hash=sha256_hash,
            doc_type="case_document"
        )
        db.add(doc)
        doc_records.append(doc)

    audit = AuditLog(
        trace_id=uuid.uuid4(),
        case_id=case.id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="case_documents_uploaded",
        input_summary=f"Uploaded {len(doc_records)} document(s): "
        + ", ".join(d.original_filename for d in doc_records),
    )
    db.add(audit)

    await db.commit()
    
    return {"uploaded_count": len(doc_records)}


@router.post("/{case_id}/extract-metadata", dependencies=[Depends(require_role("intake", "admin"))])
async def extract_metadata(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Intake only: triggers LLM metadata extraction."""
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    docs_result = await db.execute(select(CaseDocument).where(CaseDocument.case_id == case_id))
    documents = docs_result.scalars().all()
    if not documents:
        raise HTTPException(status_code=400, detail="No documents uploaded yet.")

    bucket = "pa-case-documents"
    document_files = {}

    for doc in documents:
        file_bytes = minio_service.download_file(bucket, doc.minio_object_key)
        document_files[str(doc.id)] = file_bytes

    # Parses, OCRs, chunks, and embeds each document exactly once — updating
    # doc.ocr_status / doc.extracted_text_length / doc.sha256_hash in place —
    # and hands back each document's full_text so we don't have to re-parse
    # (and re-OCR) everything a second time just to build combined_text.
    process_results = await intake_agent.process_case_documents(db, str(case_id), documents, document_files)
    result_by_doc_id = {r.document_id: r for r in process_results}

    combined_text = ""
    for doc in documents:
        result = result_by_doc_id.get(str(doc.id))
        if result and result.full_text:
            combined_text += f"\n--- {doc.original_filename} ---\n{result.full_text}"

    metadata = await intake_agent.extract_case_metadata(str(case_id), combined_text)

    audit = AuditLog(
        trace_id=uuid.uuid4(),
        case_id=case.id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="case_metadata_extracted",
        input_summary=f"Extracted metadata from {len(documents)} document(s)",
        metadata_={
            "ocr_status_by_document": {
                r.document_id: r.ocr_status for r in process_results
            }
        },
    )
    db.add(audit)

    # Commit here — process_case_documents only flushed. Without this commit,
    # the ocr_status / extracted_text_length updates never reach the DB, so
    # submit_case's "did every document fail OCR" check (FR-013a) would
    # always see the original OcrStatus.not_needed default instead of the
    # real outcome.
    await db.commit()

    return {
        "member_id": metadata.member_id or "",
        "provider_id": metadata.provider_id or "",
        "cpt_code": metadata.cpt_code or "",
        "icd_code": metadata.icd_code or "",
        "service_type": metadata.service_type or ""
    }


class SubmitCaseRequest(BaseModel):
    member_id: str
    provider_id: str
    cpt_code: Optional[str] = None
    icd_code: Optional[str] = None
    service_type: Optional[str] = None
    confirmed_all_failed: bool = False

@router.post("/{case_id}/submit", dependencies=[Depends(require_role("intake", "admin"))])
async def submit_case(
    case_id: uuid.UUID,
    request: SubmitCaseRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Intake only: validates case has documents, sets status to processing."""
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    docs_result = await db.execute(select(CaseDocument).where(CaseDocument.case_id == case_id))
    documents = docs_result.scalars().all()
    if not documents:
        raise HTTPException(status_code=400, detail="Cannot submit case without documents.")

    all_failed = all(d.ocr_status.value == "failed" for d in documents)
    trace_id = uuid.uuid4()

    if all_failed and not request.confirmed_all_failed:
        raise HTTPException(status_code=409, detail="All documents failed OCR/extraction. Please explicitly confirm to proceed.")
        
    if all_failed and request.confirmed_all_failed:
        audit_confirm = AuditLog(
            trace_id=trace_id,
            case_id=case.id,
            actor_type="user",
            actor_id=str(current_user.id),
            action="all_documents_failed_confirmed",
            input_summary="User confirmed submission despite all documents failing extraction."
        )
        db.add(audit_confirm)

    case.member_id = request.member_id
    case.provider_id = request.provider_id
    case.cpt_code = request.cpt_code
    case.icd_code = request.icd_code
    case.service_type = request.service_type
    case.status = CaseStatus.processing
    case.sla_start_at = datetime.now(timezone.utc)

    audit_submit = AuditLog(
        trace_id=trace_id,
        case_id=case.id,
        actor_type="user",
        actor_id=str(current_user.id),
        action="case_submitted",
        input_summary=f"Submitted case for processing"
    )
    db.add(audit_submit)
    await db.commit()
    
    # Launch full automated pipeline as a background task (T057).
    # run_pipeline manages its own DB session — the request session is already
    # committed above, so there is no session sharing across the async boundary.
    background_tasks.add_task(workflow_agent.run_pipeline, str(case_id))
    
    return {"id": case.id, "status": case.status.value}


@router.get("")
@router.get("/", include_in_schema=False)
async def list_cases(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all cases with status, SLA clock, metadata."""
    result = await db.execute(
        select(Case, Policy.name.label('policy_name'))
        .join(Policy, Case.policy_id == Policy.id)
        .order_by(Case.created_at.desc())
    )
    cases_with_policy = result.all()
    
    response = []
    for case_obj, policy_name in cases_with_policy:
        response.append({
            "id": case_obj.id,
            "policy_name": policy_name,
            "service_type": case_obj.service_type,
            "status": case_obj.status.value,
            "sla_start_at": case_obj.sla_start_at,
            "created_at": case_obj.created_at
        })
    return response

# ---------------------------------------------------------------------------
# T048 — NLP Case Search (US6) — Must be declared before GET /{case_id}
# because FastAPI matches paths before methods; POST /search would otherwise
# resolve to GET /{case_id} and return 405 Method Not Allowed.
# ---------------------------------------------------------------------------

class CaseSearchRequest(BaseModel):
    query: str


@router.post("/search")
async def search_cases(
    request: CaseSearchRequest,
    current_user: User = Depends(get_current_user),
):
    """
    POST /api/cases/search — all roles.

    Translates a free-text natural-language query into a StructuredSearchRequest
    via LLM query understanding (T046), then executes a hybrid dense+sparse
    search over case_profile points in Qdrant (T047).

    Returns case-level metadata only — never raw document chunks (FR-038).
    Role-based visibility is applied inside execute_case_search (FR-039a).
    """
    structured = await retrieval_agent.parse_search_query(request.query)
    results = await retrieval_agent.execute_case_search(
        structured_request=structured,
        role=current_user.role.value,
    )
    return [
        {
            "case_id":      r.case_id,
            "service_type": r.service_type,
            "status":       r.status,
            "policy_name":  r.policy_name,
            "member_id":    r.member_id,
            "provider_id":  r.provider_id,
            "cpt_code":     r.cpt_code,
            "icd_code":     r.icd_code,
            "score":        r.score,
            "summary":      r.summary,
        }
        for r in results
    ]


@router.get("/{case_id}")
async def get_case(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Role-scoped case detail retrieval."""
    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    policy = await db.get(Policy, case.policy_id)
    
    return {
        "id": case.id,
        "policy_id": case.policy_id,
        "policy_name": policy.name if policy else "",
        "member_id": case.member_id,
        "provider_id": case.provider_id,
        "cpt_code": case.cpt_code,
        "icd_code": case.icd_code,
        "service_type": case.service_type,
        "status": case.status.value,
        "sla_start_at": case.sla_start_at,
        "created_at": case.created_at
    }


# ---------------------------------------------------------------------------
# Phase 8 — Document download (for DocumentViewer, T065)
# ---------------------------------------------------------------------------

@router.get("/{case_id}/documents/{doc_id}/download")
async def download_document(
    case_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a case document as a binary stream. Nurse must hold the lock."""
    from app.db.models import CaseLock, CaseStatus

    doc = await db.get(CaseDocument, doc_id)
    if not doc or doc.case_id != case_id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify nurse has the lock (FR-023: documents only accessible post-lock)
    if current_user.role.value == "nurse":
        lock_result = await db.execute(
            select(CaseLock).where(CaseLock.case_id == case_id)
        )
        lock = lock_result.scalar_one_or_none()
        if not lock or lock.nurse_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You must lock this case before accessing documents (FR-023)"
            )

    bucket = "pa-case-documents"
    file_bytes = minio_service.download_file(bucket, doc.minio_object_key)
    content_type = doc.file_type or "application/octet-stream"

    import io
    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{doc.original_filename}"'},
    )


# ---------------------------------------------------------------------------
# Phase 8 — Case summary endpoint (returns audit log summary payload for UI)
# ---------------------------------------------------------------------------

@router.get("/{case_id}/summary")
async def get_case_summary(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the AI-generated evidence summary and verdicts for a case.
    Only accessible to a nurse who holds the lock, or to Admin (FR-023).
    """
    from app.db.models import AuditLog, CaseLock

    case = await db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # FR-023: nurse must hold lock
    if current_user.role.value == "nurse":
        lock_result = await db.execute(
            select(CaseLock).where(CaseLock.case_id == case_id)
        )
        lock = lock_result.scalar_one_or_none()
        if not lock or lock.nurse_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You must lock this case before viewing its summary (FR-023)"
            )

    # Retrieve the latest summary_generated audit entry payload
    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.case_id == case_id, AuditLog.action == "summary_generated")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    summary_log = audit_result.scalar_one_or_none()

    # Retrieve reasoning_verdict audit entries for per-req verdicts
    verdict_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.case_id == case_id, AuditLog.action == "reasoning_verdict")
        .order_by(AuditLog.timestamp.desc())
        .limit(1)
    )
    verdict_log = verdict_result.scalar_one_or_none()

    # Retrieve case documents metadata
    docs_result = await db.execute(
        select(CaseDocument).where(CaseDocument.case_id == case_id)
    )
    documents = docs_result.scalars().all()

    return {
        "case_id": str(case_id),
        "status": case.status.value,
        "summary_available": summary_log is not None,
        "summary_text": summary_log.output_summary if summary_log else None,
        "summary_metadata": summary_log.metadata_ if summary_log else None,
        "verdict_summary": verdict_log.output_summary if verdict_log else None,
        "documents": [
            {
                "id": str(d.id),
                "original_filename": d.original_filename,
                "file_type": d.file_type,
                "ocr_status": d.ocr_status.value,
                "extracted_text_length": d.extracted_text_length,
            }
            for d in documents
        ],
    }
