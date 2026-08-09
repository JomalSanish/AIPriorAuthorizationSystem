"""
T076 — Reasoning Agent Unit Tests.

Tests:
  - Present/Absent/Unclear classification
  - Citation extraction for Present/Unclear verdicts
  - Composite confidence score computation (0.4×retrieval + 0.6×llm)
  - All-absent case when no evidence found
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch
from dataclasses import dataclass

from app.agents.reasoning import (
    ReasoningAgent,
    EvidenceClassification,
    RequirementVerdict,
    _RETRIEVAL_WEIGHT,
    _LLM_WEIGHT,
)
from app.agents.retrieval import RetrievalResult


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

class MockRequirement:
    def __init__(self, text="Patient requires prior authorization for lumbar MRI."):
        self.id = uuid.uuid4()
        self.requirement_text = text


def make_chunk(score: float = 0.88, text: str = "Patient had MRI ordered.", doc_id: str = "doc1", page: int = 1) -> RetrievalResult:
    return RetrievalResult(
        chunk_index=0,
        document_id=doc_id,
        document_name="clinical_notes.pdf",
        page_number=page,
        chunk_text=text,
        score=score,
    )


reasoning_agent = ReasoningAgent()


def make_llm_response(classification="Present", llm_confidence=0.9, excerpt="MRI ordered", reasoning="Evidence clearly supports the requirement."):
    return (
        f'{{"classification": "{classification}", '
        f'"citation": {{"document_id": "doc1", "document_name": "clinical_notes.pdf", '
        f'"page_number": 1, "relevant_excerpt": "{excerpt}"}}, '
        f'"llm_confidence": {llm_confidence}, '
        f'"reasoning_text": "{reasoning}"}}'
    )


# ---------------------------------------------------------------------------
# T076a: Classification labels — Present / Absent / Unclear
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_present():
    """Classification returns Present when LLM says Present."""
    chunk = make_chunk(score=0.88)
    req = MockRequirement()

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = make_llm_response("Present", 0.9)
        verdict = await reasoning_agent.classify_requirement(req, [chunk])

    assert verdict.classification == EvidenceClassification.PRESENT


@pytest.mark.asyncio
async def test_classify_absent_with_no_chunks():
    """Classification returns Absent when no chunks are retrieved."""
    req = MockRequirement()

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (
            '{"classification": "Absent", "citation": null, '
            '"llm_confidence": 0.95, "reasoning_text": "No evidence found."}'
        )
        verdict = await reasoning_agent.classify_requirement(req, [])

    assert verdict.classification == EvidenceClassification.ABSENT
    assert verdict.citation is None
    assert verdict.retrieval_score == 0.0


@pytest.mark.asyncio
async def test_classify_unclear():
    """Classification returns Unclear when LLM says Unclear."""
    chunk = make_chunk(score=0.55)
    req = MockRequirement()

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = make_llm_response("Unclear", 0.55, "possibly relevant", "Evidence is ambiguous.")
        verdict = await reasoning_agent.classify_requirement(req, [chunk])

    assert verdict.classification == EvidenceClassification.UNCLEAR


# ---------------------------------------------------------------------------
# T076b: Composite confidence score computation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_composite_confidence_formula():
    """Composite = 0.4 * retrieval_score + 0.6 * llm_confidence."""
    retrieval_score = 0.88
    llm_confidence = 0.88
    expected_composite = _RETRIEVAL_WEIGHT * retrieval_score + _LLM_WEIGHT * llm_confidence

    chunk = make_chunk(score=retrieval_score)
    req = MockRequirement()

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = make_llm_response("Present", llm_confidence)
        verdict = await reasoning_agent.classify_requirement(req, [chunk])

    assert abs(verdict.composite_confidence - expected_composite) < 0.001, (
        f"Expected composite {expected_composite:.4f}, got {verdict.composite_confidence:.4f}"
    )


@pytest.mark.asyncio
async def test_composite_uses_max_retrieval_score():
    """When multiple chunks exist, composite uses the MAX retrieval score."""
    chunks = [make_chunk(score=0.5), make_chunk(score=0.88), make_chunk(score=0.3)]
    expected_max = 0.88
    llm_confidence = 0.80
    expected_composite = _RETRIEVAL_WEIGHT * expected_max + _LLM_WEIGHT * llm_confidence

    req = MockRequirement()

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = make_llm_response("Present", llm_confidence)
        verdict = await reasoning_agent.classify_requirement(req, chunks)

    assert abs(verdict.composite_confidence - expected_composite) < 0.001


# ---------------------------------------------------------------------------
# T076c: Citation extraction
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_citation_present_for_present_verdict():
    """Present verdict must include a citation."""
    chunk = make_chunk(score=0.88)
    req = MockRequirement()

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = make_llm_response("Present", 0.9, "The patient underwent 8 weeks of PT")
        verdict = await reasoning_agent.classify_requirement(req, [chunk])

    assert verdict.citation is not None
    assert verdict.citation.document_name == "clinical_notes.pdf"
    assert verdict.citation.page_number == 1
    assert len(verdict.citation.relevant_excerpt) > 0


@pytest.mark.asyncio
async def test_citation_present_for_unclear_verdict():
    """Unclear verdict must include a citation (for nurse evaluation, FR-022)."""
    chunk = make_chunk(score=0.55)
    req = MockRequirement()

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = make_llm_response("Unclear", 0.55, "ambiguous finding")
        verdict = await reasoning_agent.classify_requirement(req, [chunk])

    assert verdict.citation is not None


@pytest.mark.asyncio
async def test_citation_absent_for_absent_verdict():
    """Absent verdict must have citation=None."""
    req = MockRequirement()

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (
            '{"classification": "Absent", "citation": null, '
            '"llm_confidence": 0.9, "reasoning_text": "No evidence."}'
        )
        verdict = await reasoning_agent.classify_requirement(req, [])

    assert verdict.citation is None


# ---------------------------------------------------------------------------
# T076d: No accept/reject in classifications (Constitution P1)
# ---------------------------------------------------------------------------

def test_classification_enum_has_no_accept_reject():
    """Constitution P1: EvidenceClassification must never include accept/reject."""
    values = {c.value for c in EvidenceClassification}
    assert "accept" not in values
    assert "reject" not in values
    assert "Accept" not in values
    assert "Reject" not in values
    assert values == {"Present", "Absent", "Unclear"}


# ---------------------------------------------------------------------------
# T076e: Reasoning text field
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reasoning_text_returned():
    """reasoning_text field must be non-empty on a successful classification."""
    chunk = make_chunk(score=0.88)
    req = MockRequirement()

    with patch("app.services.ollama.ollama_client.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = make_llm_response("Present", 0.9, "evidence excerpt", "Evidence clearly shows PT was completed.")
        verdict = await reasoning_agent.classify_requirement(req, [chunk])

    assert verdict.reasoning_text
    assert len(verdict.reasoning_text) > 0
