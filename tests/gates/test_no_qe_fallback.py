"""
Gate: Law EF4 — No Silent QE Fallbacks.

No code outside drivers/qe/ may default engine_family to "qe".
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SCAN_DIRS = [REPO_ROOT / "src" / "quantumvitas"]

# Patterns that indicate a silent QE default
FALLBACK_PATTERNS = [
    (r'or\s+"qe"', 'or "qe"'),
    (r"or\s+'qe'", "or 'qe'"),
    (r'else\s+"qe"', 'else "qe"'),
    (r"else\s+'qe'", "else 'qe'"),
    (r'engine_family:\s*str\s*=\s*"qe"', 'engine_family default "qe"'),
    (r"engine_family:\s*str\s*=\s*'qe'", "engine_family default 'qe'"),
    (r'=\s*"qe"\s*#.*[Dd]efault', '= "qe" # default'),
]

SKIP_DIRS = {"drivers", "_vault", "__pycache__", ".venv"}


def _should_scan(path: Path) -> bool:
    parts = path.parts
    return not any(skip in parts for skip in SKIP_DIRS)


def test_no_silent_qe_fallbacks():
    """No silent QE defaults outside drivers/."""
    violations = []

    for scan_dir in SCAN_DIRS:
        for py_file in scan_dir.rglob("*.py"):
            if not _should_scan(py_file):
                continue
            try:
                text = py_file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            for lineno, line in enumerate(text.splitlines(), 1):
                # Skip comments
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue

                for pattern, description in FALLBACK_PATTERNS:
                    if re.search(pattern, line):
                        rel = py_file.relative_to(REPO_ROOT)
                        violations.append(f"  {rel}:{lineno}  {description}: {line.strip()}")

    assert not violations, (
        f"EF4 violation — silent QE fallbacks found ({len(violations)}):\n"
        + "\n".join(violations[:50])
    )



