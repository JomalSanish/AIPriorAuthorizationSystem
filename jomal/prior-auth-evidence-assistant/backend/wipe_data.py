"""
Script to wipe all cases, policies, and documents from Postgres, MinIO, and Qdrant.
Keeps Users intact.
"""

import asyncio
from sqlalchemy import delete
from app.db.database import get_session_factory
from app.db.models import AuditLog, CaseDocument, Case, PolicyRequirement, PolicyDocument, Policy
from app.services.minio import minio_service
from app.services.qdrant import qdrant_service

async def wipe_data():
    print("Wiping Postgres...")
    async with get_session_factory()() as db:
        await db.execute(delete(AuditLog))
        await db.execute(delete(CaseDocument))
        await db.execute(delete(Case))
        await db.execute(delete(PolicyRequirement))
        await db.execute(delete(PolicyDocument))
        await db.execute(delete(Policy))
        await db.commit()
    print("Postgres wiped (Users retained).")

    print("Wiping MinIO...")
    buckets = ["pa-policy-documents", "pa-case-documents"]
    for bucket in buckets:
        try:
            minio_service.ensure_bucket(bucket)
            # The client is boto3 s3
            response = minio_service.s3.list_objects_v2(Bucket=bucket)
            if "Contents" in response:
                for obj in response["Contents"]:
                    minio_service.delete_file(bucket, obj["Key"])
                    print(f"Deleted {obj['Key']} from {bucket}")
        except Exception as e:
            print(f"Failed to wipe bucket {bucket}: {e}")
    print("MinIO wiped.")

    print("Wiping Qdrant...")
    try:
        await qdrant_service.client.delete_collection("policy_requirements")
        print("Deleted Qdrant collection: policy_requirements")
    except Exception as e:
        print(f"Failed to delete policy_requirements: {e}")
        
    try:
        await qdrant_service.client.delete_collection("case_profiles")
        print("Deleted Qdrant collection: case_profiles")
    except Exception as e:
        print(f"Failed to delete case_profiles: {e}")
    print("Qdrant wiped.")
    
    print("\nAll data wiped successfully! You can now start fresh.")

if __name__ == "__main__":
    asyncio.run(wipe_data())
