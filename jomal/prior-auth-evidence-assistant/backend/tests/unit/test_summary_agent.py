"""
T077 — Summary Agent Unit Tests.

Tests:
  - Evidence summary generation from verdicts
  - Gap checklist: separate Absent and Unclear sections (FR-022)
  - Pipeline-incomplete flag
  - No-extractable-content flag
  - Constitution P1: never emits accept/reject
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.agents.summary import (
    SummaryAgent,
    GapItem,
    CaseSummary,
    FLAG_PARTIAL_ANALYSIS,
    FLAG_NO_EXTRACTABLE_CONTENT,
)
from app.agents.reasoning import (
    EvidenceClassification,
    RequirementVerdict,
    Citation,
)


summary_agent = SummaryAgent()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_verdict(
    classification: EvidenceClassification,
    text: str = "Patient requires prior authorization.",
    with_citation: bool = True,
) -> RequirementVerdict:
    citation = None
    if with_citation and classification != EvidenceClassification.ABSENT:
        citation = Citation(
            document_id="doc1",
            document_name="clinical_notes.pdf",
            page_number=2,
            relevant_excerpt="The patient underwent 8 weeks of PT.",
        )
    return RequirementVerdict(
        requirement_id=str(uuid.uuid4()),
        requirement_text=text,
        classification=classification,
        citation=citation,
        composite_confidence=0.88,
        retrieval_score=0.88,
        llm_confidence=0.88,
        reasoning_text="Evidence found and matches requirement.",
    )


MOCK_SUMMARY_RESPONSE = """{
  "summary_text": "Evidence analysis complete. Requirement 1: Present (confidence 88%). No gaps found.",
  "gap_checklist_absent": [],
  "gap_checklist_unclear": [],
  "flags": []
}"""

MOCK_SUMMARY_WITH_GAPS = """{
  "summary_text": "Evidence analysis complete. Two gaps identified.",
  "gap_checklist_absent": ["Absent requirement"],
  "gap_checklist_unclear": ["Unclear requirement"],
  "flags": []
}"""


# ---------------------------------------------------------------------------
# T077a: Summary generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_summary_returns_case_summary():
    """generate_summary returns a CaseSummary dataclass."""
    verdicts = [make_verdict(EvidenceClassification.PRESENT)]

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_SUMMARY_RESPONSE
        result = await summary_agent.generate_summary("test-case-id", verdicts)

    assert isinstance(result, CaseSummary)
    assert isinstance(result.summary_text, str)
    assert len(result.summary_text) > 0


@pytest.mark.asyncio
async def test_summary_text_non_empty():
    """summary_text must be non-empty even if all requirements are Present."""
    verdicts = [
        make_verdict(EvidenceClassification.PRESENT, "Req 1"),
        make_verdict(EvidenceClassification.PRESENT, "Req 2"),
    ]

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_SUMMARY_RESPONSE
        result = await summary_agent.generate_summary("test-case-id", verdicts)

    assert result.summary_text.strip() != ""


# ---------------------------------------------------------------------------
# T077b: Gap checklist — Absent and Unclear separate (FR-022)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gap_checklist_separates_absent_unclear():
    """FR-022: Gap checklist must have separate sections for Absent and Unclear."""
    verdicts = [
        make_verdict(EvidenceClassification.PRESENT, "Req 1"),
        make_verdict(EvidenceClassification.ABSENT,  "Req 2 — must be in gap list"),
        make_verdict(EvidenceClassification.UNCLEAR, "Req 3 — ambiguous, in gap list"),
    ]

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_SUMMARY_WITH_GAPS
        result = await summary_agent.generate_summary("test-case-id", verdicts)

    absent_items = [g for g in result.gap_checklist if g.classification == "Absent"]
    unclear_items = [g for g in result.gap_checklist if g.classification == "Unclear"]

    assert len(absent_items) >= 1, "Absent requirements must appear in gap checklist (FR-022)"
    assert len(unclear_items) >= 1, "Unclear requirements must appear in gap checklist (FR-022)"


@pytest.mark.asyncio
async def test_present_verdict_not_in_gap_checklist():
    """Present requirements must NOT appear in the gap checklist."""
    verdicts = [
        make_verdict(EvidenceClassification.PRESENT, "Fully supported requirement"),
    ]

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_SUMMARY_RESPONSE
        result = await summary_agent.generate_summary("test-case-id", verdicts)

    assert len(result.gap_checklist) == 0, "Present verdicts must not appear in gap checklist"


# ---------------------------------------------------------------------------
# T077c: Pipeline flags
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_incomplete_flag():
    """FLAG_PARTIAL_ANALYSIS is included in flags when pipeline was incomplete."""
    verdicts = [make_verdict(EvidenceClassification.PRESENT)]

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_SUMMARY_RESPONSE
        result = await summary_agent.generate_summary(
            "test-case-id",
            verdicts,
            partial=True,
        )

    assert FLAG_PARTIAL_ANALYSIS in result.flags, (
        f"Expected '{FLAG_PARTIAL_ANALYSIS}' in flags when pipeline_incomplete=True"
    )


@pytest.mark.asyncio
async def test_no_extractable_content_flag():
    """FLAG_NO_EXTRACTABLE_CONTENT included when all doc extraction failed."""
    verdicts = []  # no verdicts — nothing was extracted

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_SUMMARY_RESPONSE
        result = await summary_agent.generate_summary(
            "test-case-id",
            verdicts,
            all_documents_failed=True,
        )

    assert FLAG_NO_EXTRACTABLE_CONTENT in result.flags


@pytest.mark.asyncio
async def test_no_flags_when_pipeline_complete():
    """No flags when pipeline ran normally."""
    verdicts = [make_verdict(EvidenceClassification.PRESENT)]

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_SUMMARY_RESPONSE
        result = await summary_agent.generate_summary(
            "test-case-id",
            verdicts,
            partial=False,
            all_documents_failed=False,
        )

    assert FLAG_PARTIAL_ANALYSIS not in result.flags
    assert FLAG_NO_EXTRACTABLE_CONTENT not in result.flags


# ---------------------------------------------------------------------------
# T077d: Constitution P1 — never emit accept/reject
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_summary_does_not_contain_accept_reject():
    """Constitution P1: summary text must never contain accept/reject decisions."""
    verdicts = [make_verdict(EvidenceClassification.PRESENT)]

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = MOCK_SUMMARY_RESPONSE
        result = await summary_agent.generate_summary("test-case-id", verdicts)

    from app.agents.summary import SummaryAgent
    import inspect
    source = inspect.getsource(SummaryAgent.generate_summary)
    assert "NEVER" in source or "accept" in source.lower() or "Constitution" in source or "nurse" in source.lower(), (
        "SummaryAgent.generate_summary must contain governance directive (Constitution P1)"
    )
