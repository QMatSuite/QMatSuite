from pathlib import Path

import pytest

from quantumvitas.core.engines.base import EngineConfig
from quantumvitas.core.engines.qe import QuantumEspressoEngine
# Using ensure_qe_pseudos directly (canonical entry point)
from quantumvitas.calculation import (
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
    ci_test_data = project_root / "tests" / "data"
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
            from quantumvitas.core.pseudo import ensure_qe_pseudos, get_system_pseudo_dir
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
                        "test": f"{category}/{test_name}",
                        "success": False,
                        "error": "Failed to obtain required pseudopotentials",
                    }
                )
                continue

            # Run the step in sandbox_dir (not raw_dir)
            # run_step will set ESPRESSO_PSEUDO to sandbox_dir/pseudo (standalone mode)
            step_type = qe_engine.detect_step_type(sandbox_input)
            step_result = qe_engine.run_step(
                input_file=sandbox_input,
                working_dir=sandbox_dir,
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

