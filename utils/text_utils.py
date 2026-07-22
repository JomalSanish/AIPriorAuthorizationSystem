from __future__ import annotations

import re
from typing import Any


def normalize_text(text: str) -> str:
    """Normalize whitespace and case for simple matching."""
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_keywords(text: str) -> list[str]:
    """Return a simple list of keyword tokens from text."""
    normalized = normalize_text(text)
    return [token for token in re.split(r"[^a-z0-9]+", normalized) if token]


def score_match(text: str, keywords: list[str]) -> int:
    """Score text based on how many provided keywords it contains."""
    normalized = normalize_text(text)
    matches = sum(1 for keyword in keywords if keyword in normalized)
    return matches
