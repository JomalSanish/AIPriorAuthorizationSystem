"""
Script to safely initialize the three core system users (Admin, Intake, Nurse).
Safe to run multiple times (idempotent).
"""

import asyncio
from sqlalchemy import select
from app.db.database import get_session_factory
from app.db.models import User, UserRole
from app.core.security import hash_password

async def create_users():
    async with get_session_factory()() as db:
        
        users_to_create = [
            {"username": "admin_user", "password": "password123", "role": UserRole.admin},
            {"username": "intake_user", "password": "password123", "role": UserRole.intake},
            {"username": "nurse_user", "password": "password123", "role": UserRole.nurse},
        ]
        
        for u in users_to_create:
            # Check if user already exists
            result = await db.execute(select(User).where(User.username == u["username"]))
            existing_user = result.scalar_one_or_none()
            
            if existing_user:
                print(f"{u['username']} already exists. Skipping.")
            else:
                print(f"Creating {u['username']}...")
                new_user = User(
                    username=u["username"],
                    hashed_password=hash_password(u["password"]),
                    role=u["role"],
                    is_active=True
                )
                db.add(new_user)
                await db.commit()
                print(f"Successfully created {u['username']}!")

if __name__ == "__main__":
    asyncio.run(create_users())
