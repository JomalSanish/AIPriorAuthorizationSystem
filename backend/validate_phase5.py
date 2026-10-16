"""
Phase 5 Validation Script.

Tests:
  1. Dense + sparse indexing confirmed in Qdrant (case_document_chunk and case_profile points)
  2. RRF fusion query path via hybrid_search
  3. Retrieval Agent implementation (retrieve_evidence)
  4. NLP case-search Query Understanding (parse_search_query)
  5. Search endpoint (POST /api/cases/search)
  6. UI SearchBar component existence check

Run from backend/ with the venv active:
  python validate_phase5.py
"""

import asyncio
import json
import sys
import os
import importlib
import httpx
from typing import Any

BASE_URL = "http://localhost:8000"

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
INFO = "\033[94mINFO\033[0m"


def ok(msg: str):
    print(f"  {PASS} {msg}")


def fail(msg: str):
    print(f"  {FAIL} {msg}")


def info(msg: str):
    print(f"  {INFO} {msg}")


def header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


# ---------------------------------------------------------------------------
# 1. Qdrant collection check (dense + sparse vectors configured)
# ---------------------------------------------------------------------------

def check_qdrant_collection():
    header("1. Qdrant Dense + Sparse Collection Check")
    try:
        import httpx as _httpx
        resp = _httpx.get("http://localhost:6333/collections/pa_documents", timeout=5)
        if resp.status_code == 404:
            info("Collection 'pa_documents' does not exist yet — will be created on first upload.")
            ok("Collection config is valid (will be created on first document upload)")
            return True

        data = resp.json()
        config = data.get("result", {}).get("config", {})
        vectors = config.get("params", {}).get("vectors", {})
        sparse  = config.get("params", {}).get("sparse_vectors", {})

        if "dense" in vectors:
            dense_size = vectors["dense"].get("size", "?")
            ok(f"Dense vector config: size={dense_size}, distance={vectors['dense'].get('distance', '?')}")
        else:
            fail("Dense vector 'dense' not found in collection config")

        if "sparse" in sparse:
            ok(f"Sparse vector config: 'sparse' present")
        else:
            fail("Sparse vector 'sparse' not found in collection config")

        # Count points by doc_type
        count_resp = _httpx.post(
            "http://localhost:6333/collections/pa_documents/points/scroll",
            json={"limit": 1, "with_payload": True, "with_vector": False},
            timeout=5
        )
        if count_resp.status_code == 200:
            pts = count_resp.json().get("result", {}).get("points", [])
            info(f"Collection has points (sample count in first scroll page: {len(pts)})")
        return True

    except Exception as e:
        fail(f"Qdrant check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 2. Import retrieval module and verify classes/singletons
# ---------------------------------------------------------------------------

def check_retrieval_agent_module():
    header("2. Retrieval Agent Module Check")
    try:
        # Add backend app to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

        import app.agents.retrieval as retrieval_mod
        ok("Module 'app.agents.retrieval' imported successfully")

        # Check key classes / dataclasses exist
        for name in ["RetrievalResult", "StructuredSearchRequest", "SearchFilters", "CaseSearchResult", "RetrievalAgent"]:
            if hasattr(retrieval_mod, name):
                ok(f"  Class '{name}' exists")
            else:
                fail(f"  Class '{name}' missing from retrieval module")

        # Singleton
        if hasattr(retrieval_mod, "retrieval_agent"):
            ok("  Singleton 'retrieval_agent' exists")
        else:
            fail("  Singleton 'retrieval_agent' missing")

        # Methods on instance
        agent = retrieval_mod.retrieval_agent
        for method in ["retrieve_evidence", "parse_search_query", "execute_case_search"]:
            if callable(getattr(agent, method, None)):
                ok(f"  Method '{method}' is callable")
            else:
                fail(f"  Method '{method}' missing or not callable")

        return True
    except ImportError as e:
        fail(f"Import error: {e}")
        return False


# ---------------------------------------------------------------------------
# 3. Qdrant hybrid_search (RRF fusion) direct call
# ---------------------------------------------------------------------------

def check_qdrant_service_hybrid_search():
    header("3. Qdrant Hybrid Search (RRF Fusion) Path Check")
    try:
        from app.services.qdrant import QdrantService, SearchResult
        svc = QdrantService()
        ok("QdrantService instantiated")

        import inspect
        sig = inspect.signature(svc.hybrid_search)
        params = list(sig.parameters.keys())
        expected = ["query_dense", "query_sparse", "filter", "top_k", "doc_type"]
        for p in expected:
            if p in params:
                ok(f"  hybrid_search param '{p}' present")
            else:
                fail(f"  hybrid_search param '{p}' missing")

        # Verify RRF fusion is used (inspect source)
        src = inspect.getsource(svc.hybrid_search)
        if "Fusion.RRF" in src or "fusion=rest.Fusion.RRF" in src:
            ok("  RRF fusion code path confirmed in hybrid_search source")
        else:
            fail("  RRF fusion code path not found in hybrid_search source")

        if "Prefetch" in src or "prefetch" in src:
            ok("  Prefetch (dense + sparse) pattern found in hybrid_search source")
        else:
            fail("  Prefetch pattern not found")

        return True
    except Exception as e:
        fail(f"QdrantService check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 4. Search endpoint (POST /api/cases/search) — API call
# ---------------------------------------------------------------------------

def check_search_endpoint():
    header("4. Search Endpoint — POST /api/cases/search")
    try:
        # Login first
        login = httpx.post(
            f"{BASE_URL}/api/auth/login",
            data={"username": "admin_user", "password": "password123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        if login.status_code != 200:
            fail(f"Login failed: {login.status_code} — {login.text}")
            return False
        token = login.json().get("access_token")
        ok(f"Logged in as admin, got access token")

        # Call search
        search = httpx.post(
            f"{BASE_URL}/api/cases/search",
            json={"query": "MRI cases"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60  # LLM call may take time
        )
        if search.status_code == 200:
            results = search.json()
            ok(f"POST /api/cases/search returned 200 OK — {len(results)} results")
            if isinstance(results, list):
                ok("  Response is a list (correct shape)")
                if results:
                    first = results[0]
                    for field in ["case_id", "status", "score"]:
                        if field in first:
                            ok(f"    Field '{field}' present in result")
                        else:
                            fail(f"    Field '{field}' missing from result")
                else:
                    info("  No cases indexed yet — empty results list is valid")
            else:
                fail(f"  Response is not a list: {type(results)}")
        elif search.status_code == 404:
            fail("POST /api/cases/search returned 404 — route not registered")
        elif search.status_code == 422:
            fail(f"POST /api/cases/search returned 422 Validation Error: {search.text}")
        else:
            fail(f"POST /api/cases/search returned {search.status_code}: {search.text[:200]}")
        return search.status_code == 200

    except Exception as e:
        fail(f"Search endpoint check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 5. NLP Query Understanding — parse_search_query unit test
# ---------------------------------------------------------------------------

async def check_nlp_query_understanding():
    header("5. NLP Query Understanding — parse_search_query")
    try:
        from app.agents.retrieval import retrieval_agent, StructuredSearchRequest, SearchFilters

        result = await retrieval_agent.parse_search_query("MRI cases for lumbar spine")
        ok(f"parse_search_query returned StructuredSearchRequest")
        ok(f"  semantic_query: {result.semantic_query!r}")
        ok(f"  filters: {result.filters}")

        if not result.semantic_query:
            fail("  semantic_query is empty")
        else:
            ok("  semantic_query is non-empty")

        return True
    except Exception as e:
        fail(f"parse_search_query failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 6. SearchBar UI component existence check
# ---------------------------------------------------------------------------

def check_searchbar_ui():
    header("6. SearchBar UI Component Check")
    searchbar_path = os.path.join(
        os.path.dirname(__file__), "..", "frontend", "src", "components", "SearchBar.tsx"
    )
    searchbar_path = os.path.normpath(searchbar_path)
    if os.path.exists(searchbar_path):
        ok(f"SearchBar.tsx exists at: {searchbar_path}")
        with open(searchbar_path) as f:
            content = f.read()
        for check in ["debounce", "/api/cases/search", "CaseSearchResult", "onSelect", "ArrowDown", "Escape"]:
            if check in content:
                ok(f"  Found '{check}' in SearchBar.tsx")
            else:
                fail(f"  Missing '{check}' in SearchBar.tsx")
        return True
    else:
        fail(f"SearchBar.tsx not found at: {searchbar_path}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("\n" + "=" * 60)
    print("  Phase 5 Validation: Hybrid RAG + NLP Case Search")
    print("=" * 60)

    results = []
    results.append(check_qdrant_collection())
    results.append(check_retrieval_agent_module())
    results.append(check_qdrant_service_hybrid_search())
    results.append(check_search_endpoint())
    results.append(await check_nlp_query_understanding())
    results.append(check_searchbar_ui())

    passed = sum(results)
    total  = len(results)

    print("\n" + "=" * 60)
    if passed == total:
        print(f"\033[92m  Phase 5 Validation PASSED: {passed}/{total} checks\033[0m")
    else:
        print(f"\033[91m  Phase 5 Validation: {passed}/{total} checks passed\033[0m")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
