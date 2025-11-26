"""
CLI-driven workflow tests for the Si DOS tutorial.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from quantumvitas.cli.main import app as cli_app
from tests.utils.workflow_projects import create_workflow_project

pytestmark = pytest.mark.qe_cli


@pytest.fixture
def cli_si_dos_project(ci_test_data_dir: Path, project_root_path: Path) -> Path:
    """Create a temporary project layout for CLI workflow testing."""
    steps = [
        {"id": "scf", "input": "si.1_scf.in", "reference": "si.1_scf.out"},
        {"id": "nscf", "input": "si.2_nscf.in", "reference": "si.2_nscf.out"},
        {"id": "dos", "input": "si.3_dos.in", "reference": "si.3_dos.out"},
    ]
    project_root = project_root_path / "temp" / "test_outputs" / "cli_si_dos_project"
    return create_workflow_project(
        project_root=project_root,
        workflow_id="si_dos",
        steps=steps,
        source_dir=ci_test_data_dir / "4_Si_DOS",
        pseudo_src=project_root_path / "pseudo",
    )


def test_cli_run_workflow(cli_si_dos_project: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli_app,
        ["run-workflow", "si_dos", "--project", str(cli_si_dos_project)],
    )
    assert result.exit_code == 0, result.output
    assert "Workflow si_dos status: StepStatus.SUCCESS" in result.output
    assert "- scf" in result.output
    assert "- nscf" in result.output
    assert "- dos" in result.output

