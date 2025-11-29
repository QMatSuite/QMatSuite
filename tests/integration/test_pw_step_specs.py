from pathlib import Path

import pytest

from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.qe_pseudopotentials import ensure_pseudopotentials
from quantumvitas.workflow import (
    build_step_spec_from_qe_input,
    materialize_step_spec,
)
from tests.core.qe_step_verification import verify_step_result
from tests.core.qe_step_runner import get_default_working_dir
from tests.core.test_data import load_test_cases


pytestmark = pytest.mark.quick


@pytest.fixture(scope="module")
def qe_engine() -> QuantumEspressoEngine:
    config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    if not engine.detect_executable("pw.x"):
        raise RuntimeError("pw.x not found. QE installation required for PW spec integration tests.")
    return engine


@pytest.fixture(scope="module")
def ci_test_data_dir() -> Path:
    project_root = Path(__file__).parent.parent.parent
    ci_test_data = project_root / "tests" / "integration" / "ci_test_data"
    if not ci_test_data.exists():
        pytest.skip(f"CI test data not found: {ci_test_data}")
    return ci_test_data


@pytest.fixture(scope="module")
def pw_test_cases(ci_test_data_dir: Path):
    folder = ci_test_data_dir / "pw_single_tests"
    if not folder.exists():
        pytest.skip(f"PW test folder not found: {folder}")
    return load_test_cases(folder, ci_root=ci_test_data_dir)


class TestPWStepSpecsExecution:
    def test_pw_specs_generate_and_run(
        self,
        qe_engine: QuantumEspressoEngine,
        pw_test_cases,
        ci_test_data_dir: Path,
    ):
        """
        Convert each PW QE input into a step spec, materialize it, then run QE.
        Automatically compares with benchmark reference files from ci_test_data if available.
        """

        project_root = Path(__file__).parent.parent.parent
        results = []

        pw_folder = ci_test_data_dir / "pw_single_tests"
        for case in pw_test_cases:
            input_file = case.input_path
            category = pw_folder.name
            test_name = input_file.name
            slug = input_file.stem

            working_dir = get_default_working_dir(
                project_root,
                f"{category}_step_specs",
                slug,
            )
            steps_dir = working_dir / "steps"
            structures_dir = working_dir / "structures"
            raw_dir = working_dir / "raw"

            steps_dir.mkdir(parents=True, exist_ok=True)
            structures_dir.mkdir(parents=True, exist_ok=True)

            step_result = build_step_spec_from_qe_input(
                input_file,
                destination_dir=steps_dir,
                structure_dir=structures_dir,
                reference_structure_by="path",
            )

            generated_input, spec = materialize_step_spec(
                step_result.spec_path,
                output_dir=raw_dir,
                workflow_dir=working_dir,
                project_root=project_root,  # This sets outdir and pseudo_dir during generation
            )

            # Ensure pseudopotentials are available
            unified_pseudo_dir = project_root / "pseudo"
            unified_pseudo_dir.mkdir(parents=True, exist_ok=True)
            if not ensure_pseudopotentials(generated_input, raw_dir, unified_pseudo_dir, None):
                results.append(
                    {
                        "test": f"{category}/{test_name}",
                        "success": False,
                        "error": "Failed to obtain required pseudopotentials",
                    }
                )
                continue

            # Prepare the working directory (outdir is already set in the generated input)
            (raw_dir / "outdir").mkdir(parents=True, exist_ok=True)

            # Run the step directly on the generated input (no re-parsing)
            step_type = qe_engine.detect_step_type(generated_input)
            step_result = qe_engine.run_step(
                input_file=generated_input,
                working_dir=raw_dir,
                step_type=step_type,
                timeout=300,
            )

            # Find benchmark reference file if available
            # Pattern: pw_single_tests/benchmark.out.git.inp={test_file}
            reference_file = case.reference_path

            # Verify the result
            success, message = verify_step_result(
                step_result=step_result,
                reference_file=reference_file,
                category=category,
                tolerance=0.15,  # Set energy threshold to 0.15 Ry for ibrav conversion differences
            )

            if success:
                results.append({"test": f"{category}/{test_name}", "success": True})
            else:
                results.append(
                    {
                        "test": f"{category}/{test_name}",
                        "success": False,
                        "error": message,
                    }
                )

        failures = [r for r in results if not r["success"]]
        if failures:
            failure_messages = "\n".join(
                f"{f['test']}: {f.get('error', 'unknown error')}" for f in failures
            )
            pytest.fail(f"PW step spec execution failures:\n{failure_messages}")

