# Quickstart Guide

This document outlines the startup sequence and requirements for running the Prior Authorization Evidence Assistant.
Reference: T093.

## Prerequisites
- Docker Desktop
- Python 3.11+
- Node.js 18+
- Ollama with `llama3.2:3b` pulled
- CUDA drivers

## Startup Sequence

1. **Pull Model**: Run `ollama pull llama3.2:3b` (Requires internet — one-time step).
2. **Docker Stack**: Run `docker compose up -d` in `docker/`. Wait for Postgres, Qdrant, TEI, and MinIO to be healthy.
3. **Backend Setup**:
   - `cd backend`
   - `pip install -e .` or `pip install -r requirements.txt`
   - `alembic upgrade head`
   - `uvicorn app.main:app --reload`
4. **Frontend Setup**:
   - `cd frontend`
   - `npm install && npm run dev`
5. **Verify**: Visit `GET /api/health` to ensure all services are passing checks (T091).

See `contracts/deployment-spec.md` for more operational details.
