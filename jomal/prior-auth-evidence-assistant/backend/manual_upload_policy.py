import asyncio
import os
import sys
import httpx
import mimetypes

async def main():
    if len(sys.argv) < 2:
        print("Usage: python manual_upload_policy.py <path_to_policy_document>")
        sys.exit(1)

    filepath = sys.argv[1]
    filename = os.path.basename(filepath)
    
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)
        
    policy_name = input(f"Enter a name for the policy (default: {filename}): ").strip()
    if not policy_name:
        policy_name = filename

    mime_type, _ = mimetypes.guess_type(filepath)
    if not mime_type:
        mime_type = "application/octet-stream"

    print(f"\n--- Uploading Policy: {policy_name} ---")
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Login as Admin
        print("Authenticating as admin_user...")
        login_res = await client.post(
            "/api/auth/login",
            data={"username": "admin_user", "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if login_res.status_code != 200:
            print(f"Login failed! Is the backend running on port 8000? Error: {login_res.text}")
            return
            
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Upload the policy document
        print(f"Uploading file '{filename}' to ingestion pipeline... This may take up to a minute.")
        
        with open(filepath, "rb") as f:
            file_bytes = f.read()
            
        files = {
            'file': (filename, file_bytes, mime_type)
        }
        data = {
            'name': policy_name,
            'description': f'Manually uploaded via script.'
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
        print("\n=== SUCCESS ===")
        print(f"Policy ID: {result['id']}")
        print(f"Policy Name: {result['name']}")
        print(f"Total Chunks Indexed in Qdrant: {result['chunks_indexed']}")
        print(f"Extracted Requirements ({len(result['requirements'])} found):")
        for req in result['requirements']:
            print(f"  - [ ] {req['text']}")
        print("=================")

if __name__ == "__main__":
    asyncio.run(main())
