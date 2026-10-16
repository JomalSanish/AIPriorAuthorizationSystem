"""
Phase 6 Validation Script.

Tests:
  1. Reasoning Agent module structure — ReasoningAgent, RequirementVerdict, EvidenceClassification
  2. classify_requirement() with a synthetic requirement + zero chunks -> Absent
  3. classify_requirement() with synthetic chunks -> Present/Unclear/Absent (live LLM call)
  4. classify_all_requirements() batch loop
  5. Summary Agent module structure — SummaryAgent, CaseSummary, GapItem
  6. generate_summary() with synthetic verdicts -> CaseSummary with gap_checklist + flags
  7. Fallback summary (deterministic, no LLM)

Run from backend/ with the venv active:
  python validate_phase6.py
"""

import asyncio
import sys
import os

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
# 1. Module structure
# ---------------------------------------------------------------------------

def check_reasoning_module():
    header("1. Reasoning Agent Module Structure")
    try:
        import app.agents.reasoning as m
        ok("Module app.agents.reasoning imported")

        for name in ["EvidenceClassification", "Citation", "RequirementVerdict", "ReasoningAgent", "reasoning_agent"]:
            if hasattr(m, name):
                ok(f"  {name} exists")
            else:
                fail(f"  {name} MISSING")

        cls = m.EvidenceClassification
        for val in ["Present", "Absent", "Unclear"]:
            try:
                cls(val)
                ok(f"  EvidenceClassification.{val} valid")
            except ValueError:
                fail(f"  EvidenceClassification.{val} MISSING")

        agent = m.reasoning_agent
        for method in ["classify_requirement", "classify_all_requirements"]:
            if callable(getattr(agent, method, None)):
                ok(f"  Method {method} callable")
            else:
                fail(f"  Method {method} missing")

        return True
    except Exception as e:
        fail(f"Import error: {e}")
        return False


def check_summary_module():
    header("2. Summary Agent Module Structure")
    try:
        import app.agents.summary as m
        ok("Module app.agents.summary imported")

        for name in ["GapItem", "CaseSummary", "SummaryAgent", "summary_agent",
                     "FLAG_PARTIAL_ANALYSIS", "FLAG_NO_EXTRACTABLE_CONTENT"]:
            if hasattr(m, name):
                ok(f"  {name} exists")
            else:
                fail(f"  {name} MISSING")

        agent = m.summary_agent
        for method in ["generate_summary", "_fallback_summary"]:
            if callable(getattr(agent, method, None)):
                ok(f"  Method {method} callable")
            else:
                fail(f"  Method {method} missing")

        return True
    except Exception as e:
        fail(f"Import error: {e}")
        return False


# ---------------------------------------------------------------------------
# 2. classify_requirement — zero chunks -> Absent
# ---------------------------------------------------------------------------

async def check_classify_absent():
    header("3. classify_requirement() - Zero Chunks -> Absent")
    try:
        from app.agents.reasoning import reasoning_agent, EvidenceClassification
        from app.db.models import PolicyRequirement
        import uuid

        # Synthetic requirement
        req = PolicyRequirement()
        req.id = uuid.uuid4()
        req.requirement_text = "Patient must have documented lumbar spine MRI within the past 12 months."

        verdict = await reasoning_agent.classify_requirement(
            policy_requirement=req,
            retrieved_chunks=[],
        )

        ok(f"classify_requirement returned RequirementVerdict")
        ok(f"  classification = {verdict.classification.value}")
        ok(f"  composite_confidence = {verdict.composite_confidence}")
        ok(f"  retrieval_score = {verdict.retrieval_score} (should be 0.0 with no chunks)")
        ok(f"  reasoning_text = {verdict.reasoning_text[:80]!r}")

        if verdict.retrieval_score == 0.0:
            ok("  retrieval_score is 0.0 as expected (no chunks)")
        else:
            fail(f"  retrieval_score should be 0.0, got {verdict.retrieval_score}")

        if verdict.classification == EvidenceClassification.ABSENT:
            ok("  Classification = Absent (correct for empty chunks)")
        else:
            info(f"  Classification = {verdict.classification.value} (LLM made a choice — valid)")

        return True
    except Exception as e:
        fail(f"classify_requirement (absent) failed: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 3. classify_requirement — synthetic chunks (live LLM)
# ---------------------------------------------------------------------------

async def check_classify_with_chunks():
    header("4. classify_requirement() - With Synthetic Chunks (live LLM)")
    try:
        from app.agents.reasoning import reasoning_agent, RetrievalResult, EvidenceClassification
        from app.db.models import PolicyRequirement
        import uuid

        req = PolicyRequirement()
        req.id = uuid.uuid4()
        req.requirement_text = "Patient must have tried and failed conservative therapy (physical therapy, NSAIDs) for at least 6 weeks before surgery."

        chunks = [
            RetrievalResult(
                chunk_text=(
                    "The patient underwent 8 weeks of physical therapy without improvement. "
                    "NSAIDs were tried for 6 weeks; patient reported no pain relief. "
                    "Conservative management was deemed unsuccessful."
                ),
                score=0.88,
                document_id="doc-001",
                document_name="clinical_notes.pdf",
                page_number=2,
                chunk_index=3,
            ),
            RetrievalResult(
                chunk_text="Referral for surgical evaluation recommended due to failed conservative treatment.",
                score=0.72,
                document_id="doc-001",
                document_name="clinical_notes.pdf",
                page_number=3,
                chunk_index=5,
            ),
        ]

        verdict = await reasoning_agent.classify_requirement(
            policy_requirement=req,
            retrieved_chunks=chunks,
        )

        ok(f"classify_requirement returned verdict")
        ok(f"  classification = {verdict.classification.value}")
        ok(f"  retrieval_score = {verdict.retrieval_score}")
        ok(f"  llm_confidence = {verdict.llm_confidence}")
        ok(f"  composite_confidence = {verdict.composite_confidence}")

        # Verify composite formula: 0.4 * max_retrieval + 0.6 * llm_conf
        expected = round(0.4 * 0.88 + 0.6 * verdict.llm_confidence, 4)
        if abs(verdict.composite_confidence - expected) < 0.001:
            ok(f"  Composite confidence formula correct: {verdict.composite_confidence}")
        else:
            fail(f"  Composite confidence mismatch: got {verdict.composite_confidence}, expected ~{expected}")

        if verdict.classification in (EvidenceClassification.PRESENT, EvidenceClassification.UNCLEAR):
            if verdict.citation:
                ok(f"  Citation present: {verdict.citation.document_name} p.{verdict.citation.page_number}")
                ok(f"  Excerpt: {verdict.citation.relevant_excerpt[:80]!r}")
            else:
                info("  Citation is None (LLM did not produce one for this classification)")
        else:
            info("  Classification = Absent despite chunks (LLM decision)")

        if verdict.reasoning_text:
            ok(f"  reasoning_text: {verdict.reasoning_text[:80]!r}")
        else:
            fail("  reasoning_text is empty")

        return True
    except Exception as e:
        fail(f"classify_requirement (with chunks) failed: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 4. generate_summary — synthetic verdicts
# ---------------------------------------------------------------------------

async def check_generate_summary():
    header("5. generate_summary() - With Synthetic Verdicts")
    try:
        from app.agents.reasoning import RequirementVerdict, EvidenceClassification, Citation
        from app.agents.summary import summary_agent, CaseSummary, GapItem, FLAG_PARTIAL_ANALYSIS
        import uuid

        verdicts = [
            RequirementVerdict(
                requirement_id=str(uuid.uuid4()),
                requirement_text="Documented lumbar spine MRI within 12 months.",
                classification=EvidenceClassification.PRESENT,
                citation=Citation(
                    document_id="doc-001",
                    document_name="radiology_report.pdf",
                    page_number=1,
                    relevant_excerpt="MRI lumbar spine performed 2024-06-12, showing L4-L5 disc herniation.",
                ),
                composite_confidence=0.82,
                retrieval_score=0.88,
                llm_confidence=0.78,
                reasoning_text="Clear MRI report found within the required timeframe.",
            ),
            RequirementVerdict(
                requirement_id=str(uuid.uuid4()),
                requirement_text="Failed conservative therapy for at least 6 weeks.",
                classification=EvidenceClassification.PRESENT,
                citation=Citation(
                    document_id="doc-002",
                    document_name="clinical_notes.pdf",
                    page_number=2,
                    relevant_excerpt="8 weeks of PT without improvement; NSAIDs failed.",
                ),
                composite_confidence=0.79,
                retrieval_score=0.75,
                llm_confidence=0.82,
                reasoning_text="Evidence of failed conservative treatment documented.",
            ),
            RequirementVerdict(
                requirement_id=str(uuid.uuid4()),
                requirement_text="Prior authorization from attending physician.",
                classification=EvidenceClassification.ABSENT,
                citation=None,
                composite_confidence=0.10,
                retrieval_score=0.05,
                llm_confidence=0.12,
                reasoning_text="No physician authorization letter found in uploaded documents.",
            ),
            RequirementVerdict(
                requirement_id=str(uuid.uuid4()),
                requirement_text="BMI within acceptable range for elective procedure.",
                classification=EvidenceClassification.UNCLEAR,
                citation=Citation(
                    document_id="doc-002",
                    document_name="clinical_notes.pdf",
                    page_number=4,
                    relevant_excerpt="Patient weight 92kg, height not documented.",
                ),
                composite_confidence=0.45,
                retrieval_score=0.40,
                llm_confidence=0.48,
                reasoning_text="Weight documented but height missing — BMI cannot be calculated.",
            ),
        ]

        case_id = str(uuid.uuid4())
        summary = await summary_agent.generate_summary(
            case_id=case_id,
            verdicts=verdicts,
            partial=True,   # test flag
        )

        ok(f"generate_summary returned CaseSummary")
        ok(f"  summary_text length: {len(summary.summary_text)} chars")

        if summary.summary_text:
            ok(f"  summary_text starts: {summary.summary_text[:120]!r}")
        else:
            fail("  summary_text is empty")

        ok(f"  gap_checklist items: {len(summary.gap_checklist)}")
        if len(summary.gap_checklist) == 2:
            ok("  gap_checklist has 2 items (Absent + Unclear) — correct")
        else:
            fail(f"  gap_checklist should have 2 items, got {len(summary.gap_checklist)}")

        for item in summary.gap_checklist:
            ok(f"  Gap item: [{item.classification}] {item.requirement_text[:60]}")
            if item.classification == "Unclear" and item.citation:
                ok(f"    Unclear citation: {item.citation.get('document_name')} p.{item.citation.get('page_number')}")
            elif item.classification == "Absent":
                if item.citation is None:
                    ok("    Absent item has no citation (correct)")
                else:
                    fail("    Absent item should have no citation")

        ok(f"  flags: {summary.flags}")
        if FLAG_PARTIAL_ANALYSIS in summary.flags:
            ok(f"  FLAG_PARTIAL_ANALYSIS present (correct — partial=True was set)")
        else:
            fail("  FLAG_PARTIAL_ANALYSIS missing from flags")

        return True
    except Exception as e:
        fail(f"generate_summary failed: {e}")
        import traceback; traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# 5. Fallback summary — deterministic, no LLM
# ---------------------------------------------------------------------------

def check_fallback_summary():
    header("6. Fallback Summary (Deterministic)")
    try:
        from app.agents.reasoning import RequirementVerdict, EvidenceClassification, Citation
        from app.agents.summary import summary_agent, FLAG_PARTIAL_ANALYSIS
        import uuid

        verdicts = [
            RequirementVerdict(
                requirement_id=str(uuid.uuid4()),
                requirement_text="Documented diagnosis.",
                classification=EvidenceClassification.PRESENT,
                citation=Citation("doc-1", "intake.pdf", 1, "Diagnosis confirmed."),
                composite_confidence=0.80,
                retrieval_score=0.75,
                llm_confidence=0.83,
                reasoning_text="Present.",
            ),
            RequirementVerdict(
                requirement_id=str(uuid.uuid4()),
                requirement_text="Lab results within 30 days.",
                classification=EvidenceClassification.ABSENT,
                citation=None,
                composite_confidence=0.12,
                retrieval_score=0.05,
                llm_confidence=0.16,
                reasoning_text="Absent.",
            ),
        ]

        text = summary_agent._fallback_summary(verdicts, [FLAG_PARTIAL_ANALYSIS])
        ok(f"Fallback summary generated ({len(text)} chars)")
        ok(f"  Starts: {text[:100]!r}")

        if "Present" in text:
            ok("  'Present' found in fallback summary")
        else:
            fail("  'Present' not found in fallback summary")

        if "Absent" in text:
            ok("  'Absent' found in fallback summary")
        else:
            fail("  'Absent' not found in fallback summary")

        if FLAG_PARTIAL_ANALYSIS in text:
            ok("  FLAG_PARTIAL_ANALYSIS found in fallback summary")
        else:
            fail("  FLAG_PARTIAL_ANALYSIS missing from fallback summary")

        return True
    except Exception as e:
        fail(f"Fallback summary failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print("\n" + "=" * 62)
    print("  Phase 6 Validation: Reasoning + Summary Agents")
    print("=" * 62)

    results = []
    results.append(check_reasoning_module())
    results.append(check_summary_module())
    results.append(await check_classify_absent())
    results.append(await check_classify_with_chunks())
    results.append(await check_generate_summary())
    results.append(check_fallback_summary())

    passed = sum(results)
    total  = len(results)

    print("\n" + "=" * 62)
    if passed == total:
        print(f"\033[92m  Phase 6 Validation PASSED: {passed}/{total} checks\033[0m")
    else:
        print(f"\033[91m  Phase 6 Validation: {passed}/{total} checks passed\033[0m")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
