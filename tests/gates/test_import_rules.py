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
import os
import subprocess
import sys
from collections import defaultdict
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


def _should_enforce_gates() -> bool:
    """
    Check if architecture gates should be enforced.

    Returns:
        True by default (enforced/blocking mode).
        False if QMATSUITE_RELAX_ARCH_GATES == "1" (report-only mode for local dev).
        When False, violations are reported but tests don't fail.
    """
    return os.environ.get("QMATSUITE_RELAX_ARCH_GATES") != "1"


def _report_violations(violations: list, violation_type: str, context_path: Optional[Path] = None):
    """
    Report violations, either by failing (if enforcement enabled) or printing.

    Args:
        violations: List of violations to report (Violation objects or (line_num, func_name) tuples)
        violation_type: Description of violation type (e.g., "Forbidden kernel imports")
        context_path: Optional directory/file path for context
    """
    if not violations:
        return

    # Count violations by file
    by_file = defaultdict(list)
    for v in violations:
        if isinstance(v, tuple):  # Bare resolve calls: (line_num, func_name)
            # Use context_path or default to cli/main.py for bare calls
            target_file = context_path if context_path and context_path.is_file() else (
                PROJECT_ROOT / "src/quantumvitas/cli/main.py"
            )
            by_file[target_file].append(v)
        else:  # Violation object
            by_file[v.file_path].append(v)

    # Build report with improved diagnostics
    lines = [f"\n{'='*70}"]
    lines.append(f"{violation_type}: {len(violations)} total violation(s)")
    lines.append(f"{'='*70}")
    
    # Show top files with detailed information
    sorted_files = sorted(by_file.items(), key=lambda x: len(x[1]), reverse=True)
    for file_path_obj, file_violations in sorted_files[:10]:  # Top 10 files
        try:
            rel_path = file_path_obj.relative_to(PROJECT_ROOT)
        except ValueError:
            rel_path = file_path_obj
        
        lines.append(f"\n  File: {rel_path}")
        lines.append(f"  Violations: {len(file_violations)}")
        
        # Show first 5 violations per file with full details
        for v in file_violations[:5]:
            if isinstance(v, tuple):
                # Bare resolve call
                lines.append(f"    Line {v[0]}: bare call to {v[1]}()")
                lines.append(f"      Suggested fix: use QVService.{v[1]}_ref() or svc.{v[1]}_ref()")
            else:
                # Import violation
                import_stmt = f"{v.import_type} {v.module_name}"
                if v.import_type == "from":
                    import_stmt = f"from {v.module_name} import ..."
                lines.append(f"    Line {v.line_number}: {import_stmt}")
                lines.append(f"      Module: {v.module_name}")
                lines.append(f"      Forbidden prefix: {v.forbidden_prefix}")
                lines.append(f"      Suggested fix: use quantumvitas.api (QVService wrapper or re-export)")
        
        if len(file_violations) > 5:
            lines.append(f"    ... and {len(file_violations) - 5} more violation(s)")
    
    if len(sorted_files) > 10:
        lines.append(f"\n  ... and {len(sorted_files) - 10} more files with violations")
    
    lines.append(f"\n{'='*70}")
    lines.append("For more information, see: docs/plan/MULTI_FRONTEND_REFACTOR_MILESTONE.md")
    lines.append(f"{'='*70}\n")
    report = "\n".join(lines)
    
    if _should_enforce_gates():
        # Enforcement mode: fail the test
        pytest.fail(report)
    else:
        # Report mode: print and continue
        print(report)


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

        _report_violations(violations, "CLI: Forbidden kernel imports", cli_dir)

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

        _report_violations(violations, "Daemon: Forbidden kernel imports", daemon_dir)

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

        _report_violations(violations, "Notebook: Forbidden kernel imports", notebook_dir)

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

        _report_violations(violations, "Tools: Forbidden kernel imports", tools_dir)

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

        _report_violations(violations, "API: Forbidden frontend imports", api_file)

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

        _report_violations(violations, "CLI: Bare resolve_* function calls", cli_file)

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

