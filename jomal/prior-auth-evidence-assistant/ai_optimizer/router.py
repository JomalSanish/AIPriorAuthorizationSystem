"""Rule-based model router (stdlib only), identical in behaviour to the TS core ``RouterRules``.

Key exports: ``RouteDecision``, ``route``, ``get_model``, ``load_router_config``.
Rules (see RouterRulesSchema in core): advanced keyword -> "advanced"; short prompt without tools
-> "economy"; else ``defaultTier``; ``needs_tools`` raises to at least ``needsToolsMinTier``; the
model is the first candidate of the chosen tier. Parity: packages/fixtures/router.
Feature: model router (Python runtime). Messages are measured as their string contents joined
with ``"\\n"``, in code points; keywords match case-insensitively on ASCII word boundaries.
An empty tier falls back upward (economy -> standard -> advanced), then downward; the decision's
``tier`` is the tier the model came from. ``get_model`` logs each decision on the ``ai_optimizer``
logger (INFO ``route: <tier> <provider>/<model> (<reason>)``), like ``ModelRouterMiddleware``.

``router_config.json`` (written next to this module by the exporter) is a ``RouterConfig``::

    {"presetId": str,
     "tiers": {"economy": [{"modelId": str, "providerId": str}], "standard": [...],
               "advanced": [...]},
     "rules": {"maxCharsForEconomy": int, "advancedKeywords": [str],
               "needsToolsMinTier": tier, "defaultTier": tier}}
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_PATH = Path(__file__).with_name("router_config.json")
logger = logging.getLogger("ai_optimizer")


@dataclass(frozen=True)
class RouteDecision:
    """Result of routing one prompt: the model to call and why."""

    model: str
    provider: str
    tier: str
    reason: str


def load_router_config(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load a ``RouterConfig`` JSON (defaults to the exported ``router_config.json``)."""
    with open(path or _DEFAULT_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


_TIERS = ("economy", "standard", "advanced")
# Catalog provider id -> ``init_chat_model`` model_provider.
_LC_PROVIDERS = {"google": "google_genai", "mistral": "mistralai"}


@lru_cache(maxsize=1)
def _default_config() -> dict[str, Any]:
    return load_router_config()


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # LangChain content blocks
        return "".join(
            b if isinstance(b, str) else str(b.get("text", ""))
            for b in content
            if isinstance(b, str) or (isinstance(b, dict) and b.get("type") == "text")
        )
    return ""


def _measure_text(messages_or_text: Any) -> str:
    if isinstance(messages_or_text, str):
        return messages_or_text
    parts = []
    for m in messages_or_text:
        if isinstance(m, dict):
            content = m.get("content")
        elif isinstance(m, tuple):
            content = m[1]
        else:
            content = getattr(m, "content", None)
        parts.append(_text_of(content))
    return "\n".join(parts)


def _keyword_hit(text: str, keywords: list[str]) -> str | None:
    for kw in keywords:
        pattern = r"(?<![A-Za-z0-9_])" + re.escape(kw) + r"(?![A-Za-z0-9_])"
        if re.search(pattern, text, re.IGNORECASE):
            return kw
    return None


def _pick(tiers: dict[str, list[dict]], tier: str) -> tuple[str, dict]:
    i = _TIERS.index(tier)
    for t in [*_TIERS[i:], *reversed(_TIERS[:i])]:
        if tiers.get(t):
            return t, tiers[t][0]
    raise ValueError("router config has no candidate models")


def route(
    messages_or_text: Any,
    *,
    needs_tools: bool = False,
    config: dict | None = None,
) -> RouteDecision:
    """Pick the tier and model for a prompt (str, message dicts, or LangChain messages)."""
    cfg = config or _default_config()
    rules = cfg["rules"]
    text = _measure_text(messages_or_text)
    keyword = _keyword_hit(text, rules["advancedKeywords"])
    if keyword is not None:
        tier, reason = "advanced", f"keyword {keyword!r}"
    elif len(text) <= rules["maxCharsForEconomy"] and not needs_tools:
        tier, reason = "economy", f"{len(text)} chars <= {rules['maxCharsForEconomy']}"
    else:
        tier, reason = rules["defaultTier"], "default tier"
    floor = rules["needsToolsMinTier"]
    if needs_tools and _TIERS.index(tier) < _TIERS.index(floor):
        tier, reason = floor, f"{reason}; tools need >= {floor}"
    picked, candidate = _pick(cfg["tiers"], tier)
    if picked != tier:
        reason = f"{reason}; {tier} empty, fell back to {picked}"
    return RouteDecision(candidate["modelId"], candidate["providerId"], picked, reason)


def _init_model(model: str, provider: str, **kw: Any) -> Any:
    """Create the LangChain chat model (separate so tests can replace it)."""
    from langchain.chat_models import init_chat_model

    return init_chat_model(model, model_provider=_LC_PROVIDERS.get(provider, provider), **kw)


def get_model(messages_or_text: Any, **kw: Any) -> Any:
    """Return a LangChain chat model for the routed decision.

    Calls ``langchain.chat_models.init_chat_model(decision.model,
    model_provider=decision.provider, ...)``. ``needs_tools`` and ``config`` are consumed by
    ``route``; other keyword arguments go to ``init_chat_model``. Requires LangChain (lazy import).
    """
    decision = route(
        messages_or_text, needs_tools=kw.pop("needs_tools", False), config=kw.pop("config", None)
    )
    logger.info("route: %s %s/%s (%s)", decision.tier, decision.provider, decision.model,
                decision.reason)
    return _init_model(decision.model, decision.provider, **kw)
