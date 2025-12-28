import shlex
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from quantumvitas.cli.main import app
from quantumvitas.core.resources import slugify
from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.qe_calculation import StepResult
from tests.core.qe_step_verification import verify_step_result
from tests.core.test_data import load_test_cases

pytestmark = pytest.mark.qe_cli


@pytest.fixture(scope="module")
def qe_engine() -> QuantumEspressoEngine:
    config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    if not engine.detect_executable("pw.x"):
        pytest.skip("pw.x not found. CLI step integration requires QE.")
    return engine


def _extract_paths(stdout: str) -> tuple[Path, Path]:
    """
    Extract output and input file paths from CLI output.
    
    Expected format: "Step finished: <output_path> -> (input <input_path>)"
    """
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("Step finished:"):
            continue
        if "->" not in line:
            break
        
        # Parse: "Step finished: <output_path> -> (input <input_path>)"
        # Extract the part after "Step finished:"
        after_prefix = line.split("Step finished:", 1)[1].strip()
        
        # Split on "->" to separate output and input
        if "->" in after_prefix:
            output_part, input_part = after_prefix.split("->", 1)
            output_path_str = output_part.strip()
            
            # Extract input path from "(input <path>)"
            input_path = None
            if "(input" in input_part:
                input_part_clean = input_part.split("(input", 1)[1].strip().rstrip(")")
                if input_part_clean:
                    input_path = Path(input_part_clean).resolve()
        else:
            # No "->" separator, treat entire line as output path
            output_path_str = after_prefix
            input_path = None
        
        if output_path_str:
            return Path(output_path_str).resolve(), input_path
    
    raise AssertionError("CLI output missing 'Step finished' line.")


def _ensure_clean_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True)


def test_cli_show_command_executes_against_references(
    ci_test_data_dir: Path,
    project_root_path: Path,
    qe_engine: QuantumEspressoEngine,
):
    runner = CliRunner()
    base_dir = project_root_path / "temp" / "test_outputs" / "cli_show_command_exec"
    _ensure_clean_directory(base_dir)

    project_root = base_dir / "project"
    result = runner.invoke(
        app,
        ["init", "project", "--path", str(project_root)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout

    pseudo_src = project_root_path / "resources" / "pseudo"
    if pseudo_src.exists():
        shutil.copytree(pseudo_src, project_root / "pseudo", dirs_exist_ok=True)

    pw_dir = ci_test_data_dir / "pw_single_tests"
    cases = load_test_cases(pw_dir, ci_root=ci_test_data_dir)
    assert cases, "No pw_single_tests cases discovered."

    runs_root = base_dir / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    for case in cases:
        input_path = case.input_path
        structure_name = f"struct_{input_path.stem}"
        calculation_name = f"wf_{input_path.stem}"

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
            catch_exceptions=False,
        )
        assert (
            result.exit_code == 0
        ), f"import-structure failed for {input_path.name}: {result.stdout}"

        result = runner.invoke(
            app,
            [
                "init",
                "calculation",
                calculation_name,
                "--structure",
                structure_name,
                "--project",
                str(project_root),
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, f"init calculation failed: {result.stdout}"

        show_output = runner.invoke(
            app, ["show-command", str(input_path)], catch_exceptions=False
        )
        assert show_output.exit_code == 0, show_output.stdout

        init_line = next(
            line.strip()
            for line in show_output.stdout.splitlines()
            if line.strip().startswith("qv init step")
        )
        init_args = shlex.split(init_line)[1:]
        # Now show-command doesn't include --structure, so we add it explicitly
        # along with --calculation and --project
        init_args.extend([
            "--structure", structure_name,
            "--calculation", calculation_name,
            "--project", str(project_root)
        ])
        init_result = runner.invoke(app, init_args, catch_exceptions=False)
        assert init_result.exit_code == 0, init_result.stdout

        calculation_slug = slugify(calculation_name)
        calculation_dir = project_root / "calculations" / calculation_slug
        calculation_yaml = yaml.safe_load((calculation_dir / "calculation.yaml").read_text())
        last_step = calculation_yaml["steps"][-1]
        # With ID-only model, resolve step file via step_id
        from quantumvitas.core.resolution import resolve_step, build_resource_index
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        index = build_resource_index(project_root)
        step_id = last_step.get("step_id") or last_step.get("id")
        calculation_slug = calculation_dir.name
        step_resolved = resolve_step(project_root, calculation_slug, step_id, config=config, index=index)
        step_spec_path = step_resolved.absolute_path

        workdir = runs_root / input_path.stem
        _ensure_clean_directory(workdir)

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
            catch_exceptions=False,
        )
        assert run_result.exit_code == 0, run_result.stdout

        output_file, generated_input = _extract_paths(run_result.stdout)
        assert output_file.exists(), f"Output file missing: {output_file}"
        if generated_input is None:
            generated_input = step_spec_path

        if not case.reference_path:
            continue

        step_type = qe_engine.detect_step_type(input_path)
        step_result = StepResult(
            step_type=step_type,
            input_file=generated_input,
            output_file=output_file,
            success=True,
            return_code=0,
        )
        success, message = verify_step_result(
            step_result,
            reference_file=case.reference_path,
            category=pw_dir.name,
        )
        assert success, f"{input_path.name}: {message}"

