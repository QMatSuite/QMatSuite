"""
Static gate: GUI RPC methods must exist in daemon handler registry.

This is a pure code-scanning test - no runtime, no manifest, no fixtures.
It ensures GUI-called RPC methods are wired to daemon handlers.

Scan approach:
1. Extract method names from GUI's QMSCommandMap interface (TypeScript)
2. Extract method names from daemon's _HANDLER_MAP (Python)
3. Fail if any GUI method is not in daemon (GUI calls would fail at runtime)

Extra daemon methods are OK (GUI doesn't need to use all methods).
"""

import re
from pathlib import Path

import pytest


# GUI source file with QMSCommandMap interface
GUI_TYPES_FILE = Path(__file__).parent.parent.parent / "gui" / "src" / "types" / "qms.ts"

# Daemon server file with handler registry
DAEMON_SERVER_FILE = Path(__file__).parent.parent.parent / "src" / "qmatsuite" / "daemon" / "server.py"

# Methods exempt from the wiring check with reasons
# Use sparingly - only for methods that are intentionally not wired
EXEMPT_METHODS = {
    # Example: "some_deprecated_method": "Removed in v2, GUI fallback handles it"
}


def extract_gui_rpc_methods() -> set[str]:
    """Extract RPC method names from GUI's QMSCommandMap TypeScript interface."""
    if not GUI_TYPES_FILE.exists():
        pytest.skip(f"GUI types file not found: {GUI_TYPES_FILE}")

    content = GUI_TYPES_FILE.read_text()

    # Find QMSCommandMap interface block
    # Pattern: interface QMSCommandMap { ... }
    interface_match = re.search(
        r'export interface QMSCommandMap\s*\{(.*?)^\}',
        content,
        re.DOTALL | re.MULTILINE
    )
    if not interface_match:
        pytest.fail("Could not find QMSCommandMap interface in GUI types file")

    interface_body = interface_match.group(1)

    # Extract method names (lines like "  method_name: {")
    methods = set()
    for line in interface_body.split('\n'):
        # Match "  method_name: {" at start of line (2-space indent)
        match = re.match(r'^  ([a-z_]+):\s*\{', line)
        if match:
            methods.add(match.group(1))

    return methods


def extract_daemon_rpc_methods() -> set[str]:
    """Extract RPC method names from daemon's handler registry."""
    if not DAEMON_SERVER_FILE.exists():
        pytest.fail(f"Daemon server file not found: {DAEMON_SERVER_FILE}")

    content = DAEMON_SERVER_FILE.read_text()

    # Extract method names from handler dictionary
    # Pattern: "method_name": self._handle_...
    methods = set()
    for match in re.finditer(r'"([a-z_]+)":\s*self\._handle', content):
        methods.add(match.group(1))

    return methods


class TestGUIRPCWiring:
    """Static gate tests for GUI-to-daemon RPC wiring."""

    def test_all_gui_methods_have_daemon_handlers(self):
        """Every RPC method called by GUI must have a daemon handler."""
        gui_methods = extract_gui_rpc_methods()
        daemon_methods = extract_daemon_rpc_methods()

        # Remove exempt methods from check
        gui_methods_to_check = gui_methods - set(EXEMPT_METHODS.keys())

        # Find methods in GUI but not in daemon
        missing_in_daemon = gui_methods_to_check - daemon_methods

        if missing_in_daemon:
            pytest.fail(
                f"GUI calls {len(missing_in_daemon)} RPC methods not wired in daemon:\n"
                f"  {sorted(missing_in_daemon)}\n\n"
                f"Either:\n"
                f"  1. Add handler in daemon/server.py, or\n"
                f"  2. Add to EXEMPT_METHODS with reason (if intentionally unwired)"
            )

    def test_exempt_methods_documented(self):
        """All exempt methods must have documented reasons."""
        for method, reason in EXEMPT_METHODS.items():
            assert reason.strip(), f"EXEMPT_METHODS['{method}'] has no reason"
            assert len(reason) >= 10, f"EXEMPT_METHODS['{method}'] reason too short"

    def test_exempt_cap(self):
        """Exempt list should stay small (cap at 5)."""
        max_exempt = 5
        assert len(EXEMPT_METHODS) <= max_exempt, (
            f"EXEMPT_METHODS has {len(EXEMPT_METHODS)} entries (max {max_exempt}).\n"
            f"Fix the wiring instead of adding more exemptions."
        )

    def test_gui_types_file_exists(self):
        """GUI types file must exist for this gate to work."""
        assert GUI_TYPES_FILE.exists(), f"GUI types file not found: {GUI_TYPES_FILE}"

    def test_daemon_server_file_exists(self):
        """Daemon server file must exist for this gate to work."""
        assert DAEMON_SERVER_FILE.exists(), f"Daemon server file not found: {DAEMON_SERVER_FILE}"

    def test_extraction_sanity(self):
        """Sanity check: extractions should find reasonable method counts."""
        gui_methods = extract_gui_rpc_methods()
        daemon_methods = extract_daemon_rpc_methods()

        # GUI should have at least 50 methods (sanity check)
        assert len(gui_methods) >= 50, f"GUI has only {len(gui_methods)} methods (expected 50+)"

        # Daemon should have at least 50 methods (sanity check)
        assert len(daemon_methods) >= 50, f"Daemon has only {len(daemon_methods)} methods (expected 50+)"

        # Daemon should have at least as many as GUI calls
        assert len(daemon_methods) >= len(gui_methods) - len(EXEMPT_METHODS), (
            f"Daemon has fewer methods ({len(daemon_methods)}) than GUI calls ({len(gui_methods)})"
        )
