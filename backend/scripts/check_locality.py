#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data-Locality Enforcement Scanner (T092 — Phase 11).

Static analysis gate that fails CI if any Python or TypeScript/JavaScript
source file references a prohibited public LLM/embedding/storage API host,
a cloud API key environment variable, or a cloud-SDK import.

This script makes ZERO network calls — it is a pure grep-based static
analysis tool.  Run it as a pre-commit hook or CI step.

Usage
-----
    python backend/scripts/check_locality.py [--root <project-root>]

Exit codes
----------
    0 — no violations found (clean)
    1 — one or more violations found (details printed to stdout)

Prohibited patterns
-------------------
URLs (substring match, case-insensitive):
    api.openai.com
    api.anthropic.com
    api.cohere.com
    generativelanguage.googleapis.com
    api.mistral.ai
    api.together.xyz
    s3.amazonaws.com
    storage.googleapis.com

Environment variable names (exact token match):
    OPENAI_API_KEY
    ANTHROPIC_API_KEY
    COHERE_API_KEY
    GOOGLE_API_KEY

Python import patterns (checked in .py files only):
    from openai import
    import openai
    from anthropic import
    import anthropic

Scope
-----
- Python (.py):  full URL + env-var + import checks
- TypeScript/JavaScript (.ts, .tsx, .js, .jsx):  URL + env-var checks only
- Ignored paths:  .venv/, venv/, node_modules/, __pycache__/, .git/,
                  dist/, build/, *.egg-info/
                  This script itself (check_locality.py) is excluded from
                  the import-pattern scan to avoid false positives from the
                  pattern strings defined here.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

# ---------------------------------------------------------------------------
# Prohibited patterns
# ---------------------------------------------------------------------------

# URL substrings — matched case-insensitively anywhere in the line.
# Covers both string literals and template strings.
_PROHIBITED_URLS: list[str] = [
    "api.openai.com",
    "api.anthropic.com",
    "api.cohere.com",
    "generativelanguage.googleapis.com",
    "api.mistral.ai",
    "api.together.xyz",
    "s3.amazonaws.com",
    "storage.googleapis.com",
]

# Environment variable names — matched as exact tokens (word boundaries).
_PROHIBITED_ENV_VARS: list[str] = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "COHERE_API_KEY",
    "GOOGLE_API_KEY",
]

# Python-specific import patterns (regex).
_PROHIBITED_IMPORTS: list[str] = [
    r"^\s*from\s+openai\s+import",
    r"^\s*import\s+openai\b",
    r"^\s*from\s+anthropic\s+import",
    r"^\s*import\s+anthropic\b",
]

# Directory names to skip entirely (fast path — no file I/O for these trees).
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".git",
        "dist",
        "build",
        ".eggs",
    }
)

# Suffix → check functions to apply
_PYTHON_EXTENSIONS: frozenset[str] = frozenset({".py"})
_JS_TS_EXTENSIONS: frozenset[str] = frozenset({".ts", ".tsx", ".js", ".jsx"})

# The name of this script — excluded entirely (the pattern *strings* defined
# here would trivially match themselves and produce meaningless false positives).
_THIS_SCRIPT_NAME = Path(__file__).name

# Inline suppression comment — add this to a line to skip all locality checks
# for that line (analogous to # noqa for linters):
#   os.environ.get("OPENAI_API_KEY", "")  # noqa: locality
_NOQA_MARKER = "noqa: locality"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Violation:
    path: str
    line_number: int
    line_content: str
    pattern: str
    category: str


@dataclass
class ScanResult:
    violations: list[Violation] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def clean(self) -> bool:
        return len(self.violations) == 0


# ---------------------------------------------------------------------------
# Compiled patterns (built once at module level)
# ---------------------------------------------------------------------------

_URL_PATTERNS: list[re.Pattern] = [
    re.compile(re.escape(url), re.IGNORECASE) for url in _PROHIBITED_URLS
]

_ENV_VAR_PATTERNS: list[tuple[str, re.Pattern]] = [
    (var, re.compile(r"\b" + re.escape(var) + r"\b")) for var in _PROHIBITED_ENV_VARS
]

_IMPORT_PATTERNS: list[tuple[str, re.Pattern]] = [
    (pat, re.compile(pat, re.MULTILINE)) for pat in _PROHIBITED_IMPORTS
]


# ---------------------------------------------------------------------------
# File scanner
# ---------------------------------------------------------------------------

def _check_file(path: Path, result: ScanResult) -> None:
    """
    Scan a single file for prohibited patterns.

    Parameters
    ----------
    path:
        Absolute path to the file.
    result:
        Accumulator -- violations and file counts are appended here.
    """
    suffix = path.suffix.lower()
    # Skip this script entirely — the pattern strings it defines would trivially
    # match themselves and produce meaningless false positives.
    if path.name == _THIS_SCRIPT_NAME:
        result.files_scanned += 1
        return

    check_imports = suffix in _PYTHON_EXTENSIONS
    check_urls = suffix in _PYTHON_EXTENSIONS or suffix in _JS_TS_EXTENSIONS
    check_envvars = check_urls  # same scope as URLs

    if not (check_urls or check_imports):
        return

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return  # unreadable — skip silently

    result.files_scanned += 1
    path_str = str(path)

    lines = text.splitlines()

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Skip blank lines
        if not stripped:
            continue

        # Skip pure comment lines (Python: #, JavaScript/TypeScript: //)
        # These are documentation, not executable references.
        if stripped.startswith("#") or stripped.startswith("//"):
            continue

        # Inline suppression: # noqa: locality
        if _NOQA_MARKER in line:
            continue

        # URL checks
        if check_urls:
            for pattern in _URL_PATTERNS:
                if pattern.search(line):
                    result.violations.append(
                        Violation(
                            path=path_str,
                            line_number=lineno,
                            line_content=line.rstrip(),
                            pattern=pattern.pattern,
                            category="prohibited_url",
                        )
                    )

        # Env-var checks
        if check_envvars:
            for var_name, pattern in _ENV_VAR_PATTERNS:
                if pattern.search(line):
                    result.violations.append(
                        Violation(
                            path=path_str,
                            line_number=lineno,
                            line_content=line.rstrip(),
                            pattern=var_name,
                            category="prohibited_env_var",
                        )
                    )

        # Import checks (Python only)
        if check_imports:
            for pat_str, pattern in _IMPORT_PATTERNS:
                if pattern.match(line):
                    result.violations.append(
                        Violation(
                            path=path_str,
                            line_number=lineno,
                            line_content=line.rstrip(),
                            pattern=pat_str,
                            category="prohibited_import",
                        )
                    )


# ---------------------------------------------------------------------------
# Directory walker
# ---------------------------------------------------------------------------

def scan_directory(root: Path) -> ScanResult:
    """
    Recursively scan *root* for data-locality violations.

    Returns a ``ScanResult`` with all violations found.
    """
    result = ScanResult()

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place so os.walk doesn't descend into them.
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]

        for filename in filenames:
            filepath = Path(dirpath) / filename
            suffix = filepath.suffix.lower()

            if suffix not in _PYTHON_EXTENSIONS and suffix not in _JS_TS_EXTENSIONS:
                continue

            _check_file(filepath, result)

    return result


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def _report(result: ScanResult, root: Path) -> None:
    """Print scan results in a human-readable format (ASCII-safe for Windows consoles)."""
    out = sys.stdout
    out.write(f"Data-Locality Enforcement Scan -- root: {root}\n")
    out.write(f"Files scanned: {result.files_scanned}\n")

    if result.clean:
        out.write("[PASS] No prohibited external API references found.\n")
        return

    out.write(f"[FAIL] {len(result.violations)} violation(s) found:\n\n")

    # Group by file for readability
    by_file: dict[str, list[Violation]] = {}
    for v in result.violations:
        by_file.setdefault(v.path, []).append(v)

    for filepath, violations in sorted(by_file.items()):
        # Show path relative to root when possible
        try:
            display_path = str(Path(filepath).relative_to(root))
        except ValueError:
            display_path = filepath

        out.write(f"  {display_path}\n")
        for v in violations:
            out.write(f"    L{v.line_number} [{v.category}] pattern={v.pattern!r}\n")
            out.write(f"      {v.line_content}\n")
        out.write("\n")

    out.write(
        "Fix: Remove all references to public LLM/embedding/storage APIs.\n"
        "All inference must use local Ollama (http://localhost:11434) and\n"
        "local TEI (configured via TEI_URL env var). All storage must use\n"
        "local MinIO (configured via MINIO_ENDPOINT env var).\n"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Static analysis gate: fail if any source file references a public LLM/embedding/storage API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help=(
            "Project root directory to scan. "
            "Defaults to the repository root (two levels above this script)."
        ),
    )
    args = parser.parse_args(argv)

    if args.root is not None:
        root = args.root.resolve()
    else:
        # Default: two levels up from backend/scripts/ → project root
        root = Path(__file__).resolve().parent.parent.parent

    if not root.is_dir():
        print(f"ERROR: root directory does not exist: {root}", file=sys.stderr)
        return 2

    result = scan_directory(root)
    _report(result, root)

    return 0 if result.clean else 1


if __name__ == "__main__":
    sys.exit(main())
