"""
CLI-driven workflow tests for the Si DOS tutorial.
"""

from pathlib import Path
import shutil

import pytest
import yaml
from typer.testing import CliRunner

from quantumvitas.cli.main import app as cli_app

pytestmark = pytest.mark.qe_cli


@pytest.fixture
def cli_si_dos_project(ci_test_data_dir: Path, project_root_path: Path) -> Path:
    """Create a temporary project layout for CLI workflow testing."""
    si_dos_dir = ci_test_data_dir / "4_Si_DOS"
    project_root = project_root_path / "temp" / "test_outputs" / "cli_si_dos_project"
    if project_root.exists():
        shutil.rmtree(project_root)

    workflow_dir = project_root / "workflows" / "si_dos"
    raw_dir = workflow_dir / "raw"
    reference_dir = workflow_dir / "reference"
    raw_dir.mkdir(parents=True, exist_ok=True)
    reference_dir.mkdir(parents=True, exist_ok=True)

    for name in ["si.1_scf.in", "si.2_nscf.in", "si.3_dos.in"]:
        shutil.copy2(si_dos_dir / name, raw_dir / name)

    pseudo_src = project_root_path / "pseudo"
    shutil.copytree(pseudo_src, project_root / "pseudo")

    project_config = {
        "project": {"name": "cli_si_dos"},
        "workflows": [{"id": "si_dos", "path": "workflows/si_dos"}],
        "structures": [],
        "settings": {},
    }
    (project_root / "project.qv.yml").write_text(
        yaml.safe_dump(project_config, sort_keys=False)
    )

    reference_map = {
        "scf": ("si.1_scf.out", "reference/si.1_scf.out"),
        "nscf": ("si.2_nscf.out", "reference/si.2_nscf.out"),
        "dos": ("si.3_dos.out", "reference/si.3_dos.out"),
    }
    for src_name, rel_path in reference_map.values():
        dest = workflow_dir / Path(rel_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(si_dos_dir / "reference_out" / src_name, dest)

    workflow_config = {
        "id": "si_dos",
        "mode": "strict",
        "workflow": {"working_dir": "raw"},
        "steps": [
            {
                "id": "scf",
                "input": "si.1_scf.in",
                "reference": reference_map["scf"][1],
            },
            {
                "id": "nscf",
                "input": "si.2_nscf.in",
                "reference": reference_map["nscf"][1],
            },
            {
                "id": "dos",
                "input": "si.3_dos.in",
                "reference": reference_map["dos"][1],
            },
        ],
    }
    (workflow_dir / "workflow.yaml").write_text(
        yaml.safe_dump(workflow_config, sort_keys=False)
    )

    return project_root


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

