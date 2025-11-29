import json
import shlex
from pathlib import Path

import pytest
import yaml
from pymatgen.core import Lattice, Structure
from typer.testing import CliRunner

from quantumvitas.project.model import Project
from quantumvitas.cli.main import app, _parse_override_args
from quantumvitas.core.resources import slugify
from quantumvitas.workflow.input_runner import PreparedInputStep
from quantumvitas.workflow.geometry import read_geometry_from_input, compare_geometries
from quantumvitas.core.engines.qe_workflow import StepResult
from quantumvitas.io import QEInputParser, read_structure
from quantumvitas.workflow.types import StepMode
from tests.core.test_data import load_test_cases


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
    result = runner.invoke(app, ["init", "project", "--path", str(dest)])
    assert result.exit_code == 0, result.stdout
    project_file = dest / "project.qv.yml"
    assert project_file.exists()
    workflows_dir = dest / "workflows"
    assert workflows_dir.exists()
    assert not any(workflows_dir.iterdir())


def test_cli_init_auto_creates_project_dir():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(app, ["init", "project"])
        assert result.exit_code == 0, result.stdout
        project_dir = Path("project1")
        assert project_dir.is_dir()
        assert (project_dir / "project.qv.yml").exists()


def test_parse_override_args_basic():
    bundle = _parse_override_args(["--ecutwfc=50"])
    overrides = bundle.parameters
    assert len(overrides) == 1
    assert overrides[0].name == "ecutwfc"
    assert overrides[0].value == 50
    assert overrides[0].section is None


def test_parse_override_args_with_section_and_flag():
    bundle = _parse_override_args(["--system.degauss", "0.01", "--lda_plus_u"])
    overrides = bundle.parameters
    assert len(overrides) == 2
    first = overrides[0]
    assert first.name == "degauss"
    assert first.section == "system"
    assert abs(first.value - 0.01) < 1e-12
    second = overrides[1]
    assert second.name == "lda_plus_u"
    assert second.value is True


def test_parse_card_and_species_overrides():
    bundle = _parse_override_args(
        [
            "--CARD.K_POINTS.data=[[4,4,4,0,0,0]]",
            "--species.Si.mass=28.0855",
            "--species.Si.pseudopot=Si.pbe-n.UPF",
        ]
    )
    card = bundle.card_overrides["K_POINTS"]
    assert card["data"][0] == [4, 4, 4, 0, 0, 0]
    species = bundle.species_overrides["Si"]
    assert species["mass"] == 28.0855
    assert species["pseudopot"] == "Si.pbe-n.UPF"


def test_cli_import_structure_registers_json(tmp_path: Path):
    runner = CliRunner()
    dest = tmp_path / "proj"
    result = runner.invoke(app, ["init", "project", "--path", str(dest)])
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
    assert any(entry["meta"]["name"] == "si_struct" for entry in data["structures"])


def test_cli_list(sample_project: Path):
    runner = CliRunner()
    result = runner.invoke(app, ["list", "--project", str(sample_project)])
    assert result.exit_code == 0
    assert "Project: sample" in result.stdout
    assert "Structures:" in result.stdout
    assert "Workflows:" in result.stdout


def test_cli_rename_structure(sample_project: Path):
    runner = CliRunner()
    dest_path = "structures/si_renamed.cif"
    result = runner.invoke(
        app,
        [
            "rename",
            "structure",
            "si",
            "--project",
            str(sample_project),
            "--name",
            "Si renamed",
            "--path",
            dest_path,
        ],
    )
    assert result.exit_code == 0, result.stdout

    config = yaml.safe_load((sample_project / "project.qv.yml").read_text())
    entry = config["structures"][0]
    assert entry["name"] == "Si renamed"
    assert entry["file"] == dest_path
    assert entry["meta"]["slug"].startswith("si-renamed")
    assert (sample_project / dest_path).exists()


def test_cli_rename_workflow(sample_project: Path):
    runner = CliRunner()
    new_path = "workflows/wf_new"
    result = runner.invoke(
        app,
        [
            "rename",
            "workflow",
            "wf",
            "--project",
            str(sample_project),
            "--name",
            "Workflow new",
            "--path",
            new_path,
        ],
    )
    assert result.exit_code == 0, result.stdout

    config = yaml.safe_load((sample_project / "project.qv.yml").read_text())
    entry = config["workflows"][0]
    assert entry["name"] == "Workflow new"
    assert entry["path"] == new_path
    assert entry["meta"]["slug"].startswith("workflow-new")
    assert (sample_project / new_path).exists()


def test_cli_delete_structure(tmp_path: Path):
    runner = CliRunner()
    project_root = tmp_path / "proj"
    runner.invoke(app, ["init", "project", "--path", str(project_root)])

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
    source = tmp_path / "si.cif"
    structure.to(fmt="cif", filename=str(source))
    runner.invoke(
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
    structure_file = project_root / "structures" / "si.json"
    assert structure_file.exists()

    result = runner.invoke(
        app,
        [
            "delete",
            "structure",
            "si",
            "--project",
            str(project_root),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert not structure_file.exists()
    data = yaml.safe_load((project_root / "project.qv.yml").read_text())
    assert all(entry["name"] != "si" for entry in data["structures"])


def test_cli_delete_workflow(tmp_path: Path):
    runner = CliRunner()
    project_root = tmp_path / "proj"
    runner.invoke(app, ["init", "project", "--path", str(project_root)])

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
    source = tmp_path / "si.cif"
    structure.to(fmt="cif", filename=str(source))
    runner.invoke(
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
    runner.invoke(
        app,
        [
            "init",
            "workflow",
            "wf1",
            "--project",
            str(project_root),
            "--structure",
            "si",
        ],
    )
    wf_dir = project_root / "workflows" / "wf1"
    assert wf_dir.exists()

    result = runner.invoke(
        app,
        [
            "delete",
            "workflow",
            "wf1",
            "--project",
            str(project_root),
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert not wf_dir.exists()
    data = yaml.safe_load((project_root / "project.qv.yml").read_text())
    assert all(entry["name"] != "wf1" for entry in data["workflows"])


def test_cli_run_workflow_strict_option(sample_project: Path, monkeypatch):
    runner = CliRunner()
    captured = {}

    class DummyStatus:
        def __init__(self, value: str):
            self.value = value
            self.name = value.upper()

    class DummyStep:
        def __init__(self):
            self.step_id = "scf"
            self.status = DummyStatus("success")
            self.reference_file = None
            self.message = None
            self.metrics = {}

    class DummyResult:
        def __init__(self):
            self.status = DummyStatus("success")
            self.steps = [DummyStep()]

    def fake_run(self, workflow):
        captured["mode"] = workflow.mode
        return DummyResult()

    monkeypatch.setattr("quantumvitas.workflow.runner.WorkflowRunner.run", fake_run)

    result = runner.invoke(
        app,
        [
            "run",
            "workflow",
            "wf",
            "--project",
            str(sample_project),
            "--strict",
            "--verbose",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["mode"] == StepMode.STRICT
    assert "Workflow wf status" in result.stdout
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

    captured_runs: dict[str, Path] = {}

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
            "run",
            "step",
            str(step_file),
            "--project",
            str(project_root),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Step finished" in result.stdout
    assert captured["input_file"].exists()


def test_cli_run_step_accepts_step_yaml(tmp_path: Path, monkeypatch):
    runner = CliRunner()
    project_root = tmp_path / "proj"
    project_root.mkdir()
    (project_root / "project.qv.yml").write_text(
        yaml.safe_dump({"project": {"name": "proj"}, "structures": [], "workflows": []})
    )
    (project_root / "structures").mkdir()

    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
    source = tmp_path / "si.cif"
    structure.to(fmt="cif", filename=str(source))
    runner.invoke(
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

    step_file = tmp_path / "step.yaml"
    yaml.safe_dump(
        {"structure": "si", "step_type": "scf", "input_name": "si_step.pw.in"},
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
            "run",
            "step",
            str(step_file),
            "--project",
            str(project_root),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "Step finished" in result.stdout
    assert captured["input_file"].exists()


def test_cli_step_create_and_insert(sample_project: Path):
    runner = CliRunner()
    steps_dir = sample_project / "workflows" / "wf" / "steps"
    result = runner.invoke(
        app,
        [
            "init",
            "step",
            "si",
            "--project",
            str(sample_project),
            "--workflow",
            "wf",
            "--name",
            "nscf",
            "--type",
            "nscf",
            "--input-name",
            "nscf.pw.in",
            "--SYSTEM.ecutwfc=60",
            "--SYSTEM.ecutrho=240",
            "--CARD.K_POINTS.option=automatic",
            '--CARD.K_POINTS.data=[[4,4,4,0,0,0]]',
            "--species.Si.mass=28.0855",
            "--species.Si.pseudopot=Si.pbe-n-rrkjus_psl.1.0.0.UPF",
        ],
    )
    assert result.exit_code == 0, result.stdout
    spec_path = steps_dir / "nscf.step.yaml"
    assert spec_path.exists()
    spec_data = yaml.safe_load(spec_path.read_text())
    assert spec_data["structure"] == "si"
    assert spec_data["parameters"]["SYSTEM"]["ecutwfc"] == 60
    assert spec_data["cards"]["K_POINTS"]["option"] == "automatic"
    assert spec_data["cards"]["K_POINTS"]["data"][0] == [4, 4, 4, 0, 0, 0]
    assert spec_data["species_overrides"]["Si"]["mass"] == 28.0855
    assert (
        spec_data["species_overrides"]["Si"]["pseudopot"]
        == "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
    )

    workflow_yaml = sample_project / "workflows" / "wf" / "workflow.yaml"
    workflow_data = yaml.safe_load(workflow_yaml.read_text())
    assert any(step["id"] == "nscf" for step in workflow_data["steps"])


def test_cli_step_set_param(tmp_path: Path):
    step_file = tmp_path / "custom.step.yaml"
    yaml.safe_dump(
        {
            "structure": "si",
            "step_type": "scf",
            "parameters": {"SYSTEM": {"ecutwfc": 40}},
        },
        step_file.open("w"),
    )

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "configure",
            "step",
            str(step_file),
            "--SYSTEM.ecutwfc=80",
            "--CONTROL.tstress=true",
            "--CARD.K_POINTS.data=[[8,8,8,0,0,0]]",
            "--species.Si.mass=26.5",
        ],
    )
    assert result.exit_code == 0, result.stdout
    data = yaml.safe_load(step_file.read_text())
    assert data["parameters"]["SYSTEM"]["ecutwfc"] == 80
    assert data["parameters"]["CONTROL"]["tstress"] is True
    assert data["cards"]["K_POINTS"]["data"][0] == [8, 8, 8, 0, 0, 0]
    assert data["species_overrides"]["Si"]["mass"] == 26.5

    result = runner.invoke(
        app,
        [
            "configure",
            "step",
            str(step_file),
            "--remove",
            "--SYSTEM.ecutwfc=0",
            "--CARD.K_POINTS.rows.row1=0,0,1",
            "--species.Si.mass=0",
        ],
    )
    assert result.exit_code == 0, result.stdout
    data = yaml.safe_load(step_file.read_text())
    assert "SYSTEM" not in data["parameters"]
    cards = data.get("cards", {})
    assert cards["K_POINTS"]["rows"]["row1"] == [0, 0, 1]
    si_payload = data.get("species_overrides", {}).get("Si", {})
    assert "mass" not in si_payload


def test_cli_show_command(tmp_path: Path):
    input_file = tmp_path / "si_scf.in"
    input_file.write_text(
        "&CONTROL\n  calculation = 'scf'\n/\n&SYSTEM\n  ecutwfc = 30\n  ecutrho = 240\n/\n"
    )
    runner = CliRunner()
    result = runner.invoke(app, ["show-command", str(input_file)])
    assert result.exit_code == 0
    assert "qv init step '<structure-id>'" in result.stdout
    assert "configure step" in result.stdout


def test_cli_show_command_generates_matching_input(
    ci_test_data_dir: Path, tmp_path: Path, monkeypatch
):
    runner = CliRunner()
    project_root = tmp_path / "proj"
    assert (
        runner.invoke(app, ["init", "project", "--path", str(project_root)]).exit_code == 0
    ), "project init failed"

    pw_dir = ci_test_data_dir / "pw_single_tests"
    cases = load_test_cases(pw_dir, ci_root=ci_test_data_dir)
    assert cases, "No pw_single_tests inputs found."

    captured_runs: dict[str, Path] = {}

    def fake_run_input_step(
        *,
        engine,
        input_file,
        working_dir,
        project_root,
        step_type=None,
        parameter_overrides=None,
    ):
        captured_runs["input_file"] = input_file
        return (
            StepResult(
                step_type=step_type or "scf",
                input_file=input_file,
                output_file=working_dir / f"{input_file.stem}.out",
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

    geometry_skipped = []
    for case in cases:
        input_path = case.input_path
        structure_name = f"struct_{input_path.stem}"
        workflow_name = f"wf_{input_path.stem}"

        result = runner.invoke(
            app,
            [
                "import-structure",
                str(input_path),
                "--project",
                str(project_root),
                "--name",
                structure_name,
            ],
        )
        assert (
            result.exit_code == 0
        ), f"import-structure failed for {input_path}: {result.stdout}"

        result = runner.invoke(
            app,
            [
                "init",
                "workflow",
                workflow_name,
                "--structure",
                structure_name,
                "--project",
                str(project_root),
            ],
        )
        assert (
            result.exit_code == 0
        ), f"init workflow failed for {workflow_name}: {result.stdout}"

        show_output = runner.invoke(app, ["show-command", str(input_path)])
        assert show_output.exit_code == 0, show_output.stdout
        init_line = next(
            line.strip()
            for line in show_output.stdout.splitlines()
            if line.strip().startswith("qv init step")
        )
        init_args = shlex.split(init_line)[1:]
        placeholder_index = init_args.index("<structure-id>")
        init_args[placeholder_index] = structure_name
        init_args.extend(["--workflow", workflow_name, "--project", str(project_root)])
        init_result = runner.invoke(app, init_args)
        assert init_result.exit_code == 0, init_result.stdout

        workflow_slug = slugify(workflow_name)
        workflow_dir = project_root / "workflows" / workflow_slug
        workflow_yaml = yaml.safe_load((workflow_dir / "workflow.yaml").read_text())
        last_step = workflow_yaml["steps"][-1]
        step_spec_path = workflow_dir / last_step["step_file"]

        captured_runs.clear()
        workdir = tmp_path / f"workdir_{input_path.stem}"
        run_result = runner.invoke(
            app,
            [
                "run",
                "step",
                str(step_spec_path),
                "--project",
                str(project_root),
                "--workdir",
                str(workdir),
            ],
        )
        assert run_result.exit_code == 0, run_result.stdout
        generated_input = captured_runs.get("input_file")
        assert generated_input and generated_input.exists()

        original_qe = QEInputParser.parse_file(input_path)
        generated_qe = QEInputParser.parse_file(generated_input)

        # Structural parameters are intentionally transformed (ibrav -> ibrav=0 + CELL_PARAMETERS)
        # so we only compare non-structural parameters
        STRUCTURAL_KEYS = {"ibrav", "nat", "ntyp", "a", "b", "c", "cosab", "cosac", "cosbc"}

        def _param_map(qe_input):
            result = {}
            for nl in qe_input.namelists:
                params = dict(nl.parameters)
                # Remove structural parameters from comparison
                for key in list(params.keys()):
                    lower_key = str(key).lower()
                    if lower_key in STRUCTURAL_KEYS or lower_key.startswith("celldm"):
                        del params[key]
                if params:
                    result[nl.name.upper()] = params
            return result

        assert _param_map(original_qe) == _param_map(generated_qe)

        try:
            original_geom = read_geometry_from_input(input_path)
            generated_geom = read_geometry_from_input(generated_input)
        except ValueError:
            geometry_skipped.append(input_path.name)
        else:
            success, message = compare_geometries(
                generated_geom, original_geom, cell_atol=1e-5, position_atol=1e-4
            )
            assert success, f"{input_path.name}: {message}"

    if geometry_skipped:
        print(
            f"Geometry comparison skipped for {len(geometry_skipped)}/{len(cases)} inputs: {geometry_skipped}"
        )
    else:
        print("Geometry comparison executed for all inputs.")


def test_cli_get_command_alias(tmp_path: Path):
    input_file = tmp_path / "si_scf.in"
    input_file.write_text("&CONTROL\n  calculation = 'scf'\n/\n")
    runner = CliRunner()
    result = runner.invoke(app, ["get-command", str(input_file)])
    assert result.exit_code == 0
    assert "qv init step '<structure-id>'" in result.stdout


def test_cli_delete_structure(tmp_path: Path):
    runner = CliRunner()
    project_root = tmp_path / "proj"
    runner.invoke(app, ["init", "project", "--path", str(project_root)])
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
    source = tmp_path / "si.cif"
    structure.to(fmt="cif", filename=str(source))
    runner.invoke(
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
    structure_file = project_root / "structures" / "si.json"
    assert structure_file.exists()

    result = runner.invoke(
        app,
        ["delete", "structure", "si", "--project", str(project_root)],
    )
    assert result.exit_code == 0, result.stdout
    assert not structure_file.exists()
    data = yaml.safe_load((project_root / "project.qv.yml").read_text())
    assert not any(entry["name"] == "si" for entry in data["structures"])


def test_cli_delete_workflow(tmp_path: Path):
    runner = CliRunner()
    project_root = tmp_path / "proj"
    runner.invoke(app, ["init", "project", "--path", str(project_root)])
    structure = Structure(Lattice.cubic(5.43), ["Si"], [[0, 0, 0]])
    source = tmp_path / "si.cif"
    structure.to(fmt="cif", filename=str(source))
    runner.invoke(
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
    result = runner.invoke(
        app,
        [
            "init",
            "workflow",
            "wf1",
            "--project",
            str(project_root),
            "--structure",
            "si",
        ],
    )
    assert result.exit_code == 0, result.stdout
    wf_dir = project_root / "workflows" / "wf1"
    assert wf_dir.exists()

    result = runner.invoke(
        app,
        ["delete", "workflow", "wf1", "--project", str(project_root)],
    )
    assert result.exit_code == 0, result.stdout
    assert not wf_dir.exists()
    data = yaml.safe_load((project_root / "project.qv.yml").read_text())
    assert not any(entry["name"] == "wf1" for entry in data["workflows"])


