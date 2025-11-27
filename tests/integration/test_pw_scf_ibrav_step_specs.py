import json
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


pytestmark = pytest.mark.quick


@pytest.fixture(scope="module")
def qe_engine() -> QuantumEspressoEngine:
    config = EngineConfig(name="qe")
    engine = QuantumEspressoEngine(config)
    if not engine.detect_executable("pw.x"):
        raise RuntimeError("pw.x not found. QE installation required for integration tests.")
    return engine


@pytest.fixture(scope="module")
def ci_test_data_dir() -> Path:
    project_root = Path(__file__).parent.parent.parent
    ci_test_data = project_root / "tests" / "integration" / "ci_test_data"
    if not ci_test_data.exists():
        pytest.skip(f"CI test data not found: {ci_test_data}")
    return ci_test_data


@pytest.fixture(scope="module")
def pw_scf_ibrav_tests(ci_test_data_dir: Path):
    """Get all SCF ibrav test files from pw_scf_ibrav directory."""
    pw_scf_ibrav_dir = ci_test_data_dir / "pw_scf_ibrav"
    if not pw_scf_ibrav_dir.exists():
        pytest.skip(f"pw_scf_ibrav directory not found: {pw_scf_ibrav_dir}")
    
    # Find all .in files (excluding benchmark files)
    input_files = [
        f for f in pw_scf_ibrav_dir.glob("*.in")
        if "benchmark" not in f.name.lower()
    ]
    
    if not input_files:
        pytest.skip("No SCF ibrav test files found in pw_scf_ibrav directory")
    
    # Create test info list
    pw_tests = []
    for input_file in sorted(input_files):
        pw_tests.append(
            {
                "test_file": input_file.name,
                "input_file": input_file,
            }
        )
    
    return pw_tests


class TestPWScfIbravStepSpecsExecution:
    def test_pw_scf_ibrav_specs_generate_and_run(
        self,
        qe_engine: QuantumEspressoEngine,
        pw_scf_ibrav_tests,
        ci_test_data_dir: Path,
    ):
        """
        Convert each PW SCF ibrav QE input into a step spec, materialize it, then run QE.
        Automatically compares with benchmark reference files from pw_scf_ibrav directory.
        """
        project_root = Path(__file__).parent.parent.parent
        results = []
        pw_scf_ibrav_dir = ci_test_data_dir / "pw_scf_ibrav"

        for test_info in pw_scf_ibrav_tests:
            input_file = test_info["input_file"]
            test_name = test_info["test_file"]
            slug = test_name.replace("/", "_").replace(".in", "")

            working_dir = get_default_working_dir(
                project_root,
                "pw_scf_ibrav_step_specs",
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
                        "test": test_name,
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
            # Pattern: pw_scf_ibrav/benchmark.out.git.inp={test_file}
            benchmark_file = pw_scf_ibrav_dir / f"benchmark.out.git.inp={test_name}"
            reference_file = benchmark_file if benchmark_file.exists() else None

            # Verify the result
            success, message = verify_step_result(
                step_result=step_result,
                reference_file=reference_file,
                category="pw_scf_ibrav",
                # Use project-wide energy threshold (no custom tolerance)
            )

            if success:
                results.append({"test": test_name, "success": True})
            else:
                results.append(
                    {
                        "test": test_name,
                        "success": False,
                        "error": message,
                    }
                )

        failures = [r for r in results if not r["success"]]
        if failures:
            failure_messages = "\n".join(
                f"{f['test']}: {f.get('error', 'unknown error')}" for f in failures
            )
            pytest.fail(f"PW SCF ibrav step spec execution failures:\n{failure_messages}")

