"""Gate test: No legacy .history system.

This gate ensures the legacy .history system is fully removed and
cannot be reintroduced. All history/provenance functionality must
use the new provenance module (.provenance/ directory with SQLite + CAS).

Laws enforced:
- History == Provenance (single system only)
- No technical debt from parallel systems
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src" / "quantumvitas"


class TestNoLegacyHistoryImports:
    """Verify no code imports from quantumvitas.history module."""

    # Files that are allowed to reference .history (comments, docs, migration only)
    ALLOWED_EXCEPTIONS = frozenset({
        # The history module itself (will be deleted)
        "history/__init__.py",
        "history/storage.py",
        "history/events.py",
        "history/run_revision.py",
        "history/digests.py",
        "history/pins.py",
    })

    def _get_python_files(self) -> list[Path]:
        """Get all Python files in src/, excluding history module."""
        files = []
        for path in SRC_DIR.rglob("*.py"):
            rel = path.relative_to(SRC_DIR).as_posix()
            if rel not in self.ALLOWED_EXCEPTIONS:
                files.append(path)
        return files

    def test_no_history_module_imports(self):
        """No code should import from quantumvitas.history module."""
        violations = []

        for path in self._get_python_files():
            try:
                source = path.read_text()
                tree = ast.parse(source)
            except (SyntaxError, UnicodeDecodeError):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if "quantumvitas.history" in alias.name:
                            violations.append(
                                f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}: "
                                f"import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module and "quantumvitas.history" in node.module:
                        violations.append(
                            f"{path.relative_to(PROJECT_ROOT)}:{node.lineno}: "
                            f"from {node.module} import ..."
                        )

        if violations:
            pytest.fail(
                f"Found {len(violations)} imports from quantumvitas.history:\n"
                + "\n".join(violations[:20])
                + ("\n..." if len(violations) > 20 else "")
            )


class TestNoSkipHistoryParameter:
    """Verify skip_history parameter has been removed."""

    def test_yaml_io_no_skip_history(self):
        """yaml_io.py should not have skip_history parameter."""
        yaml_io = SRC_DIR / "core" / "yaml_io.py"
        source = yaml_io.read_text()

        # Check function signature
        if "skip_history" in source:
            # Find line numbers
            lines = source.splitlines()
            violations = []
            for i, line in enumerate(lines, 1):
                if "skip_history" in line:
                    violations.append(f"Line {i}: {line.strip()}")

            pytest.fail(
                f"yaml_io.py still contains skip_history:\n"
                + "\n".join(violations[:10])
            )

    def test_runner_no_skip_history(self):
        """runner.py should not have skip_history parameter."""
        runner = SRC_DIR / "calculation" / "runner.py"
        source = runner.read_text()

        if "skip_history" in source:
            lines = source.splitlines()
            violations = []
            for i, line in enumerate(lines, 1):
                if "skip_history" in line:
                    violations.append(f"Line {i}: {line.strip()}")

            pytest.fail(
                f"runner.py still contains skip_history:\n"
                + "\n".join(violations[:10])
            )


class TestNoHistoryDirectoryWrites:
    """Verify no code writes to .history/ directory."""

    # Pattern to match .history directory references
    HISTORY_DIR_PATTERN = re.compile(
        r'["\']\.history["\']|'
        r'HISTORY_DIR_NAME|'
        r'history_dir\s*=|'
        r'/\.history/',
        re.IGNORECASE,
    )

    # Allowed exceptions (comments, docs, migration helpers)
    ALLOWED_PATTERNS = frozenset({
        "# ",  # Comments
        "'''",  # Docstrings
        '"""',  # Docstrings
        "delete",  # Delete operations are OK
        "remove",  # Remove operations are OK
        "clean",  # Cleanup operations are OK
    })

    def test_no_history_dir_references(self):
        """No code should reference .history directory for writes."""
        violations = []

        # Files that are exempt (the history module itself, will be deleted)
        exempt_files = {
            "history/storage.py",
            "history/events.py",
            "history/__init__.py",
            "history/run_revision.py",
            "history/pins.py",
        }

        for path in SRC_DIR.rglob("*.py"):
            rel = path.relative_to(SRC_DIR).as_posix()
            if rel in exempt_files:
                continue

            try:
                source = path.read_text()
            except UnicodeDecodeError:
                continue

            lines = source.splitlines()
            for i, line in enumerate(lines, 1):
                if self.HISTORY_DIR_PATTERN.search(line):
                    # Check if this is an allowed pattern
                    stripped = line.strip()
                    is_allowed = any(
                        stripped.startswith(p) or p in stripped.lower()
                        for p in self.ALLOWED_PATTERNS
                    )
                    if not is_allowed:
                        violations.append(
                            f"{path.relative_to(PROJECT_ROOT)}:{i}: {stripped[:80]}"
                        )

        if violations:
            pytest.fail(
                f"Found {len(violations)} .history directory references:\n"
                + "\n".join(violations[:20])
                + ("\n..." if len(violations) > 20 else "")
            )


class TestHistoryModuleDeleted:
    """Verify the legacy history module has been deleted."""

    def test_history_module_not_exists(self):
        """src/quantumvitas/history/ should not exist."""
        history_dir = SRC_DIR / "history"
        if history_dir.exists():
            files = list(history_dir.rglob("*.py"))
            pytest.fail(
                f"Legacy history module still exists at {history_dir}\n"
                f"Files: {[f.name for f in files]}"
            )
