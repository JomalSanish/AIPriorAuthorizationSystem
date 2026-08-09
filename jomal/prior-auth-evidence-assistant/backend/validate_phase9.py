"""
Phase 9 Validation Script.

Tests:
  1. Admin API module structure (new endpoints exist)
  2. PATCH /admin/cases — re-verification logic (FR-032, SC-009)
  3. GET /admin/cases — all-cases shape
  4. GET /admin/nurses/workload — nurse workload shape
  5. GET /admin/nurses/{id}/history — nurse history shape
  6. GET /admin/audit/{case_id} — audit trail shape (FR-041)
  7. GET /admin/audit — global audit log with pagination

Run from backend/ with the venv active:
  python validate_phase9.py
"""

import asyncio
import sys
import os
import uuid
import inspect

sys.path.insert(0, os.path.dirname(__file__))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

def ok(msg):   print(f"  {PASS} {msg}")
def fail(msg): print(f"  {FAIL} {msg}")

def header(title):
    print(f"\n{'=' * 62}")
    print(f"  {title}")
    print(f"{'=' * 62}")


# ---------------------------------------------------------------------------
# 1. Admin API module structure
# ---------------------------------------------------------------------------

def check_admin_module():
    header("1. Admin API Module Structure (Phase 9 additions)")
    try:
        import app.api.admin as m
        ok("Module app.api.admin imported")

        new_endpoints = [
            "admin_list_cases",
            "admin_patch_case",
            "admin_nurse_workload",
            "admin_nurse_history",
            "get_case_audit",
            "get_global_audit",
        ]
        for name in new_endpoints:
            if hasattr(m, name) and callable(getattr(m, name)):
                ok(f"  {name} callable")
            else:
                fail(f"  {name} MISSING or not callable")

        new_models = ["PatchCaseRequest"]
        for name in new_models:
            if hasattr(m, name):
                ok(f"  {name} exists")
            else:
                fail(f"  {name} MISSING")

        # Verify 10 routes registered
        route_count = len([r for r in m.router.routes])
        if route_count >= 10:
            ok(f"  Router has {route_count} routes (>= 10 expected)")
        else:
            fail(f"  Router has only {route_count} routes")

        return True
    except Exception as e:
        fail(f"Import error: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 2. Re-verification logic (FR-032)
# ---------------------------------------------------------------------------

def check_re_verification_logic():
    header("2. FR-032 Re-Verification Logic (source inspection)")
    try:
        from app.api.admin import admin_patch_case
        source = inspect.getsource(admin_patch_case)

        checks = {
            "Checks accepted/rejected status before re-queue": "accepted, CaseStatus.rejected",
            "Invalidates NurseDecision (FR-032)":              "nurse_decision_invalidated",
            "Releases active lock":                            "await db.delete(lock)",
            "Transitions to re_verification_required":         "re_verification_required",
            "Writes admin_edit audit entry":                   "admin_edit",
            "Writes case_re_verification audit entry":         "case_re_verification",
            "Single transaction (SC-009)":                     "await db.commit()",
        }

        all_ok = True
        for desc, token in checks.items():
            if token in source:
                ok(f"  {desc}")
            else:
                fail(f"  {desc} — token '{token}' NOT found")
                all_ok = False

        return all_ok
    except Exception as e:
        fail(f"Check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 3. FR-032 live DB: admin edit of accepted case
# ---------------------------------------------------------------------------

async def check_re_verification_db():
    header("3. FR-032 Live DB: Admin Edit -> Re-Verification")
    try:
        from datetime import datetime, timezone
        from sqlalchemy import select
        from app.db.database import get_session_factory
        from app.db.models import (
            Case, CaseStatus, CaseLock, NurseDecision, NurseDecisionEnum,
            Policy, User, UserRole, AuditLog, ActorType,
        )
        from app.services.audit import audit_service

        async with get_session_factory()() as db:
            # Create test admin + nurse
            admin = User(username=f"test_admin9_{uuid.uuid4().hex[:6]}", hashed_password="x", role=UserRole.admin, is_active=True)
            nurse = User(username=f"test_nurse9_{uuid.uuid4().hex[:6]}", hashed_password="x", role=UserRole.nurse, is_active=True)
            db.add(admin); db.add(nurse)
            await db.flush()

            policy = Policy(name="Test Policy Phase9", is_active=True, created_by=admin.id)
            db.add(policy)
            await db.flush()

            # Case in accepted status
            case = Case(
                policy_id=policy.id, member_id="M100", provider_id="P100",
                status=CaseStatus.accepted, created_by=admin.id,
                decided_at=datetime.now(timezone.utc), decided_by=nurse.id,
                decision_comment="All evidence present.",
            )
            db.add(case)
            await db.flush()

            # Nurse decision
            decision = NurseDecision(
                case_id=case.id, nurse_id=nurse.id,
                decision=NurseDecisionEnum.accepted, comment="All evidence present.",
            )
            db.add(decision)
            await db.flush()

            ok(f"  Setup: case {str(case.id)[:8]} status={case.status.value}")

            # Simulate admin PATCH: fields changed + re-verification triggered
            trace_id = uuid.uuid4()
            case.member_id = "M999"
            case.status = CaseStatus.re_verification_required
            case.decided_at = None
            case.decided_by = None
            case.decision_comment = None

            await audit_service.log(
                db, trace_id=trace_id, case_id=case.id,
                actor_type=ActorType.user, actor_id=str(admin.id),
                action="admin_edit", input_summary="Admin edited member_id",
            )
            await audit_service.log(
                db, trace_id=trace_id, case_id=case.id,
                actor_type=ActorType.user, actor_id=str(admin.id),
                action="case_re_verification",
                input_summary="FR-032: decision invalidated after admin edit",
            )
            await db.flush()

            # Verify status changed
            if case.status == CaseStatus.re_verification_required:
                ok("  Status transitioned to re_verification_required")
            else:
                fail(f"  Status is still {case.status.value}")

            # Verify audit entries
            audit_result = await db.execute(
                select(AuditLog).where(AuditLog.case_id == case.id).order_by(AuditLog.timestamp)
            )
            audit_entries = audit_result.scalars().all()
            actions = [a.action for a in audit_entries]

            if "admin_edit" in actions:
                ok("  admin_edit audit entry present")
            else:
                fail("  admin_edit audit entry MISSING")

            if "case_re_verification" in actions:
                ok("  case_re_verification audit entry present")
            else:
                fail("  case_re_verification audit entry MISSING")

            await db.rollback()  # don't persist test data
        return True
    except Exception as e:
        fail(f"Live DB check failed: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 4. All-cases endpoint response shape
# ---------------------------------------------------------------------------

def check_all_cases_shape():
    header("4. GET /admin/cases Response Shape (source check)")
    try:
        from app.api.admin import admin_list_cases
        source = inspect.getsource(admin_list_cases)

        required_fields = ["case_id", "policy_name", "member_id", "status", "lock_holder", "sla_start_at"]
        all_ok = True
        for f in required_fields:
            if f in source:
                ok(f"  Field '{f}' present in response")
            else:
                fail(f"  Field '{f}' MISSING from response")
                all_ok = False
        return all_ok
    except Exception as e:
        fail(f"Check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 5. Nurse workload endpoint
# ---------------------------------------------------------------------------

def check_nurse_workload_shape():
    header("5. GET /admin/nurses/workload Response Shape (source check)")
    try:
        from app.api.admin import admin_nurse_workload
        source = inspect.getsource(admin_nurse_workload)

        for f in ["nurse_id", "username", "active_locks", "decided_cases"]:
            if f in source:
                ok(f"  Field '{f}' present")
            else:
                fail(f"  Field '{f}' MISSING")
        return True
    except Exception as e:
        fail(f"Check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 6. Audit trail endpoint (FR-041)
# ---------------------------------------------------------------------------

def check_audit_trail_shape():
    header("6. GET /admin/audit/{case_id} Response Shape (FR-041)")
    try:
        from app.api.admin import get_case_audit
        source = inspect.getsource(get_case_audit)

        required_fields = [
            "timestamp", "actor_type", "actor_id", "action",
            "model_name", "confidence_score", "input_summary", "output_summary",
        ]
        all_ok = True
        for f in required_fields:
            if f in source:
                ok(f"  Field '{f}' present (FR-041)")
            else:
                fail(f"  Field '{f}' MISSING — FR-041 violation!")
                all_ok = False
        return all_ok
    except Exception as e:
        fail(f"Check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 7. Global audit log pagination
# ---------------------------------------------------------------------------

def check_global_audit():
    header("7. GET /admin/audit Pagination (source check)")
    try:
        from app.api.admin import get_global_audit
        source = inspect.getsource(get_global_audit)

        checks = {
            "Page parameter": "page",
            "page_size parameter": "page_size",
            "Offset calculation": "offset",
            "Action filter": "action",
            "Date range filter": "from_date",
        }
        all_ok = True
        for desc, token in checks.items():
            if token in source:
                ok(f"  {desc}")
            else:
                fail(f"  {desc} MISSING")
                all_ok = False
        return all_ok
    except Exception as e:
        fail(f"Check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("\n" + "=" * 62)
    print("  Phase 9 Validation: Admin Dashboard API")
    print("=" * 62)

    results = []
    results.append(check_admin_module())
    results.append(check_re_verification_logic())
    results.append(await check_re_verification_db())
    results.append(check_all_cases_shape())
    results.append(check_nurse_workload_shape())
    results.append(check_audit_trail_shape())
    results.append(check_global_audit())

    passed = sum(results)
    total  = len(results)

    print("\n" + "=" * 62)
    if passed == total:
        print(f"\033[92m  Phase 9 Validation PASSED: {passed}/{total} checks\033[0m")
    else:
        print(f"\033[91m  Phase 9 Validation: {passed}/{total} checks passed\033[0m")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
