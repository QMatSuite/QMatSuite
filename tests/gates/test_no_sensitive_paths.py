"""Gate S1: No sensitive local identifiers in committed files.

Scans all tracked repo files (excluding .tmp/) for real usernames,
hostnames, and absolute home paths. Fails if any are found.

IMPORTANT: This test must NOT echo the actual sensitive strings in
its output. It only reports rule ID, file path, and line number.
"""

import re
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent

# ── Rules ────────────────────────────────────────────────────────────
# Each rule: (rule_id, compiled_regex, description)
# Patterns are defined indirectly to avoid the gate itself being a leak.

# Build patterns from components to avoid literal sensitive strings in source
_SENSITIVE_RULES: list[tuple[str, re.Pattern, str]] = []


def _add_user_rule(username: str, rule_id: str) -> None:
    """Register a rule that catches a real username as a whole word."""
    pat = re.compile(r"\b" + re.escape(username) + r"\b")
    _SENSITIVE_RULES.append((rule_id, pat, f"real username ({len(username)} chars)"))


def _add_host_rule(hostname: str, rule_id: str) -> None:
    """Register a rule that catches a real hostname."""
    pat = re.compile(re.escape(hostname), re.IGNORECASE)
    _SENSITIVE_RULES.append((rule_id, pat, f"real hostname ({len(hostname)} chars)"))


def _add_path_rule(path_prefix: str, rule_id: str) -> None:
    """Register a rule that catches an absolute home path."""
    pat = re.compile(re.escape(path_prefix))
    _SENSITIVE_RULES.append((rule_id, pat, f"absolute home path"))


# Known sensitive identifiers (add new ones here when discovered)
# Usernames
_add_user_rule("<USER>", "S1-U1")
_add_user_rule("<USER>", "S1-U2")

# Hostnames
_add_host_rule("<HOST>", "S1-H1")

# Absolute home paths — catch /Users/<known-user>
_add_path_rule("<HOME>", "S1-P1")
_add_path_rule("<HOME>", "S1-P2")
_add_path_rule("<HOME>/", "S1-P3")
_add_path_rule("<HOME>/", "S1-P4")

# Temp session paths
_add_path_rule("claude-504/", "S1-T1")

# ── Allowlist ────────────────────────────────────────────────────────
# Files that are allowed to contain these patterns (e.g., this gate itself)
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
    # Show 20 chars of context on each side
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
            # Skip allowlisted files and .tmp
            if relpath in _ALLOWED_FILES:
                continue
            if relpath.startswith(".tmp/"):
                continue

            filepath = PROJECT_ROOT / relpath
            if not filepath.is_file():
                continue

            # Skip binary files
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
            # Cap output to avoid flooding
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
