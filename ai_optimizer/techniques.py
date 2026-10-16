"""Prompt-optimization techniques (stdlib only), byte-identical to the TS core implementation.

Key exports: ``optimize_text``, ``optimize_messages``, ``optimize_request``, ``load_techniques``.
Rule techniques (whitespace-normalize, filler-removal, dedupe-sentences, cache-prefix-ordering,
caveman-output, max-output-cap) are pure functions; ``llm`` techniques are not run here.
Parity is enforced by the golden fixtures in packages/fixtures/optimizer.
Feature: prompt optimizer (Python runtime).

``catalog_techniques.json`` (written next to this module by the exporter) has the shape::

    {"selected": ["<technique id>", ...],
     "techniques": [{"id": str, "mode": "rule", "ruleId": str, "order": int,
                     "affects": "input" | "output" | "both", "params": {...}}, ...]}

Messages may be dicts ``{"role", "content"}``, ``(role, content)`` tuples or LangChain
``BaseMessage`` objects; each keeps its type. "Trim" and "whitespace" use the JavaScript
``String.prototype.trim`` / ``\\s`` character set so both runtimes agree on non-ASCII input.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

Message = Any  # str | dict {"role", "content"} | langchain_core.messages.BaseMessage

_DEFAULT_TECHNIQUES_PATH = Path(__file__).with_name("catalog_techniques.json")

# JavaScript's whitespace set (``\s`` and ``trim``), used instead of Python's ``str.isspace``.
_JS_WS = (
    "\t\n\v\f\r             "
    "     　﻿"
)
_WS_CLASS = "[" + re.escape(_JS_WS) + "]"
_RULE_LINE = re.compile(r"-{3,}|\*{3,}|_{3,}")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])" + _WS_CLASS + "+")
_WS_RUN = re.compile(_WS_CLASS + "+")
_TRAILING_END = re.compile(r"[.!?]+$")
_LLM_TECHNIQUES = {"llm-compress"}

# LangChain message ``type`` -> chat role.
_LC_ROLES = {"human": "user", "ai": "assistant"}


def load_techniques(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load the exported technique catalog (``selected`` ids + per-technique params)."""
    with open(path or _DEFAULT_TECHNIQUES_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _default_catalog() -> dict[str, dict[str, Any]]:
    return {t["id"]: t for t in load_techniques()["techniques"]}


def _trim(s: str) -> str:
    return s.strip(_JS_WS)


# ─── message accessors (type-preserving) ────────────────────────────────────


def _role(msg: Message) -> str:
    if isinstance(msg, dict):
        role = msg.get("role", "")
    elif isinstance(msg, tuple):
        role = msg[0]
    else:
        role = getattr(msg, "type", "")
    return _LC_ROLES.get(role, role)


def _content(msg: Message) -> Any:
    if isinstance(msg, dict):
        return msg.get("content")
    if isinstance(msg, tuple):
        return msg[1]
    return getattr(msg, "content", None)


def _with_content(msg: Message, content: Any) -> Message:
    if isinstance(msg, dict):
        return {**msg, "content": content}
    if isinstance(msg, tuple):
        return (msg[0], content)
    return msg.model_copy(update={"content": content})


def _system_like(messages: list[Message], content: str) -> Message:
    """Build a system message of the same kind as ``messages`` (dict by default)."""
    for m in messages:
        if isinstance(m, tuple):
            return ("system", content)
        if not isinstance(m, dict):
            from langchain_core.messages import SystemMessage

            return SystemMessage(content=content)
    return {"role": "system", "content": content}


# ─── text rules ─────────────────────────────────────────────────────────────


def _whitespace_normalize(text: str, params: dict) -> str:
    out: list[str] = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if _RULE_LINE.fullmatch(line.strip(" \t")):
            continue
        body = line.lstrip(" \t")
        line = (line[: len(line) - len(body)] + re.sub(r"[ \t]+", " ", body)).rstrip(" \t")
        if line == "" and out and out[-1] == "":
            continue
        out.append(line)
    return "\n".join(out).strip(" \t\n")


def _filler_patterns(params: dict) -> list[re.Pattern[str]]:
    phrases = sorted(params.get("phrases", []), key=len, reverse=True)  # stable for ties
    return [
        re.compile(r"(?<![A-Za-z0-9])" + re.escape(p) + r"(?![A-Za-z0-9])", re.IGNORECASE)
        for p in phrases
        if p
    ]


def _filler_line(line: str, patterns: list[re.Pattern[str]]) -> str:
    original, removed = line, 0
    for pat in patterns:
        line, n = pat.subn("", line)
        removed += n
    if not removed:
        return original
    line = re.sub(r"[ \t]+", " ", line)
    line = re.sub(r" +(?=[,.;:!?])", "", line)
    if line.startswith(", "):
        line = line[2:]
    elif line.startswith(","):
        line = line[1:]
    line = _trim(line)
    if _trim(original)[:1].isupper() and line[:1].islower():
        line = line[0].upper() + line[1:]
    return line


def _filler_removal(text: str, params: dict) -> str:
    patterns = _filler_patterns(params)
    return "\n".join(_filler_line(line, patterns) for line in text.split("\n"))


def _sentence_key(sentence: str) -> str:
    return _trim(_TRAILING_END.sub("", _WS_RUN.sub(" ", sentence.lower())))


def _dedupe(text: str, seen: set[str]) -> str:
    out: list[str] = []
    for line in text.split("\n"):
        if line == "":
            out.append(line)
            continue
        kept: list[str] = []
        for sentence in _SENTENCE_SPLIT.split(line):
            key = _sentence_key(sentence)
            if key and key in seen:
                continue
            seen.add(key)
            kept.append(sentence)
        if kept:
            out.append(" ".join(kept))
    return "\n".join(out)


# ─── technique dispatch ─────────────────────────────────────────────────────

# A rule maps (messages, params, rule params) -> (messages, params); optimize_text runs a text
# as one user message so text and request share the same code.
_Rule = Callable[[list[Message], dict, dict], tuple[list[Message], dict]]


def _per_content(fn: Callable[[str, dict], str], roles: set[str] | None) -> _Rule:
    def rule(messages: list[Message], params: dict, rp: dict) -> tuple[list[Message], dict]:
        out = []
        for m in messages:
            c = _content(m)
            if isinstance(c, str) and (roles is None or _role(m) in roles):
                m = _with_content(m, fn(c, rp))
            out.append(m)
        return out, params

    return rule


def _dedupe_rule(messages: list[Message], params: dict, rp: dict) -> tuple[list[Message], dict]:
    seen: set[str] = set()
    out = []
    for m in messages:
        c = _content(m)
        out.append(_with_content(m, _dedupe(c, seen)) if isinstance(c, str) else m)
    return out, params


def _cache_prefix(messages: list[Message], params: dict, rp: dict) -> tuple[list[Message], dict]:
    system = [m for m in messages if _role(m) == "system"]
    return system + [m for m in messages if _role(m) != "system"], params


def _caveman(messages: list[Message], params: dict, rp: dict) -> tuple[list[Message], dict]:
    instruction = rp.get("instruction", "")
    for i, m in enumerate(messages):
        if _role(m) != "system":
            continue
        c = _content(m)
        if isinstance(c, str):
            c = c + "\n\n" + instruction
        else:  # LangChain content blocks
            c = [*(c or []), {"type": "text", "text": instruction}]
        return [*messages[:i], _with_content(m, c), *messages[i + 1 :]], params
    return [_system_like(messages, instruction), *messages], params


def _max_output_cap(messages: list[Message], params: dict, rp: dict) -> tuple[list[Message], dict]:
    cap = rp.get("maxTokens")
    if cap is None:
        return messages, params
    existing = params.get("max_tokens")
    return messages, {**params, "max_tokens": cap if existing is None else min(existing, cap)}


_RULES: dict[str, _Rule] = {
    "whitespace-normalize": _per_content(_whitespace_normalize, None),
    "filler-removal": _per_content(_filler_removal, {"system", "user"}),
    "dedupe-sentences": _dedupe_rule,
    "cache-prefix-ordering": _cache_prefix,
    "caveman-output": _caveman,
    "max-output-cap": _max_output_cap,
}
_MESSAGE_ONLY = {"cache-prefix-ordering", "max-output-cap"}


def _resolve(technique: str, config: dict | None) -> tuple[str | None, dict]:
    """Return ``(rule id, params)``; a rule id of None means skip (an ``llm`` technique)."""
    entry = _default_catalog().get(technique, {})
    if entry.get("mode") == "llm" or (not entry and technique in _LLM_TECHNIQUES):
        return None, {}
    rule_id = entry.get("ruleId", technique)
    if rule_id not in _RULES:
        raise ValueError(f"unknown technique {technique!r}")
    return rule_id, {**entry.get("params", {}), **((config or {}).get(technique) or {})}


def _selected() -> list[str]:
    return list(load_techniques()["selected"])


def optimize_text(text: str, techniques: list[str], config: dict | None = None) -> str:
    """Apply ``techniques`` in list order to a plain-text prompt and return the new text.

    ``config`` maps technique id -> param overrides, e.g.
    ``{"caveman-output": {"instruction": "Be terse."}}``; missing params come from
    ``catalog_techniques.json``. Message-only techniques (cache-prefix-ordering,
    max-output-cap) are no-ops for text.
    """
    for technique in techniques:
        rule_id, rp = _resolve(technique, config)
        if rule_id is None or rule_id in _MESSAGE_ONLY:
            continue
        if rule_id == "caveman-output":
            text = text + "\n\n" + rp.get("instruction", "")
            continue
        messages, _ = _RULES[rule_id]([{"role": "user", "content": text}], {}, rp)
        text = messages[0]["content"]
    return text


def optimize_request(
    messages: list[Message],
    params: dict | None = None,
    techniques: list[str] | None = None,
    config: dict | None = None,
) -> tuple[list[Message], dict]:
    """Apply techniques to a chat request; return ``(messages, params)``.

    ``params`` holds request parameters such as ``max_tokens`` (set by max-output-cap).
    ``techniques=None`` uses the exported ``selected`` list. Messages keep their input type
    (dict stays dict, LangChain messages stay LangChain messages). Golden-fixture entry point
    for ``kind: "messages"`` cases.
    """
    out, out_params = list(messages), dict(params or {})
    for technique in _selected() if techniques is None else techniques:
        rule_id, rp = _resolve(technique, config)
        if rule_id is not None:
            out, out_params = _RULES[rule_id](out, out_params, rp)
    return out, out_params


def optimize_messages(
    messages: str | list[Message],
    techniques: list[str] | None = None,
    config: dict | None = None,
) -> str | list[Message]:
    """Optimize the input of ``llm.invoke(...)`` (the Implement flow's ``invoke-wrap``).

    A ``str`` input is treated like ``optimize_text``; a message list goes through
    ``optimize_request`` and only the messages are returned.
    """
    if isinstance(messages, str):
        return optimize_text(messages, _selected() if techniques is None else techniques, config)
    return optimize_request(messages, None, techniques, config)[0]
