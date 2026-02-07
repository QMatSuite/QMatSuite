"""Gate S1: No sensitive local identifiers in committed files.

Scans all tracked repo files (excluding .tmp/) for real usernames,
hostnames, and absolute home paths. Fails if any are found.

IMPORTANT: This test must NOT echo the actual sensitive strings in
its output. It only reports rule ID, file path, and line number.

Known identifiers are stored hex-encoded so they survive git-filter-repo
rewrites without being replaced by placeholders.
"""

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent

# ── Rules ────────────────────────────────────────────────────────────
# Each rule: (rule_id, compiled_regex, description)
_SENSITIVE_RULES: list[tuple[str, re.Pattern, str]] = []


def _from_hex(hex_str: str) -> str:
    """Decode a hex-encoded string."""
    return bytes.fromhex(hex_str).decode("utf-8")


def _add_word_rule(hex_encoded: str, rule_id: str, desc: str) -> None:
    """Register a rule from a hex-encoded string, matched as whole word."""
    word = _from_hex(hex_encoded)
    pat = re.compile(r"\b" + re.escape(word) + r"\b")
    _SENSITIVE_RULES.append((rule_id, pat, desc))


def _add_literal_rule(hex_encoded: str, rule_id: str, desc: str) -> None:
    """Register a rule from a hex-encoded string, matched literally (case-insensitive)."""
    literal = _from_hex(hex_encoded)
    pat = re.compile(re.escape(literal), re.IGNORECASE)
    _SENSITIVE_RULES.append((rule_id, pat, desc))


# ── Known sensitive identifiers (hex-encoded) ───────────────────────
# To add a new identifier: python3 -c "print('mystring'.encode().hex())"
#
# Usernames
_add_word_rule("686837343635", "S1-U1", "known username")            # hh7465
_add_word_rule("6b6672616e6b65", "S1-U2", "known username")         # kfranke

# Hostnames
_add_literal_rule(                                                    # PHY-K3302477DD
    "5048592d4b333330323437374444", "S1-H1", "known hostname"
)

# ── Generic pattern rules (catch future leaks too) ──────────────────
# /Users/<name> paths — exclude placeholders and generic example names
_GENERIC_ALLOWED_NAMES = r"(?:user|example|testuser|username|nobody|root)"
_SENSITIVE_RULES.append((
    "S1-P1",
    re.compile(
        r"/Users/(?!<)(?!" + _GENERIC_ALLOWED_NAMES + r"(?:/|$))"
        r"[a-zA-Z][a-zA-Z0-9_.-]+"
    ),
    "absolute macOS home path",
))
_SENSITIVE_RULES.append((
    "S1-P3",
    re.compile(
        r"C:\\Users\\(?!<)(?!" + _GENERIC_ALLOWED_NAMES + r"(?:\\|$))"
        r"[a-zA-Z][a-zA-Z0-9_.-]+"
    ),
    "absolute Windows home path",
))

# Claude session temp paths
_SENSITIVE_RULES.append((
    "S1-T1",
    re.compile(r"claude-\d+/"),
    "Claude session temp path",
))

# ── Allowlist ────────────────────────────────────────────────────────
_ALLOWED_FILES = {
    "tests/gates/test_no_sensitive_paths.py",  # this file defines the rules
}

# ── Helpers ──────────────────────────────────────────────────────────


def _get_tracked_files() -> list[str]:
    """Return list of git-tracked file paths relative to PROJECT_ROOT."""
    result = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def _mask_match(line: str, match: re.Match) -> str:
    """Return a masked snippet showing only the first/last char of the match."""
    s, e = match.start(), match.end()
    matched = line[s:e]
    if len(matched) <= 2:
        masked = "**"
    else:
        masked = matched[0] + "*" * (len(matched) - 2) + matched[-1]
    ctx_start = max(0, s - 20)
    ctx_end = min(len(line), e + 20)
    prefix = line[ctx_start:s]
    suffix = line[e:ctx_end]
    return f"...{prefix}[{masked}]{suffix}..."


# ── Test ─────────────────────────────────────────────────────────────


class TestNoSensitivePaths:
    """Scan all tracked files for leaked local identifiers."""

    def test_no_sensitive_identifiers(self):
        """No tracked file (outside allowlist) may contain sensitive strings."""
        violations = []

        tracked = _get_tracked_files()
        for relpath in tracked:
            if relpath in _ALLOWED_FILES:
                continue
            if relpath.startswith(".tmp/"):
                continue

            filepath = PROJECT_ROOT / relpath
            if not filepath.is_file():
                continue

            try:
                lines = filepath.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, PermissionError):
                continue

            for lineno, line in enumerate(lines, 1):
                for rule_id, pattern, desc in _SENSITIVE_RULES:
                    m = pattern.search(line)
                    if m:
                        snippet = _mask_match(line, m)
                        violations.append(
                            f"  [{rule_id}] {relpath}:{lineno}  {snippet}"
                        )
                        break  # one violation per line is enough

        if violations:
            shown = violations[:50]
            extra = len(violations) - len(shown)
            msg = (
                f"Found {len(violations)} sensitive-identifier violation(s) "
                f"in tracked files (Law S1):\n"
                + "\n".join(shown)
            )
            if extra > 0:
                msg += f"\n  ... and {extra} more"
            pytest.fail(msg)
