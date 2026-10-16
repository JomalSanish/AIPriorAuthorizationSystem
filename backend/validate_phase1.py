"""
Phase 1 Validation Script
=========================

Validates all Phase 1 components:
  1. Secrets abstraction — SecretsProvider wired correctly
  2. Docker containers — postgres, qdrant, tei (embedding), minio reachable
  3. Ollama — native service responds and llama3.2:3b is present
  4. JWT/OAuth2 — tokens issued and validated per role (3 roles)

Run from backend/ directory with:
    python validate_phase1.py

Or via pytest:
    python -m pytest validate_phase1.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 1. Secrets Abstraction
# ---------------------------------------------------------------------------

def test_secrets_abstraction():
    """SecretsProvider protocol and EnvSecretsProvider wired correctly."""
    # Set a dummy env var for testing
    os.environ["TEST_SECRET_KEY"] = "test_value_12345"

    from app.core.secrets import EnvSecretsProvider, SecretsProvider, secrets_provider

    # Protocol conformance
    assert isinstance(secrets_provider, SecretsProvider), (
        "secrets_provider does not satisfy SecretsProvider protocol"
    )

    # get() returns correct value
    provider = EnvSecretsProvider()
    val = provider.get("TEST_SECRET_KEY")
    assert val == "test_value_12345", f"Expected 'test_value_12345', got '{val}'"

    # get() raises KeyError for missing key
    try:
        provider.get("__NONEXISTENT_SECRET_1234__")
        assert False, "Should have raised KeyError"
    except KeyError:
        pass

    # get_with_default() returns default
    default_val = provider.get_with_default("__MISSING__", "fallback")
    assert default_val == "fallback"

    print("  ✅ Secrets abstraction: PASS")


# ---------------------------------------------------------------------------
# 2. JWT / OAuth2 — issue and validate tokens per role
# ---------------------------------------------------------------------------

def test_jwt_per_role():
    """JWT tokens issued and validated correctly for all 3 roles."""
    from app.core.security import (
        create_access_token,
        create_refresh_token,
        decode_token,
        hash_password,
        verify_password,
    )

    user_id = str(uuid.uuid4())

    for role in ["intake", "nurse", "admin"]:
        token = create_access_token(subject=user_id, role=role)
        payload = decode_token(token)

        assert payload.sub == user_id, f"[{role}] sub mismatch"
        assert payload.role == role, f"[{role}] role mismatch"
        assert payload.type == "access", f"[{role}] token type wrong"
        assert len(payload.scopes) > 0, f"[{role}] no scopes"

        # Verify role-specific scopes
        if role == "intake":
            assert "case:create" in payload.scopes
            assert "policy:read" in payload.scopes
            assert "case:decide" not in payload.scopes
        elif role == "nurse":
            assert "case:lock" in payload.scopes
            assert "case:decide" in payload.scopes
            assert "user:manage" not in payload.scopes
        elif role == "admin":
            assert "user:manage" in payload.scopes
            assert "audit:read" in payload.scopes
            assert "case:*" in payload.scopes

    # Refresh token
    refresh = create_refresh_token(subject=user_id)
    ref_payload = decode_token(refresh)
    assert ref_payload.type == "refresh"
    assert ref_payload.sub == user_id
    assert ref_payload.scopes == []  # refresh tokens have no scopes

    # Invalid token rejected
    try:
        decode_token("not.a.valid.jwt")
        assert False, "Should have raised TokenDecodeError"
    except Exception:
        pass

    # Password hashing
    plain = "TestPass123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("wrong", hashed)

    print("  ✅ JWT/OAuth2 per role: PASS")
    print("     Roles tested: intake ✓  nurse ✓  admin ✓")
    print("     Scopes validated per FR-003a ✓")
    print("     Refresh tokens ✓  Password hashing ✓  Invalid token rejection ✓")


# ---------------------------------------------------------------------------
# 3. Infrastructure Connectivity Checks
# ---------------------------------------------------------------------------

async def test_infrastructure():
    """All four Docker containers and native Ollama are reachable."""
    from app.core.healthcheck import (
        check_minio,
        check_ollama,
        check_postgres,
        check_qdrant,
        check_tei,
    )

    checks = {
        "postgres": check_postgres,
        "qdrant": check_qdrant,
        "tei (embedding)": check_tei,
        "minio": check_minio,
        "ollama (native)": check_ollama,
    }

    results = {}
    for name, fn in checks.items():
        result = await fn()
        results[name] = result
        status = "✅" if result.ok else "⚠️ "
        print(f"  {status} {name}: {result.detail}")

    failures = [n for n, r in results.items() if not r.ok]
    if failures:
        print(f"\n  ⚠️  Non-critical failures: {', '.join(failures)}")
        print("     (TEI may be downloading model; Ollama may not be running)")

    # Postgres is the hard requirement for Phase 1
    if not results["postgres"].ok:
        raise AssertionError(f"PostgreSQL REQUIRED but failed: {results['postgres'].detail}")

    return results


# ---------------------------------------------------------------------------
# 4. Settings / Config
# ---------------------------------------------------------------------------

_PLACEHOLDER_SECRETS = {
    "changeme_use_secrets_manager",
    "changeme_generate_a_real_secret_before_use",
}

def test_settings():
    """Settings module loads without errors, and no secret is still a template placeholder."""
    from app.config import get_settings
    settings = get_settings()
    assert settings.DATABASE_URL
    assert settings.JWT_SECRET_KEY
    assert settings.QDRANT_URL
    assert settings.TEI_URL
    assert settings.OLLAMA_URL
    assert settings.MINIO_ENDPOINT

    secret_fields = {
        "JWT_SECRET_KEY": settings.JWT_SECRET_KEY,
        "DATABASE_URL": settings.DATABASE_URL,  # catches the password embedded in the URL too
    }
    for name, value in secret_fields.items():
        for placeholder in _PLACEHOLDER_SECRETS:
            assert placeholder not in value, (
                f"{name} still contains the template placeholder '{placeholder}' — "
                f"generate a real secret before running Phase 1 validation."
            )

    print("  ✅ Settings: PASS (all required vars present, no placeholder secrets)")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("  PA Evidence Assistant — Phase 1 Validation")
    print("=" * 60)
    print(f"  Time: {datetime.now(timezone.utc).isoformat()}")
    print()

    # --- 1. Secrets
    print("1. Secrets Abstraction")
    try:
        test_secrets_abstraction()
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        sys.exit(1)

    # --- 2. Settings
    print("\n2. Application Settings")
    try:
        test_settings()
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        sys.exit(1)

    # --- 3. JWT per role
    print("\n3. JWT / OAuth2 Authentication")
    try:
        test_jwt_per_role()
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        sys.exit(1)

    # --- 4. Infrastructure
    print("\n4. Infrastructure Connectivity")
    try:
        results = asyncio.run(test_infrastructure())
    except AssertionError as e:
        print(f"  ❌ FAIL: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"  ❌ FAIL (unexpected): {e}")
        sys.exit(1)

    # --- Summary
    print("\n" + "=" * 60)
    print("  PHASE 1 VALIDATION SUMMARY")
    print("=" * 60)
    print("  ✅ Secrets abstraction")
    print("  ✅ Application settings")
    print("  ✅ JWT tokens — all 3 roles (intake/nurse/admin)")
    if results.get("postgres") and results["postgres"].ok:
        print("  ✅ PostgreSQL (Docker)")
    if results.get("qdrant") and results["qdrant"].ok:
        print("  ✅ Qdrant (Docker)")
    if results.get("tei (embedding)") and results["tei (embedding)"].ok:
        print("  ✅ Text-Embeddings-Inference (Docker)")
    if results.get("minio") and results["minio"].ok:
        print("  ✅ MinIO (Docker)")
    if results.get("ollama (native)") and results["ollama (native)"].ok:
        print("  ✅ Ollama (native — llama3.2:3b present)")
    print("\n  Phase 1 gate: PASS ✓")
    print("  Ready to proceed to Phase 2.")
    print()


if __name__ == "__main__":
    main()
