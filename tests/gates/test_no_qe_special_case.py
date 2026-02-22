"""
Gate: M8 — No QE-Only RPC Handlers.

After M8, the daemon dispatch dict must NOT contain QE-specific RPC
registrations that have generic replacements. Engine-detection RPCs
(detect_qe, list_qe_engines, set_qe_engine) are ALLOWED until a generic
detect_engine RPC is implemented (spec §5.5).

GUI TypeScript must NOT contain old QE-specific convenience methods
or component names.
"""

import ast
import re
from io import StringIO
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent


# ── Daemon dispatch dict ──────────────────────────────────────────

# QE RPCs that MUST be gone (replaced by generic equivalents)
FORBIDDEN_DAEMON_RPCS = {
    "list_qe_ui_parameters",
    "list_qe_parameter_metadata",
    "reload_qe_parameter_metadata",
    "get_qe_parameter_metadata_debug_info",
    "discover_qe_engines",
    "import_step_from_qe_input",
}

# QE RPCs that are ALLOWED (engine detection, no generic replacement yet)
ALLOWED_DAEMON_RPCS = {
    "detect_qe",
    "list_qe_engines",
    "set_qe_engine",
}


def test_daemon_dispatch_no_forbidden_qe_rpcs():
    """Daemon dispatch dict must not register forbidden QE RPCs."""
    from qmatsuite.daemon.server import QMSDaemon

    daemon = QMSDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    registered = set(daemon._handlers.keys())

    violations = registered & FORBIDDEN_DAEMON_RPCS
    assert not violations, (
        f"Forbidden QE-specific RPCs still in daemon dispatch: {sorted(violations)}. "
        f"These were replaced by generic engine RPCs in M8."
    )


def test_daemon_dispatch_keeps_allowed_qe_rpcs():
    """Daemon dispatch dict must still have engine-detection RPCs."""
    from qmatsuite.daemon.server import QMSDaemon

    daemon = QMSDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    registered = set(daemon._handlers.keys())

    missing = ALLOWED_DAEMON_RPCS - registered
    assert not missing, (
        f"Allowed QE engine-detection RPCs missing from dispatch: {sorted(missing)}. "
        f"These are kept until generic detect_engine is implemented (spec §5.5)."
    )


# ── GUI TypeScript ────────────────────────────────────────────────

GUI_SRC = REPO_ROOT / "gui" / "src"

# Patterns forbidden in GUI TypeScript (old QE-specific names)
FORBIDDEN_GUI_PATTERNS = [
    (r"\blistQeUiParameters\b", "old QE convenience method"),
    (r"\bQEParameterBrowser\b", "old QE-specific component name"),
    (r"\buseQEParameterMetadata\b", "old QE-specific hook name"),
]

# Patterns explicitly ALLOWED in GUI TypeScript
ALLOWED_GUI_PATTERNS = {
    "QEDetectionResult",  # Used by SettingsPanel for detect_qe response
    "detect_qe",          # Engine detection RPC
    "list_qe_engines",    # Engine detection RPC
    "set_qe_engine",      # Engine detection RPC
}


@pytest.mark.skipif(
    not GUI_SRC.exists(),
    reason="GUI source not found",
)
def test_gui_no_forbidden_qe_patterns():
    """GUI TypeScript must not use old QE-specific names."""
    violations = []

    for ts_file in GUI_SRC.rglob("*.ts"):
        _check_gui_file(ts_file, violations)
    for tsx_file in GUI_SRC.rglob("*.tsx"):
        _check_gui_file(tsx_file, violations)

    assert not violations, (
        f"Found {len(violations)} forbidden QE pattern(s) in GUI:\n"
        + "\n".join(f"  {v}" for v in violations)
    )


def _check_gui_file(path: Path, violations: list):
    text = path.read_text(errors="replace")
    rel = path.relative_to(REPO_ROOT)

    for pattern, desc in FORBIDDEN_GUI_PATTERNS:
        for match in re.finditer(pattern, text):
            # Check if this match is in an allowed context
            matched_text = match.group(0)
            if matched_text in ALLOWED_GUI_PATTERNS:
                continue
            line_no = text[:match.start()].count("\n") + 1
            violations.append(f"{rel}:{line_no}: {desc} ({matched_text})")
