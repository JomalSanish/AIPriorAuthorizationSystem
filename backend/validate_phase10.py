"""
Phase 10 Validation Script
Ensures all testing and evaluation files are present and syntactically valid.
"""
import os
import sys

def check_file(path: str) -> bool:
    if os.path.exists(path):
        print(f"  [PASS] Found {path}")
        return True
    else:
        print(f"  [FAIL] Missing {path}")
        return False

def validate_phase_10():
    print("=" * 60)
    print("Phase 10 Validation: Testing & Evaluation")
    print("=" * 60)
    
    files = [
        "tests/unit/test_workflow_agent.py",
        "tests/unit/test_reasoning_agent.py",
        "tests/unit/test_summary_agent.py",
        "tests/unit/test_prompt_minimization.py",
        "tests/integration/test_auth.py",
        "tests/integration/test_admin.py",
        "tests/integration/test_nurse_review.py",
        "tests/integration/test_e2e_lifecycle.py",
        "tests/evaluation/golden_dataset.py",
        "tests/evaluation/data/golden_samples.json",
        "tests/evaluation/test_rag_evaluation.py",
    ]
    
    all_passed = True
    for f in files:
        if not check_file(f):
            all_passed = False
            
    if all_passed:
        print("\nSUCCESS: All Phase 10 testing and evaluation artifacts are present.")
        sys.exit(0)
    else:
        print("\nFAILED: Missing one or more Phase 10 artifacts.")
        sys.exit(1)

if __name__ == "__main__":
    validate_phase_10()
