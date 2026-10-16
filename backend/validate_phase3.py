import asyncio
import os
import uuid
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.db.models import User
from app.core.security import hash_password
from app.config import get_settings

async def seed_and_test():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.username == "admin_user"))
        user = result.scalars().first()
        if not user:
            user = User(
                username="admin_user",
                hashed_password=hash_password("password123"),
                role="admin",
                is_active=True
            )
            session.add(user)
            await session.commit()
            print("Seeded admin_user.")
    
    print("Testing Phase 3: Policy Ingestion...")
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        login_res = await client.post(
            "/api/auth/login",
            data={"username": "admin_user", "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.text}")
            return
            
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        print("Uploading synthetic policy document...")
        synthetic_policy_text = b"Lumbar MRI is medically necessary when the patient has severe lower back pain radiating to the leg (radiculopathy) for more than 6 weeks, and has failed conservative treatment such as physical therapy. A red flag symptom like progressive neurological deficit also qualifies."
        
        files = {
            'file': ('lumbar_mri_policy.txt', synthetic_policy_text, 'text/plain')
        }
        data = {
            'name': 'Lumbar MRI Policy',
            'description': 'Criteria for Lumbar MRI approval'
        }
        
        upload_res = await client.post(
            "/api/policies/",
            headers=headers,
            data=data,
            files=files,
            timeout=120.0
        )
        
        if upload_res.status_code != 200:
            print(f"Upload failed: {upload_res.text}")
            return
            
        result = upload_res.json()
        print("\nUpload Result:")
        print(f"  Policy ID: {result['id']}")
        print(f"  Policy Name: {result['name']}")
        print(f"  Extracted Requirements: {len(result['requirements'])}")
        for req in result['requirements']:
            print(f"    - {req['text']}")
        print(f"  Chunks Indexed: {result['chunks_indexed']}")
        
        print("\nPhase 3 Validation complete!")

if __name__ == "__main__":
    asyncio.run(seed_and_test())
