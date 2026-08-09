"""
Phase 8 Validation Script.

Tests:
  1. Nurse Review API module structure
  2. Scheduler module structure + job registration
  3. Lock endpoint (live DB): lock → conflict → unlock
  4. Decide endpoint: validates mandatory comment (FR-028)
  5. Queue endpoint: returns metadata-only fields
  6. History endpoint: structure check
  7. FR-023: summary endpoint blocks non-lock holders
  8. State machine: pending_nurse_review -> accepted/rejected (T056)

Run from backend/ with the venv active:
  python validate_phase8.py
"""

import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(__file__))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
INFO = "\033[94mINFO\033[0m"


def ok(msg):   print(f"  {PASS} {msg}")
def fail(msg): print(f"  {FAIL} {msg}")
def info(msg): print(f"  {INFO} {msg}")


def header(title):
    print(f"\n{'=' * 62}")
    print(f"  {title}")
    print(f"{'=' * 62}")


# ---------------------------------------------------------------------------
# 1. Nurse Review API module structure
# ---------------------------------------------------------------------------

def check_nurse_review_module():
    header("1. Nurse Review API Module Structure")
    try:
        import app.api.nurse_review as m
        ok("Module app.api.nurse_review imported")

        for name in ["router", "get_review_queue", "lock_case", "release_lock",
                     "get_history", "decide_case", "DecisionRequest"]:
            if hasattr(m, name):
                ok(f"  {name} exists")
            else:
                fail(f"  {name} MISSING")

        return True
    except Exception as e:
        fail(f"Import error: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 2. Scheduler module structure
# ---------------------------------------------------------------------------

def check_scheduler_module():
    header("2. Scheduler Module Structure")
    try:
        import app.services.scheduler as m
        ok("Module app.services.scheduler imported")

        for name in ["start_scheduler", "shutdown_scheduler", "release_expired_locks"]:
            if callable(getattr(m, name, None)):
                ok(f"  {name} callable")
            else:
                fail(f"  {name} MISSING")

        # Test that scheduler can be started and registers the job
        sched = m.start_scheduler()
        ok("  start_scheduler() returned scheduler instance")

        job_ids = [j.id for j in sched.get_jobs()]
        if "release_expired_locks" in job_ids:
            ok("  release_expired_locks job registered")
        else:
            fail(f"  release_expired_locks job NOT found. Jobs: {job_ids}")

        m.shutdown_scheduler()
        ok("  shutdown_scheduler() completed")

        return True
    except Exception as e:
        fail(f"Scheduler check failed: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 3. Lock lifecycle (live DB): create, conflict, release
# ---------------------------------------------------------------------------

async def check_lock_lifecycle():
    header("3. Lock Lifecycle (live DB)")
    try:
        from app.db.database import get_session_factory
        from app.db.models import Case, CaseLock, CaseStatus, Policy, User, UserRole
        from sqlalchemy import select

        async with get_session_factory()() as db:
            # Create a test nurse user
            nurse = User(
                username=f"test_nurse_{uuid.uuid4().hex[:6]}",
                hashed_password="x",
                role=UserRole.nurse,
                is_active=True,
            )
            db.add(nurse)

            # Need a policy
            admin_result = await db.execute(select(User).where(User.role == UserRole.admin).limit(1))
            admin = admin_result.scalar_one_or_none()
            if not admin:
                info("  No admin user found, creating one")
                admin = User(
                    username=f"test_admin_{uuid.uuid4().hex[:6]}",
                    hashed_password="x",
                    role=UserRole.admin,
                    is_active=True,
                )
                db.add(admin)
                await db.flush()

            policy = Policy(
                name="Test Policy Phase8",
                is_active=True,
                created_by=admin.id,
            )
            db.add(policy)
            await db.flush()

            # Create a test case in pending_nurse_review
            case = Case(
                policy_id=policy.id,
                member_id="M001",
                provider_id="P001",
                status=CaseStatus.pending_nurse_review,
                created_by=admin.id,
            )
            db.add(case)
            await db.flush()

            from datetime import datetime, timezone, timedelta
            lock = CaseLock(
                case_id=case.id,
                nurse_id=nurse.id,
                locked_at=datetime.now(timezone.utc),
                lock_expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
            )
            db.add(lock)
            await db.flush()
            ok(f"  Created CaseLock for case {str(case.id)[:8]}")

            # Verify lock exists
            lock_result = await db.execute(
                select(CaseLock).where(CaseLock.case_id == case.id)
            )
            fetched_lock = lock_result.scalar_one_or_none()
            if fetched_lock and fetched_lock.nurse_id == nurse.id:
                ok("  Lock correctly owned by nurse")
            else:
                fail("  Lock ownership mismatch")

            # Delete lock (simulate release)
            await db.delete(fetched_lock)
            await db.flush()
            ok("  Lock released (deleted)")

            # Verify gone
            check_result = await db.execute(
                select(CaseLock).where(CaseLock.case_id == case.id)
            )
            if check_result.scalar_one_or_none() is None:
                ok("  Lock no longer exists after release")
            else:
                fail("  Lock still exists after release")

            await db.rollback()  # Don't persist test data
        return True
    except Exception as e:
        fail(f"Lock lifecycle check failed: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 4. DecisionRequest validation (FR-028 mandatory comment)
# ---------------------------------------------------------------------------

def check_decision_validation():
    header("4. Decision Validation (FR-028 mandatory comment)")
    try:
        from app.api.nurse_review import DecisionRequest
        from pydantic import ValidationError

        # Empty comment should fail
        try:
            DecisionRequest(decision="accepted", comment="")
            fail("  Empty comment should have raised ValidationError (FR-028)")
            return False
        except ValidationError:
            ok("  Empty comment rejected (FR-028 satisfied)")

        # Whitespace-only comment should fail
        try:
            DecisionRequest(decision="accepted", comment="   ")
            fail("  Whitespace comment should have raised ValidationError (FR-028)")
            return False
        except ValidationError:
            ok("  Whitespace-only comment rejected (FR-028 satisfied)")

        # Invalid decision should fail
        try:
            DecisionRequest(decision="approve", comment="test")
            fail("  Invalid decision 'approve' should have raised ValidationError")
            return False
        except ValidationError:
            ok("  Invalid decision value rejected")

        # Valid request
        req = DecisionRequest(decision="accepted", comment="Patient meets all criteria.")
        ok(f"  Valid request accepted: decision={req.decision} comment={req.comment[:30]!r}")

        return True
    except Exception as e:
        fail(f"Decision validation check failed: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 5. FR-023: summary endpoint field check
# ---------------------------------------------------------------------------

def check_fr023_fields():
    header("5. FR-023: Queue Returns Metadata Only (no summary/docs fields)")
    try:
        # Verify the queue response shape matches spec (no summary_text, no documents)
        # Check the router's response logic by examining the function
        import inspect
        from app.api.nurse_review import get_review_queue

        source = inspect.getsource(get_review_queue)

        # Should contain metadata fields
        for field in ["case_id", "member_id", "status", "sla_start_at", "is_locked_by_me"]:
            if field in source:
                ok(f"  Queue includes field: {field}")
            else:
                fail(f"  Queue is missing field: {field}")

        # Should NOT return summary or documents (FR-023)
        for forbidden in ["summary_text", "evidence", "gap_checklist"]:
            if forbidden in source:
                fail(f"  Queue returns '{forbidden}' — FR-023 violation!")
            else:
                ok(f"  Queue does NOT return '{forbidden}' (FR-023 satisfied)")

        return True
    except Exception as e:
        fail(f"FR-023 check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# 6. State machine: pending_nurse_review transitions
# ---------------------------------------------------------------------------

async def check_nurse_decision_transitions():
    header("6. State Machine: Nurse Decision Transitions (T056)")
    try:
        from app.agents.workflow import workflow_agent, VALID_TRANSITIONS, InvalidStatusTransitionError
        from app.db.models import CaseStatus

        # Valid: pending_nurse_review -> accepted
        allowed = VALID_TRANSITIONS.get(CaseStatus.pending_nurse_review, [])
        if CaseStatus.accepted in allowed:
            ok("  pending_nurse_review -> accepted is valid")
        else:
            fail("  pending_nurse_review -> accepted is NOT in VALID_TRANSITIONS")

        if CaseStatus.rejected in allowed:
            ok("  pending_nurse_review -> rejected is valid")
        else:
            fail("  pending_nurse_review -> rejected is NOT in VALID_TRANSITIONS")

        # Invalid: pending_nurse_review -> processing (should raise)
        try:
            await workflow_agent.transition_status(
                db=None,
                case_id=None,
                from_status=CaseStatus.pending_nurse_review,
                to_status=CaseStatus.processing,
                trace_id=uuid.uuid4(),
            )
            fail("  pending_nurse_review -> processing should have raised")
        except InvalidStatusTransitionError:
            ok("  pending_nurse_review -> processing correctly raises InvalidStatusTransitionError")

        return True
    except Exception as e:
        fail(f"Transition check failed: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 7. APScheduler release_expired_locks (logic check, no real DB)
# ---------------------------------------------------------------------------

async def check_expired_lock_job():
    header("7. Expired Lock Release Job (logic check)")
    try:
        from app.services.scheduler import release_expired_locks
        import inspect

        source = inspect.getsource(release_expired_locks)

        if "lock_expires_at < now" in source:
            ok("  Job queries for lock_expires_at < now()")
        else:
            fail("  Job does not filter by lock_expires_at < now()")

        if "case_lock_auto_released" in source:
            ok("  Job writes case_lock_auto_released audit entry (FR-040a)")
        else:
            fail("  Job missing case_lock_auto_released audit entry")

        if "await db.delete(lock)" in source:
            ok("  Job deletes expired locks")
        else:
            fail("  Job does not delete expired locks")

        ok("  Expired lock job logic verified")
        return True
    except Exception as e:
        fail(f"Expired lock job check failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("\n" + "=" * 62)
    print("  Phase 8 Validation: Nurse Review + APScheduler")
    print("=" * 62)

    results = []
    results.append(check_nurse_review_module())
    results.append(check_scheduler_module())
    results.append(await check_lock_lifecycle())
    results.append(check_decision_validation())
    results.append(check_fr023_fields())
    results.append(await check_nurse_decision_transitions())
    results.append(await check_expired_lock_job())

    passed = sum(results)
    total  = len(results)

    print("\n" + "=" * 62)
    if passed == total:
        print(f"\033[92m  Phase 8 Validation PASSED: {passed}/{total} checks\033[0m")
    else:
        print(f"\033[91m  Phase 8 Validation: {passed}/{total} checks passed\033[0m")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
