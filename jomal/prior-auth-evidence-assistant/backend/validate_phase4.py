import asyncio
import os
import uuid
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.db.models import User, Policy
from app.core.security import hash_password
from app.config import get_settings

async def seed_and_test():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "intake_user"))
        user = result.scalars().first()
        if not user:
            user = User(
                username="intake_user",
                hashed_password=hash_password("password123"),
                role="intake",
                is_active=True
            )
            session.add(user)
            await session.commit()
            print("Seeded intake_user.")
            
        policy_res = await session.execute(select(Policy).where(Policy.is_active == True))
        policy = policy_res.scalars().first()
        if not policy:
            print("No active policy found. Please run validate_phase3.py first.")
            return
        policy_id = str(policy.id)

    print("Testing Phase 4: Case Creation...")
    
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=120.0) as client:
        login_res = await client.post(
            "/api/auth/login",
            data={"username": "intake_user", "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.text}")
            return
            
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 1. Create Case Draft
        print(f"Creating case draft for policy {policy_id}...")
        create_res = await client.post("/api/cases/", headers=headers, json={"policy_id": policy_id})
        if create_res.status_code != 200:
            print(f"Case creation failed: {create_res.text}")
            return
            
        case_id = create_res.json()["id"]
        print(f"Created Case Draft ID: {case_id}")
        
        # 2. Upload Documents
        print("Uploading synthetic case documents...")
        case_text = b"Patient John Doe (ID: MEM123456) was seen by Dr. Smith (NPI: 987654321). Patient complains of severe lower back pain for 8 weeks radiating to the left leg. Physical therapy was attempted for 6 weeks with no improvement. Requesting Lumbar MRI (CPT: 72148) for diagnosis. ICD-10: M54.5"
        
        files = [
            ('files', ('clinical_notes.txt', case_text, 'text/plain'))
        ]
        
        upload_res = await client.post(
            f"/api/cases/{case_id}/documents",
            headers=headers,
            files=files
        )
        if upload_res.status_code != 200:
            print(f"Document upload failed: {upload_res.text}")
            return
        print(f"Uploaded {upload_res.json()['uploaded_count']} documents.")
        
        # 3. Extract Metadata
        print("Extracting metadata...")
        extract_res = await client.post(f"/api/cases/{case_id}/extract-metadata", headers=headers)
        if extract_res.status_code != 200:
            print(f"Metadata extraction failed: {extract_res.text}")
            return
            
        metadata = extract_res.json()
        print(f"Extracted Metadata: {metadata}")
        
        # 4. Submit Case
        print("Submitting case...")
        submit_data = {
            "member_id": metadata.get("member_id") or "UNKNOWN",
            "provider_id": metadata.get("provider_id") or "UNKNOWN",
            "cpt_code": metadata.get("cpt_code"),
            "icd_code": metadata.get("icd_code"),
            "service_type": "MRI",
            "confirmed_all_failed": False
        }
        submit_res = await client.post(f"/api/cases/{case_id}/submit", headers=headers, json=submit_data)
        if submit_res.status_code != 200:
            print(f"Case submission failed: {submit_res.text}")
            return
            
        print(f"Case submitted successfully. Status: {submit_res.json()['status']}")
        
        print("\nPhase 4 Validation complete!")

if __name__ == "__main__":
    asyncio.run(seed_and_test())
