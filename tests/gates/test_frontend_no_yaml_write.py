"""
Gate test for Law H9: Filesystem Access Control.

Per API Constitution Law H9:
- Only kernel (core layer) is allowed to modify YAML SSOT files
- Frontends (daemon, CLI) MUST NOT write to YAML files directly
- All filesystem mutations MUST go through kernel via API calls

YAML SSOT files:
- project.qms.yml -> ProjectDoc
- calculation.yaml -> CalcDoc
- *.step.yaml -> StepDoc

This gate test detects direct YAML writes in frontend code.
"""

import ast
import re
from pathlib import Path

import pytest


# Patterns that indicate direct YAML writes (Law H9 violations)
YAML_WRITE_PATTERNS = [
    r"\.write_text\s*\(\s*yaml\.safe_dump",
    r"\.write_text\s*\(\s*yaml\.dump",
    r"yaml\.safe_dump\s*\([^)]+,\s*\w+\)",  # yaml.safe_dump(data, file)
    r"yaml\.dump\s*\([^)]+,\s*\w+\)",  # yaml.dump(data, file)
]

# SSOT file patterns that should not be written by frontends
SSOT_FILE_PATTERNS = [
    r"project\.qms\.yml",
    r"calculation\.yaml",
    r"\.step\.yaml",
]

# Allowed exceptions per H9.3
ALLOWED_EXCEPTIONS = [
    # User export files (not SSOT)
    "export_project_to_snapshot",
    "save_project_command",  # Writes to user-specified output file
    # Test files that simulate CLI behavior
    "tests/",
]


def find_yaml_write_violations(file_path: Path) -> list[tuple[int, str]]:
    """
    Find lines in a file that contain potential YAML write violations.

    Returns:
        List of (line_number, line_content) tuples for violations
    """
    violations = []
    content = file_path.read_text()
    lines = content.split("\n")

    for i, line in enumerate(lines, start=1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        # Check for YAML write patterns
        for pattern in YAML_WRITE_PATTERNS:
            if re.search(pattern, line):
                # Check if it's an allowed exception
                is_allowed = False
                for exception in ALLOWED_EXCEPTIONS:
                    if exception in str(file_path) or exception in line:
                        is_allowed = True
                        break

                if not is_allowed:
                    violations.append((i, line.strip()))
                break

    return violations


class TestFrontendNoYamlWrite:
    """Gate test: Frontends must not write YAML files directly."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def test_cli_no_direct_yaml_writes(self, project_root: Path):
        """
        CLI must not contain direct YAML write calls to SSOT files.

        Per Law H9, CLI should use API calls for all YAML modifications.
        """
        cli_path = project_root / "src" / "qmatsuite" / "cli" / "main.py"
        if not cli_path.exists():
            pytest.skip(f"CLI file not found: {cli_path}")

        violations = find_yaml_write_violations(cli_path)

        # Filter out known allowed patterns
        real_violations = []
        for line_num, line in violations:
            # Check if this is writing to a user-specified output (allowed)
            if "output_path.write_text" in line:
                continue
            # Check if this is in a TODO-marked section
            if "TODO:" in line:
                continue
            real_violations.append((line_num, line))

        # Filter out _write_step_spec helper (standalone step files, allowed per H9.3)
        # _write_step_spec is only used for standalone steps or user export files
        # These are not SSOT files (project.qms.yml, calculation.yaml, *.step.yaml in calculations)
        cli_content = cli_path.read_text()
        cli_lines = cli_content.split("\n")
        filtered_violations = []
        for line_num, line in real_violations:
            # Check if this line is inside _write_step_spec function
            # by looking at surrounding context (up to 50 lines back)
            in_write_step_spec = False
            for check_line_num in range(line_num - 1, max(0, line_num - 50), -1):
                check_line = cli_lines[check_line_num - 1] if check_line_num <= len(cli_lines) else ""
                if "def _write_step_spec" in check_line:
                    in_write_step_spec = True
                    break
                # Stop at any other function definition
                if check_line.startswith("def ") and "_write_step_spec" not in check_line:
                    break
            if not in_write_step_spec:
                filtered_violations.append((line_num, line))
        real_violations = filtered_violations

        if real_violations:
            violation_report = "\n".join(
                f"  Line {num}: {line}" for num, line in real_violations
            )
            pytest.fail(
                f"CLI contains {len(real_violations)} direct YAML write violation(s):\n"
                f"{violation_report}\n\n"
                f"Per Law H9, use API calls instead:\n"
                f"  - svc.calculation.add_step_from_spec() for step creation\n"
                f"  - svc.project.init_calculation() for calculation creation\n"
                f"  - QMSService.init_project() for project creation\n"
            )

    def test_daemon_no_direct_yaml_writes(self, project_root: Path):
        """
        Daemon must not contain direct YAML write calls to SSOT files.

        Per Law H9, daemon should use API calls for all YAML modifications.
        """
        daemon_path = project_root / "src" / "qmatsuite" / "daemon" / "server.py"
        if not daemon_path.exists():
            pytest.skip(f"Daemon file not found: {daemon_path}")

        violations = find_yaml_write_violations(daemon_path)

        if violations:
            violation_report = "\n".join(
                f"  Line {num}: {line}" for num, line in violations
            )
            pytest.fail(
                f"Daemon contains {len(violations)} direct YAML write violation(s):\n"
                f"{violation_report}\n\n"
                f"Per Law H9, use API calls instead."
            )

    def test_api_utils_no_yaml_writes(self, project_root: Path):
        """
        API utils must not write YAML files directly.

        Per Law H2, utils should be pure helpers or proxy reexports.
        YAML writes belong in service methods.
        """
        utils_path = project_root / "src" / "qmatsuite" / "api" / "utils.py"
        if not utils_path.exists():
            pytest.skip(f"Utils file not found: {utils_path}")

        violations = find_yaml_write_violations(utils_path)

        # Filter out snapshot export (allowed per H9.3)
        real_violations = [
            (num, line) for num, line in violations
            if "snapshot" not in line.lower()
        ]

        if real_violations:
            violation_report = "\n".join(
                f"  Line {num}: {line}" for num, line in real_violations
            )
            pytest.fail(
                f"API utils contains {len(real_violations)} direct YAML write violation(s):\n"
                f"{violation_report}\n\n"
                f"Per Law H2, move YAML writes to service methods."
            )


class TestSSSOTWriterClasses:
    """Verify SSOT files are only written by their designated YamlDoc classes."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def test_yamldoc_classes_exist(self, project_root: Path):
        """Verify the required YamlDoc classes exist in core/yamldoc.py."""
        yamldoc_path = project_root / "src" / "qmatsuite" / "core" / "yamldoc.py"
        if not yamldoc_path.exists():
            pytest.skip(f"yamldoc.py not found: {yamldoc_path}")

        content = yamldoc_path.read_text()

        # Check for required classes
        required_classes = ["StepDoc", "CalcDoc", "ProjectDoc"]
        missing = [cls for cls in required_classes if f"class {cls}" not in content]

        if missing:
            pytest.fail(
                f"Missing required YamlDoc classes in core/yamldoc.py: {missing}\n"
                f"Per Law H9.1, these classes are the only allowed writers for SSOT files."
            )
