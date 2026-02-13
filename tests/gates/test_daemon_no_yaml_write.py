"""
Gate test: Daemon _handle_* methods must NOT contain direct YAML/model writes.

All YAML writes and model saves must go through QVService methods.
This prevents "second truth" where daemon handlers bypass the API layer.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest


def _get_handler_methods():
    """Get all _handle_* methods from QVDaemon."""
    from quantumvitas.daemon.server import QVDaemon

    methods = []
    for name, method in inspect.getmembers(QVDaemon, predicate=inspect.isfunction):
        if name.startswith("_handle_"):
            methods.append((name, method))
    return methods


# Forbidden call patterns in handler methods (function names that indicate direct model writes)
FORBIDDEN_CALLS = {
    "save_calculation",
    "save_yaml_doc",
}

# Methods that are allowed to use yaml.safe_load for payload parsing
# (not for reading model files)
ALLOWED_YAML_LOAD_METHODS = set()  # None allowed after Phase 0A


class TestDaemonNoYamlWrite:
    """Daemon _handle_* methods must not contain direct YAML writes."""

    @pytest.mark.parametrize("name,method", _get_handler_methods(), ids=lambda x: x if isinstance(x, str) else "")
    def test_no_save_calls(self, name, method):
        """No _handle_* method should call save_calculation or save_yaml_doc."""
        source = textwrap.dedent(inspect.getsource(method))
        tree = ast.parse(source)

        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Check direct calls: save_calculation(...)
                if isinstance(func, ast.Name) and func.id in FORBIDDEN_CALLS:
                    violations.append(f"{name} calls {func.id}() directly")
                # Check attribute calls: obj.save_calculation(...)
                elif isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_CALLS:
                    violations.append(f"{name} calls .{func.attr}() directly")

        assert not violations, (
            f"Daemon handler(s) bypass QVService with direct model saves:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
