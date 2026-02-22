"""
CLI-driven calculation tests for the Si DOS tutorial.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from quantumvitas.cli.main import app as cli_app
from quantumvitas.core.resources import get_resources_dir
from tests.utils.calculation_projects import create_calculation_project

pytestmark = pytest.mark.qe_cli


@pytest.fixture
def cli_si_dos_project(ci_test_data_dir: Path, project_root_path: Path, tmp_path: Path) -> Path:
    """Create a temporary project layout for CLI calculation testing.

    Uses tmp_path for proper isolation in parallel xdist runs.
    """
    steps = [
        {"ulid": "scf", "input": "si.1_scf.in", "reference": "si.1_scf.out"},
        {"ulid": "nscf", "input": "si.2_nscf.in", "reference": "si.2_nscf.out"},
        {"ulid": "dos", "input": "si.3_dos.in", "reference": "si.3_dos.out"},
    ]
    # Use tmp_path for proper xdist isolation (each worker gets unique temp dir)
    project_root = tmp_path / "cli_si_dos_project"
    return create_calculation_project(
        project_root=project_root,
        calculation_id="si_dos",
        steps=steps,
        source_dir=ci_test_data_dir / "4_Si_DOS",
        pseudo_src=get_resources_dir() / "pseudo",
    )


def test_cli_run_calculation(cli_si_dos_project: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["run", "calculation", "si_dos", "--project", str(cli_si_dos_project), "--verbose"],
    )
    assert result.exit_code == 0, result.output
    assert "Calculation si_dos status: SUCCESS" in result.output
    # Check that all steps completed successfully
    assert "step_type_spec: qe_scf" in result.output
    assert "step_type_spec: qe_nscf" in result.output
    assert "step_type_spec: qe_dos" in result.output
