"""
Gate test G-K3: YAML Read Single Entry Point (Law K3).

Enforces that all YAML reads in the kernel go through core/yaml_io.py.
Direct yaml.safe_load usage outside yaml_io.py is banned except for
explicitly allowlisted exceptions:

  EXC-003: Legacy code scheduled for deletion (deadline 2026-05-01)
  EXC-004: Non-SSOT files (settings, exports, in-memory strings)
  K4-ALLOW: Engine reads removed when PR-K4 lands (EngineInput replaces these)

Scanned packages (kernel): core, calculation, execution, engine, workflow,
analysis, project, history, io, ir, presets, data, drivers, engines, parsers, viz.

Excluded packages (frontends): cli, daemon, frontends, api, legacy.
Frontend YAML reads are covered by separate tests.
Legacy is excluded under EXC-003.
"""

import ast
import re
from pathlib import Path

import pytest


# Kernel packages to scan for yaml.safe_load violations
KERNEL_PACKAGES = [
    "core",
    "calculation",
    "execution",
    "engine",
    "workflow",
    "analysis",
    "project",
    "history",
    "io",
    "ir",
    "presets",
    "data",
    "drivers",
    "engines",
    "parsers",
    "viz",
]

# The ONLY file allowed to call yaml.safe_load for SSOT reads
YAML_IO_MODULE = "core/yaml_io.py"

# Allowlist: files that may use yaml.safe_load with justification
# Format: (relative_path_from_quantumvitas, line_number_or_None, exception_code)
ALLOWLIST = [
    # EXC-004: settings file, not SSOT
    ("project/storage.py", None, "EXC-004"),
    # EXC-004: snapshot import from in-memory string (not file path)
    ("project/snapshot.py", None, "EXC-004"),
    # EXC-003: legacy deletion scheduled 2026-05-01
    ("legacy/migrate.py", None, "EXC-003"),
    # K4-ALLOW: removed when PR-K4 lands (EngineInput replaces these reads)
    ("engine/pyscf_engine.py", None, "K4-ALLOW"),
    ("engine/orca_engine.py", None, "K4-ALLOW"),
    ("engine/psi4_engine.py", None, "K4-ALLOW"),
]

# Patterns that indicate a yaml.safe_load call
SAFE_LOAD_PATTERN = re.compile(r"yaml\.safe_load\b")


def _is_allowlisted(rel_path: str) -> bool:
    """Check if a file is in the allowlist."""
    for allowed_path, _, _ in ALLOWLIST:
        if rel_path.endswith(allowed_path):
            return True
    return False


def _find_safe_load_calls(file_path: Path) -> list[tuple[int, str]]:
    """Find all yaml.safe_load calls in a Python file, skipping comments and docstrings.

    Uses AST to identify string-literal nodes (docstrings, comments) and only
    reports actual code calls to yaml.safe_load.

    Returns list of (line_number, line_text) tuples.
    """
    try:
        content = file_path.read_text()
    except Exception:
        return []

    # Use AST to find lines occupied by string-literal expressions (docstrings)
    docstring_lines: set[int] = set()
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            _str_types = (ast.Constant,) + ((ast.Str,) if hasattr(ast, "Str") else ())
            if isinstance(node, ast.Expr) and isinstance(node.value, _str_types):
                # Mark all lines of this string literal as docstring
                for ln in range(node.lineno, (node.end_lineno or node.lineno) + 1):
                    docstring_lines.add(ln)
    except SyntaxError:
        pass  # If AST fails, fall back to regex-only

    results = []
    for i, line in enumerate(content.split("\n"), start=1):
        stripped = line.strip()
        # Skip comments
        if stripped.startswith("#"):
            continue
        # Skip docstring lines
        if i in docstring_lines:
            continue
        # Skip lines with EXC-004, EXC-003, or K4-ALLOW annotations
        if "EXC-004" in line or "EXC-003" in line or "K4-ALLOW" in line:
            continue
        if SAFE_LOAD_PATTERN.search(line):
            results.append((i, stripped))
    return results


class TestYamlReadSingleEntry:
    """Gate test: yaml.safe_load must only appear in core/yaml_io.py."""

    @pytest.fixture
    def src_root(self) -> Path:
        """Get quantumvitas source root."""
        return Path(__file__).parent.parent.parent / "src" / "quantumvitas"

    def test_no_yaml_safe_load_outside_yaml_io(self, src_root: Path):
        """
        All kernel Python files must not call yaml.safe_load directly.

        The only allowed location is core/yaml_io.py (the single entry point).
        Allowlisted files (EXC-003, EXC-004, K4-ALLOW) are excluded.
        """
        violations = []

        for package in KERNEL_PACKAGES:
            pkg_dir = src_root / package
            if not pkg_dir.exists():
                continue

            for py_file in pkg_dir.rglob("*.py"):
                rel_path = str(py_file.relative_to(src_root))

                # Skip the yaml_io module itself (it's the single entry point)
                if rel_path == YAML_IO_MODULE:
                    continue

                # Skip allowlisted files
                if _is_allowlisted(rel_path):
                    continue

                hits = _find_safe_load_calls(py_file)
                for line_num, line_text in hits:
                    violations.append((rel_path, line_num, line_text))

        if violations:
            report = "\n".join(
                f"  {path}:{line_num}: {text}"
                for path, line_num, text in violations
            )
            pytest.fail(
                f"Found {len(violations)} yaml.safe_load call(s) outside core/yaml_io.py:\n"
                f"{report}\n\n"
                f"Fix: Use CalcDoc/StepDoc/ProjectDoc .load(path).to_dict() from core/yamldoc.py,\n"
                f"or load_yaml_doc(path).to_dict() from core/yaml_io.py.\n"
                f"If this is a non-SSOT source, add '# EXC-004' comment on the same line."
            )

    def test_allowlisted_files_have_annotations(self, src_root: Path):
        """
        Allowlisted files must have EXC-003, EXC-004, or K4-ALLOW annotations
        on their yaml.safe_load lines, so the exception is visible in code review.
        """
        missing_annotations = []

        for allowed_path, _, exc_code in ALLOWLIST:
            file_path = src_root / allowed_path
            if not file_path.exists():
                continue

            content = file_path.read_text()
            for i, line in enumerate(content.split("\n"), start=1):
                if line.strip().startswith("#"):
                    continue
                if SAFE_LOAD_PATTERN.search(line):
                    if exc_code not in line:
                        missing_annotations.append(
                            (allowed_path, i, line.strip(), exc_code)
                        )

        if missing_annotations:
            report = "\n".join(
                f"  {path}:{num}: missing '{exc}' annotation: {text}"
                for path, num, text, exc in missing_annotations
            )
            pytest.fail(
                f"Allowlisted yaml.safe_load calls missing exception annotations:\n"
                f"{report}\n\n"
                f"Add '# {missing_annotations[0][3]}' comment on the yaml.safe_load line."
            )

    def test_yaml_io_is_the_single_read_entry(self, src_root: Path):
        """Verify core/yaml_io.py exists and contains _load_yaml_raw."""
        yaml_io = src_root / YAML_IO_MODULE
        assert yaml_io.exists(), f"{YAML_IO_MODULE} not found"

        content = yaml_io.read_text()
        assert "def _load_yaml_raw" in content, (
            f"{YAML_IO_MODULE} must define _load_yaml_raw()"
        )
        assert "yaml.safe_load" in content, (
            f"{YAML_IO_MODULE} must contain yaml.safe_load (it's the single entry point)"
        )
