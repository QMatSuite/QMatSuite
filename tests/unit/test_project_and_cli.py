import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quantumvitas.project.model import Project
from quantumvitas.cli.main import app


def _write_yaml(path: Path, data: dict) -> None:
    import yaml

    path.write_text(yaml.safe_dump(data, sort_keys=False))


@pytest.fixture()
def sample_project(tmp_path: Path) -> Path:
    project_root = tmp_path / "project"
    project_root.mkdir()
    project_config = {
        "project": {"name": "sample"},
        "workflows": [{"id": "wf", "path": "workflows/wf"}],
        "structures": [{"id": "si", "file": "structures/si.cif"}],
    }
    _write_yaml(project_root / "project.qv.yml", project_config)
    (project_root / "structures").mkdir()
    (project_root / "structures" / "si.cif").write_text("placeholder")
    workflow_dir = project_root / "workflows" / "wf"
    (workflow_dir / "raw").mkdir(parents=True)
    _write_yaml(
        workflow_dir / "workflow.yaml",
        {
            "id": "wf",
            "workflow": {"working_dir": "raw"},
            "steps": [{"id": "scf", "input": "raw/scf.in"}],
        },
    )
    (workflow_dir / "raw" / "scf.in").write_text("&control\n calculation='scf'\n/")
    return project_root


def test_project_open(sample_project: Path):
    project = Project.open(sample_project)
    assert project.list_workflows() == ["wf"]
    assert project.list_structures() == ["si"]
    workflow = project.get_workflow("wf")
    assert workflow.id == "wf"
    assert workflow.raw_dir == (sample_project / "workflows" / "wf" / "raw")


def test_cli_init(tmp_path: Path):
    runner = CliRunner()
    dest = tmp_path / "new_project"
    result = runner.invoke(app, ["init", str(dest), "--workflow-id", "demo"])
    assert result.exit_code == 0
    project_file = dest / "project.qv.yml"
    assert project_file.exists()
    workflow_file = dest / "workflows" / "demo" / "workflow.yaml"
    assert workflow_file.exists()


