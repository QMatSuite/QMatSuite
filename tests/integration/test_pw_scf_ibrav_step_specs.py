import json
from pathlib import Path

import pytest

from qmatsuite.core.engines.base import EngineConfig
from qmatsuite.core.engines.qe import QuantumEspressoEngine
# Using ensure_qe_pseudos directly (canonical entry point)
from qmatsuite.calculation import (
    build_step_spec_from_qe_input,
    materialize_step_spec,
)
from tests.core.qe_step_verification import verify_step_result
from tests.core.qe_step_runner import get_default_working_dir


pytestmark = pytest.mark.quick


@pytest.fixture(scope="module")
def qe_engine() -> QuantumEspressoEngine:
    config = EngineConfig(name="qe")
    try:
        engine = QuantumEspressoEngine(config)
        if not engine.detect_executable("pw.x"):
            raise RuntimeError("pw.x not found. QE installation required for integration tests.")
        return engine
    except RuntimeError as e:
        # Re-raise with clear message about missing QE
        raise RuntimeError(
            f"QE engine initialization failed: {e}\n"
            "Install internal QE to .qmatsuite/engines/qe/<folder>/bin or set settings.qe.bin_dir to external QE bin directory."
        ) from e


@pytest.fixture(scope="module")
def ci_test_data_dir() -> Path:
    project_root = Path(__file__).parent.parent.parent
    ci_test_data = project_root / "tests" / "data"
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
            # fixture_dir: read-only template directory for materialized step specs
            # This is NOT the same as product "project/calc/raw" (which is a writable runtime directory)
            fixture_dir = working_dir / "raw"

            steps_dir.mkdir(parents=True, exist_ok=True)
            structures_dir.mkdir(parents=True, exist_ok=True)

            step_result = build_step_spec_from_qe_input(
                input_file,
                destination_dir=steps_dir,
                structure_dir=structures_dir,
                reference_structure_by="path",
            )

            # Materialize step spec to fixture_dir (read-only template/fixture directory)
            # fixture_dir is used only as source of input templates, not for execution
            # In product code, this would be calculation.raw_dir (a writable runtime directory)
            generated_input, spec = materialize_step_spec(
                step_result.spec_path,
                output_dir=fixture_dir,
                calculation_dir=working_dir,
                project_root=None,  # Standalone mode
            )

            # Create sandbox working directory for execution (separate from fixture_dir)
            # This ensures fixture_dir stays read-only and execution happens in sandbox
            from tests.core.qe_step_runner import create_sandbox_working_dir
            import shutil
            sandbox_dir = create_sandbox_working_dir(working_dir, prefix=f"{slug}_run_")
            
            # Copy generated input from fixture_dir (template) to sandbox_dir (execution)
            sandbox_input = sandbox_dir / generated_input.name
            shutil.copy2(generated_input, sandbox_input)
            
            # Materialize pseudopotentials to sandbox_dir/pseudo (standalone mode)
            # run_step will set ESPRESSO_PSEUDO to sandbox_dir/pseudo
            sandbox_pseudo_dir = sandbox_dir / "pseudo"
            sandbox_pseudo_dir.mkdir(parents=True, exist_ok=True)
            from qmatsuite.core.pseudo import ensure_qe_pseudos, get_system_pseudo_dir
            result = ensure_qe_pseudos(
                qe_input_file=sandbox_input,
                project_pseudo_dir=sandbox_pseudo_dir,
                system_pseudo_dir=get_system_pseudo_dir(),
                strict=False,
                additional_search_dirs=None,
            )
            if not result.all_available:
                results.append(
                    {
                        "test": test_name,
                        "success": False,
                        "error": "Failed to obtain required pseudopotentials",
                    }
                )
                continue

            # Run the step in sandbox_dir (not raw_dir)
            # run_step will set ESPRESSO_PSEUDO to sandbox_dir/pseudo (standalone mode)
            step_type_gen = qe_engine.detect_step_type(sandbox_input)  # Returns GEN type (e.g., "scf")
            # Convert GEN to SPEC for execution layer
            from qmatsuite.workflow.step_type_convert import spec_from
            step_type_spec = spec_from("qe", step_type_gen)  # Convert to SPEC (e.g., "qe_scf")
            step_result = qe_engine.run_step(
                input_file=sandbox_input,
                working_dir=sandbox_dir,
                step_type_spec=step_type_spec,  # Execution layer uses SPEC type
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

