import json
from pathlib import Path

import pytest
import yaml
from pymatgen.core import Lattice, Structure
from typer.testing import CliRunner

from quantumvitas.project.model import Project
from quantumvitas.cli.main import app, _parse_override_args
from quantumvitas.workflow.input_runner import PreparedInputStep
from quantumvitas.core.engines.qe_workflow import StepResult
from quantumvitas.io import read_structure


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


def test_parse_override_args_basic():
    overrides = _parse_override_args(["--ecutwfc=50"])
    assert len(overrides) == 1
    assert overrides[0].name == "ecutwfc"
    assert overrides[0].value == 50
    assert overrides[0].section is None


def test_parse_override_args_with_section_and_flag():
    overrides = _parse_override_args(["--system.degauss", "0.01", "--lda_plus_u"])
    assert len(overrides) == 2
    first = overrides[0]
    assert first.name == "degauss"
    assert first.section == "system"
    assert abs(first.value - 0.01) < 1e-12
    second = overrides[1]
    assert second.name == "lda_plus_u"
    assert second.value is True


def test_cli_import_structure_registers_json(tmp_path: Path):
    runner = CliRunner()
    dest = tmp_path / "proj"
    result = runner.invoke(app, ["init", str(dest)])
    assert result.exit_code == 0

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
    source = tmp_path / "si.cif"
    structure.to(fmt="cif", filename=str(source))

    result = runner.invoke(
        app,
        [
            "import-structure",
            str(source),
            "--project",
            str(dest),
            "--id",
            "si_struct",
        ],
    )
    assert result.exit_code == 0, result.stdout

    stored = dest / "structures" / "si_struct.json"
    assert stored.exists()

    loaded = read_structure(stored)
    assert loaded.composition.reduced_formula == "Si"

    data = yaml.safe_load((dest / "project.qv.yml").read_text())
    assert any(entry["id"] == "si_struct" for entry in data["structures"])


def test_cli_run_stepfile_generates_input(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    project_root = tmp_path / "proj"
    project_root.mkdir()
    # Create minimal project file
    (project_root / "project.qv.yml").write_text(
        yaml.safe_dump({"project": {"name": "proj"}, "structures": [], "workflows": []})
    )
    (project_root / "structures").mkdir()

    # Create and import structure
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
    source = tmp_path / "si.cif"
    structure.to(fmt="cif", filename=str(source))
    result = runner.invoke(
        app,
        [
            "import-structure",
            str(source),
            "--project",
            str(project_root),
            "--id",
            "si",
        ],
    )
    assert result.exit_code == 0

    # Step file referencing structure
    step_file = tmp_path / "step.yaml"
    yaml.safe_dump(
        {
            "structure": "si",
            "step_type": "scf",
            "input_name": "si_step.pw.in",
            "parameters": {
                "SYSTEM": {"ecutwfc": 60},
                "ELECTRONS": {"conv_thr": 1e-8},
            },
        },
        step_file.open("w"),
    )

    captured = {}

    def fake_run_input_step(
        *,
        engine,
        input_file,
        working_dir,
        project_root,
        step_type=None,
        parameter_overrides=None,
    ):
        captured["input_file"] = input_file
        captured["working_dir"] = working_dir
        return (
            StepResult(
                step_type="scf",
                input_file=input_file,
                output_file=working_dir / "si_step.pw.out",
                success=True,
                return_code=0,
            ),
            PreparedInputStep(
                working_dir=working_dir,
                original_input=input_file,
                modified_input=input_file,
                project_root=project_root,
            ),
        )

    monkeypatch.setattr("quantumvitas.cli.main.run_input_step", fake_run_input_step)

    result = runner.invoke(
        app,
        [
            "run-stepfile",
            str(step_file),
            "--project",
            str(project_root),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Step file run finished" in result.stdout
    assert captured["input_file"].exists()


