"""
Pre-migration behavior tests for CLI commands affected by Law H9 migration.

These tests capture the CURRENT behavior of CLI commands that will be migrated
from direct YAML writes to API calls. After migration, these tests MUST still pass.

Commands covered:
- init project
- init calculation
- init step

Note: Tests requiring structure fixtures are marked with @pytest.mark.slow
and can be run separately.
"""

import pytest
import yaml
from pathlib import Path
from typer.testing import CliRunner

from qmatsuite.cli.main import app


@pytest.fixture
def cli_runner():
    """Return a CLI test runner."""
    return CliRunner()


class TestInitProjectBehavior:
    """Capture init project behavior before migration."""

    def test_init_project_creates_project_yaml(self, tmp_path: Path, cli_runner: CliRunner):
        """init project creates project.qms.yml with correct schema."""
        project_dir = tmp_path / "test_project"

        result = cli_runner.invoke(app, ["init", "project", "--path", str(project_dir)])

        assert result.exit_code == 0, result.output
        assert (project_dir / "project.qms.yml").exists()

        # Verify schema
        config = yaml.safe_load((project_dir / "project.qms.yml").read_text())
        # Schema has "project" key with nested fields or top-level keys
        assert "calculations" in config
        assert "structures" in config
        # project.meta exists inside project key or top-level
        if "project" in config:
            assert "meta" in config["project"]
        else:
            assert "meta" in config

    def test_init_project_creates_subdirectories(self, tmp_path: Path, cli_runner: CliRunner):
        """init project creates structures/ and calculations/ directories."""
        project_dir = tmp_path / "test_project"

        result = cli_runner.invoke(app, ["init", "project", "--path", str(project_dir)])

        assert result.exit_code == 0, result.output
        assert (project_dir / "structures").is_dir()
        assert (project_dir / "calculations").is_dir()

    def test_init_project_outputs_success_message(self, tmp_path: Path, cli_runner: CliRunner):
        """init project outputs success message with path."""
        project_dir = tmp_path / "test_project"

        result = cli_runner.invoke(app, ["init", "project", "--path", str(project_dir)])

        assert result.exit_code == 0
        assert "Project created at" in result.output
        assert str(project_dir) in result.output


class TestInitCalculationBehaviorSimple:
    """Capture init calculation behavior - simple tests without structure requirements."""

    def test_init_calculation_requires_structure_or_template(
        self, tmp_path: Path, cli_runner: CliRunner
    ):
        """init calculation fails without --structure or --template."""
        project_dir = tmp_path / "test_project"
        cli_runner.invoke(app, ["init", "project", "--path", str(project_dir)])

        result = cli_runner.invoke(
            app,
            ["init", "calculation", "test_calc", "--project", str(project_dir)]
        )

        # Should fail - requires structure or template
        assert result.exit_code != 0
        assert "--structure is required" in result.output or "structure" in result.output.lower()


class TestCLIViolationLocations:
    """Document that CLI has direct YAML writes at specific locations.

    These are integration tests that verify the CLI code paths exist.
    After migration, these tests should be updated or removed.
    """

    def test_cli_has_write_step_spec_function(self):
        """Verify _write_step_spec exists in CLI (will be removed after migration)."""
        from qmatsuite.cli import main
        assert hasattr(main, "_write_step_spec")

    def test_cli_imports_yaml(self):
        """Verify CLI imports yaml for direct writes (indicates violation)."""
        import qmatsuite.cli.main as cli_main
        import inspect
        source = inspect.getsource(cli_main)
        # CLI currently imports yaml for direct writes
        assert "import yaml" in source or "from yaml" in source
