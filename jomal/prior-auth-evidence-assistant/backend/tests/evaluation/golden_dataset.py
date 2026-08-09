"""
T087 — Synthetic Golden Dataset Schema + Loader.

Defines the GoldenSample dataclass and load_golden_dataset() function.
Synthetic data only — never real PHI (FR-044).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class GoldenSample:
    """
    A single golden evaluation sample for offline RAG quality testing.

    All fields contain synthetic clinical data only (FR-044 — never real PHI).

    Attributes:
        case_document_text:       Synthetic clinical document text to embed.
        policy_requirement:       The policy requirement being evaluated.
        expected_retrieved_chunks: Top-k expected chunk texts (synthetic).
        expected_verdict:         Present | Absent | Unclear
        expected_citation:        Short excerpt the model should cite (or None for Absent).
    """
    case_document_text: str
    policy_requirement: str
    expected_retrieved_chunks: List[str]
    expected_verdict: str          # "Present" | "Absent" | "Unclear"
    expected_citation: Optional[str]

    def __post_init__(self):
        valid_verdicts = {"Present", "Absent", "Unclear"}
        if self.expected_verdict not in valid_verdicts:
            raise ValueError(
                f"expected_verdict must be one of {valid_verdicts}, got '{self.expected_verdict}'"
            )


def load_golden_dataset(path: str | Path) -> List[GoldenSample]:
    """
    Load a golden dataset from a JSON file.

    JSON format: list of dicts with keys matching GoldenSample fields.

    Args:
        path: Path to the JSON file.

    Returns:
        List of GoldenSample instances.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If any sample has an invalid expected_verdict.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Golden dataset file not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    samples = []
    for i, item in enumerate(raw):
        try:
            sample = GoldenSample(
                case_document_text=item["case_document_text"],
                policy_requirement=item["policy_requirement"],
                expected_retrieved_chunks=item.get("expected_retrieved_chunks", []),
                expected_verdict=item["expected_verdict"],
                expected_citation=item.get("expected_citation"),
            )
            samples.append(sample)
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid golden sample at index {i}: {e}") from e

    return samples
