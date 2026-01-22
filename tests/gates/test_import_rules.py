"""
Gate tests for import rule enforcement.

These tests verify the architecture's import rules are not violated.
They detect IMPORTS using AST, not method calls.

CRITICAL: These must NOT false-positive on legitimate method calls like:
    svc.resolve_calculation(...)  # OK - method call
    QVService().resolve_calculation(...)  # OK - method call

They SHOULD catch:
    from quantumvitas.core.resolution import resolve_calculation  # FORBIDDEN
    import quantumvitas.core.resolution  # FORBIDDEN
    from quantumvitas.core import resolution  # FORBIDDEN
"""

import ast
import importlib
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for Python < 3.11
    except ImportError:
        tomllib = None

from tests.gates._import_scan import scan_python_files, Violation

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _discover_cli_entry_module() -> str:
    """
    Discover the CLI entry module from pyproject.toml.

    Returns:
        Module path (e.g., "quantumvitas.cli.main")
    """
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    if not pyproject_path.exists():
        raise RuntimeError("pyproject.toml not found")

    # Try tomllib first (Python 3.11+)
    if tomllib:
        with open(pyproject_path, "rb") as f:
            config = tomllib.load(f)
    else:
        # Fallback: try toml package if available
        try:
            import toml
            config = toml.load(pyproject_path)
        except ImportError:
            # Last resort: parse manually for console_scripts
            content = pyproject_path.read_text()
            if 'qv = "quantumvitas.cli:app"' in content:
                # Default based on known structure
                return "quantumvitas.cli.main"
            raise RuntimeError("Cannot parse pyproject.toml - install tomli or toml")

    # Extract console_scripts entry
    scripts = config.get("project", {}).get("scripts", {})
    if "qv" in scripts:
        entry_point = scripts["qv"]
        # Format: "quantumvitas.cli:app" -> module is "quantumvitas.cli"
        if ":" in entry_point:
            module_part = entry_point.split(":")[0]
            # The actual module with app is cli/main.py
            if module_part == "quantumvitas.cli":
                return "quantumvitas.cli.main"
            return module_part
        return entry_point

    # Fallback: search for Typer app
    cli_main = PROJECT_ROOT / "src/quantumvitas/cli/main.py"
    if cli_main.exists():
        return "quantumvitas.cli.main"

    raise RuntimeError("Cannot discover CLI entry module")


def _discover_daemon_entry_module() -> str:
    """
    Discover the daemon entry module.

    Returns:
        Module path (e.g., "quantumvitas.daemon.server")
    """
    # Check if daemon/server.py exists
    daemon_server = PROJECT_ROOT / "src/quantumvitas/daemon/server.py"
    if daemon_server.exists():
        # Check if it has QVDaemon class
        content = daemon_server.read_text()
        if "class QVDaemon" in content:
            return "quantumvitas.daemon.server"

    # Fallback: search for server/app factory patterns
    # This is a last resort - we expect daemon/server.py to exist
    raise RuntimeError("Cannot discover daemon entry module - daemon/server.py not found")


def _get_bootstrap_allowlist() -> dict[str, set[str]]:
    """
    Get the extremely narrow bootstrap exception allowlist.

    Returns:
        Dict mapping file paths (as strings) to sets of allowed module prefixes.
        Only ONE file should be allowed, and only minimal imports.
    """
    bootstrap_path = PROJECT_ROOT / "src/quantumvitas/frontends/_shared/bootstrap.py"
    if bootstrap_path.exists():
        # Allow ONLY quantumvitas.core.context for bootstrap
        return {
            str(bootstrap_path): {"quantumvitas.core.context"}
        }
    # No bootstrap file exists yet - no exceptions
    return {}


class TestFrontendImportRules:
    """Frontends must not import from kernel modules."""

    FORBIDDEN_PREFIXES = (
        "quantumvitas.core",
        "quantumvitas.calculation",
        "quantumvitas.analysis",
        "quantumvitas.io",
        "quantumvitas.drivers",
        "quantumvitas.engine",
        "quantumvitas.workflow",
        "quantumvitas.presets",
    )

    def test_cli_no_kernel_imports(self):
        """cli/* must not import from kernel modules."""
        cli_dir = PROJECT_ROOT / "src/quantumvitas/cli"
        if not cli_dir.exists():
            pytest.skip("CLI directory does not exist")

        allowed_paths = _get_bootstrap_allowlist()
        violations = scan_python_files(
            [cli_dir],
            self.FORBIDDEN_PREFIXES,
            allowed_paths=allowed_paths,
        )

        # Filter out any in-progress migration markers
        violations = [
            v
            for v in violations
            if not self._has_migration_marker(v.file_path, v.line_number)
        ]

        assert violations == [], self._format_violations(violations)

    def test_daemon_no_kernel_imports(self):
        """daemon/* must not import from kernel modules."""
        daemon_dir = PROJECT_ROOT / "src/quantumvitas/daemon"
        if not daemon_dir.exists():
            pytest.skip("Daemon directory does not exist")

        allowed_paths = _get_bootstrap_allowlist()
        violations = scan_python_files(
            [daemon_dir],
            self.FORBIDDEN_PREFIXES,
            allowed_paths=allowed_paths,
        )

        violations = [
            v
            for v in violations
            if not self._has_migration_marker(v.file_path, v.line_number)
        ]

        assert violations == [], self._format_violations(violations)

    def test_notebook_no_kernel_imports(self):
        """notebook/* must not import from kernel modules."""
        notebook_dir = PROJECT_ROOT / "src/quantumvitas/frontends/notebook"
        if not notebook_dir.exists():
            pytest.skip("Notebook frontend does not exist")

        allowed_paths = _get_bootstrap_allowlist()
        violations = scan_python_files(
            [notebook_dir],
            self.FORBIDDEN_PREFIXES,
            allowed_paths=allowed_paths,
        )

        assert violations == [], self._format_violations(violations)

    def _has_migration_marker(self, file_path: Path, line_number: int) -> bool:
        """Check if a line has a migration marker comment."""
        try:
            lines = file_path.read_text().splitlines()
            if line_number <= len(lines):
                line = lines[line_number - 1]
                return "# MIGRATION:" in line or "# MIGRATION ZONE" in line
        except Exception:
            pass
        return False

    def _format_violations(self, violations: list[Violation]) -> str:
        """Format violations for assertion message."""
        if not violations:
            return ""
        lines = ["Forbidden kernel imports found:"]
        for v in violations:
            lines.append(
                f"  {v.file_path.relative_to(PROJECT_ROOT)}:{v.line_number}: "
                f"{v.import_type} {v.module_name} (forbidden prefix: {v.forbidden_prefix})"
            )
        return "\n".join(lines)


class TestToolsImportRules:
    """Tools must only import from api."""

    FORBIDDEN_PREFIXES = (
        "quantumvitas.core",
        "quantumvitas.calculation",
        "quantumvitas.drivers",
        "quantumvitas.analysis",
        "quantumvitas.io",
        "quantumvitas.engine",
    )

    def test_tools_no_kernel_imports(self):
        """tools/* must not import from kernel modules."""
        tools_dir = PROJECT_ROOT / "src/quantumvitas/tools"
        if not tools_dir.exists():
            pytest.skip("Tools directory does not exist")

        violations = scan_python_files(
            [tools_dir],
            self.FORBIDDEN_PREFIXES,
        )

        assert violations == [], self._format_violations(violations)

    def _format_violations(self, violations: list[Violation]) -> str:
        """Format violations for assertion message."""
        if not violations:
            return ""
        lines = ["Forbidden kernel imports in tools:"]
        for v in violations:
            lines.append(
                f"  {v.file_path.relative_to(PROJECT_ROOT)}:{v.line_number}: "
                f"{v.import_type} {v.module_name}"
            )
        return "\n".join(lines)


class TestAPIImportRules:
    """API must not import from frontends or tools."""

    FORBIDDEN_PREFIXES = ("quantumvitas.frontends", "quantumvitas.cli", "quantumvitas.daemon", "quantumvitas.tools")

    def test_api_no_frontend_imports(self):
        """api.py must not import from frontends/*."""
        api_file = PROJECT_ROOT / "src/quantumvitas/api.py"
        if not api_file.exists():
            pytest.skip("API file does not exist")

        violations = scan_python_files(
            [api_file.parent],
            self.FORBIDDEN_PREFIXES,
        )

        # Filter to only api.py
        violations = [v for v in violations if v.file_path.name == "api.py"]

        assert violations == [], self._format_violations(violations)

    def _format_violations(self, violations: list[Violation]) -> str:
        """Format violations for assertion message."""
        if not violations:
            return ""
        lines = ["Forbidden frontend imports in API:"]
        for v in violations:
            lines.append(
                f"  {v.file_path.relative_to(PROJECT_ROOT)}:{v.line_number}: "
                f"{v.import_type} {v.module_name}"
            )
        return "\n".join(lines)


class TestCLIThinRule:
    """
    CLI thin rule: CLI must not make bare calls to resolve_* functions.

    This detects AST Call nodes where func is a Name (not Attribute).
    Method calls like svc.resolve_calculation() are ast.Attribute and are allowed.
    """

    def test_cli_no_bare_resolve_calls(self):
        """CLI must not make bare calls to resolve_* functions."""
        cli_file = PROJECT_ROOT / "src/quantumvitas/cli/main.py"
        if not cli_file.exists():
            pytest.skip("CLI main.py does not exist")

        violations = self._scan_bare_calls(cli_file)

        assert violations == [], self._format_violations(violations)

    def _scan_bare_calls(self, file_path: Path) -> list[tuple[int, str]]:
        """
        Scan for bare calls to resolve_* functions using AST.

        Returns:
            List of (line_number, function_name) tuples
        """
        violations = []
        forbidden_functions = {"resolve_calculation", "resolve_step", "resolve_structure"}

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return violations
        except Exception:
            return violations

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if this is a bare call (func is Name, not Attribute)
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                    if func_name in forbidden_functions:
                        violations.append((node.lineno, func_name))

        return violations

    def _format_violations(self, violations: list[tuple[int, str]]) -> str:
        """Format violations for assertion message."""
        if not violations:
            return ""
        lines = ["Bare resolve_* function calls found (use svc.resolve_*_ref() instead):"]
        for line_num, func_name in violations:
            lines.append(f"  {PROJECT_ROOT / 'src/quantumvitas/cli/main.py'}:{line_num}: {func_name}()")
        return "\n".join(lines)


class TestImportabilitySmoke:
    """
    Smoke tests that verify key modules are importable.

    CRITICAL: These catch the "gates green but code broken" scenario.
    Entry modules are discovered dynamically, not hardcoded.
    """

    def test_cli_importable(self):
        """CLI entry module must be importable."""
        try:
            cli_module_path = _discover_cli_entry_module()
        except RuntimeError as e:
            pytest.skip(f"Cannot discover CLI entry module: {e}")

        try:
            module = importlib.import_module(cli_module_path)
            # Check that 'app' attribute exists (for Typer)
            if not hasattr(module, "app"):
                pytest.fail(f"CLI module {cli_module_path} does not have 'app' attribute")
        except ImportError as e:
            pytest.fail(f"CLI import failed: {e}")

    def test_daemon_importable(self):
        """Daemon entry module must be importable."""
        try:
            daemon_module_path = _discover_daemon_entry_module()
        except RuntimeError as e:
            pytest.skip(f"Cannot discover daemon entry module: {e}")

        try:
            module = importlib.import_module(daemon_module_path)
            # Check that 'QVDaemon' class exists
            if not hasattr(module, "QVDaemon"):
                pytest.fail(f"Daemon module {daemon_module_path} does not have 'QVDaemon' class")
        except ImportError as e:
            pytest.fail(f"Daemon import failed: {e}")

    def test_api_importable(self):
        """API must be importable."""
        try:
            from quantumvitas.api import QVService
        except ImportError as e:
            pytest.fail(f"API import failed: {e}")

    def test_package_importable(self):
        """Main package must be importable."""
        try:
            import quantumvitas
        except ImportError as e:
            pytest.fail(f"Package import failed: {e}")

    def test_cli_compiles(self):
        """CLI must compile without syntax errors."""
        cli_file = PROJECT_ROOT / "src/quantumvitas/cli/main.py"
        if not cli_file.exists():
            pytest.skip("CLI main.py does not exist")

        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(cli_file)],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"CLI compilation failed:\n{result.stderr}"
        )

    def test_daemon_compiles(self):
        """Daemon must compile without syntax errors."""
        daemon_file = PROJECT_ROOT / "src/quantumvitas/daemon/server.py"
        if not daemon_file.exists():
            pytest.skip("Daemon server.py does not exist")

        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(daemon_file)],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, (
            f"Daemon compilation failed:\n{result.stderr}"
        )

