"""
Policy Management API Endpoints.
"""

import uuid
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.db.models import Policy, PolicyRequirement, User, PolicyDocument, AuditLog
from app.api.deps import get_current_user, require_role
from app.agents.intake import intake_agent
from app.services.minio import minio_service

router = APIRouter()

@router.post("/", dependencies=[Depends(require_role("admin"))])
async def upload_policy(
    name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin only: Upload a policy document and trigger ingestion."""
    # 1. Create Policy record
    policy = Policy(
        name=name,
        description=description,
        version="1.0",
        created_by=current_user.id
    )
    db.add(policy)
    await db.flush()

    file_bytes = await file.read()
    
    # 2. Upload to MinIO
    bucket = "pa-policy-documents"
    minio_service.ensure_bucket(bucket)
    object_key = f"{policy.id}/{file.filename}"
    minio_service.upload_file(bucket, object_key, file_bytes, file.content_type or "application/octet-stream")
    
    # Create PolicyDocument record
    import hashlib
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    doc = PolicyDocument(
        policy_id=policy.id,
        original_filename=file.filename,
        file_type=file.content_type or "application/octet-stream",
        minio_object_key=object_key,
        sha256_hash=sha256_hash
    )
    db.add(doc)
    await db.flush()
    
    # 3. Trigger Ingestion (Intake Agent)
    ingestion_result = await intake_agent.ingest_policy(
        db=db,
        policy_id=str(policy.id),
        document_bytes=file_bytes,
        filename=file.filename or "unknown",
        file_type=file.content_type or "application/octet-stream"
    )
    
    # 4. Audit Log
    audit = AuditLog(
        trace_id=uuid.uuid4(),
        actor_type="user",
        actor_id=str(current_user.id),
        action="policy_upload",
        input_summary=f"Uploaded policy: {name}",
        metadata_={"ingestion_stats": {"requirements": ingestion_result.extracted_requirements_count, "chunks": ingestion_result.chunk_count}}
    )
    db.add(audit)
    await db.commit()
    await db.refresh(policy)
    
    # Fetch reqs
    reqs = (await db.execute(select(PolicyRequirement).where(PolicyRequirement.policy_id == policy.id))).scalars().all()
    
    return {
        "id": policy.id,
        "name": policy.name,
        "requirements": [{"id": r.id, "text": r.requirement_text} for r in reqs],
        "chunks_indexed": ingestion_result.chunk_count
    }


@router.get("/")
async def list_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    All roles: List active policies (id + name) — used to populate the
    case-creation policy dropdown (FR-008).

    Admin: List ALL policies (active + inactive) with document count,
    requirement count, and status — used by the Policy Management registry
    table (T033), which needs to display and let admins reactivate/inspect
    inactive policies too.
    """
    if current_user.role.value == "admin":
        doc_counts = dict(
            (row[0], row[1])
            for row in (
                await db.execute(
                    select(PolicyDocument.policy_id, func.count(PolicyDocument.id))
                    .group_by(PolicyDocument.policy_id)
                )
            ).all()
        )
        req_counts = dict(
            (row[0], row[1])
            for row in (
                await db.execute(
                    select(PolicyRequirement.policy_id, func.count(PolicyRequirement.id))
                    .group_by(PolicyRequirement.policy_id)
                )
            ).all()
        )
        result = await db.execute(select(Policy).order_by(Policy.created_at.desc()))
        policies = result.scalars().all()
        return [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "is_active": p.is_active,
                "created_at": p.created_at,
                "document_count": doc_counts.get(p.id, 0),
                "requirement_count": req_counts.get(p.id, 0),
            }
            for p in policies
        ]

    result = await db.execute(
        select(Policy).where(Policy.is_active == True)
    )
    policies = result.scalars().all()
    return [{"id": p.id, "name": p.name} for p in policies]


@router.get("/{policy_id}", dependencies=[Depends(require_role("admin"))])
async def get_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin only: Get full policy details with requirements."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
        
    reqs = (await db.execute(select(PolicyRequirement).where(PolicyRequirement.policy_id == policy_id))).scalars().all()
    
    return {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "is_active": policy.is_active,
        "requirements": [{"id": r.id, "text": r.requirement_text} for r in reqs]
    }


@router.patch("/{policy_id}", dependencies=[Depends(require_role("admin"))])
async def deactivate_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin only: Soft delete policy."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
        
    policy.is_active = False
    
    # Audit Log
    audit = AuditLog(
        trace_id=uuid.uuid4(),
        actor_type="user",
        actor_id=str(current_user.id),
        action="policy_deactivate",
        input_summary=f"Deactivated policy: {policy.name}"
    )
    db.add(audit)
    
    await db.commit()
    return {"message": "Policy deactivated successfully"}
