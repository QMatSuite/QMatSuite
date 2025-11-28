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
def pw_tests_from_manifest(ci_test_data_dir: Path):
    manifest_file = ci_test_data_dir / "manifest.json"
    if not manifest_file.exists():
        pytest.skip(f"manifest.json not found: {manifest_file}")

    with open(manifest_file) as f:
        manifest = json.load(f)

    pw_tests = []
    for test in manifest.get("tests", []):
        category = test.get("category", "")
        if not category.startswith("pw_"):
            continue
        rel_input = test.get("input_file", "")
        input_file = ci_test_data_dir / rel_input
        if input_file.exists():
            pw_tests.append(
                {
                    "category": category,
                    "test_file": test.get("test_file"),
                    "input_file": input_file,
                }
            )

    if not pw_tests:
        pytest.skip("No PW tests found in manifest.json")

    return pw_tests


class TestPWStepSpecsExecution:
    def test_pw_specs_generate_and_run(
        self,
        qe_engine: QuantumEspressoEngine,
        pw_tests_from_manifest,
        ci_test_data_dir: Path,
    ):
        """
        Convert each PW QE input into a step spec, materialize it, then run QE.
        Automatically compares with benchmark reference files from ci_test_data if available.
        """

        project_root = Path(__file__).parent.parent.parent
        results = []

        for test_info in pw_tests_from_manifest:
            input_file = test_info["input_file"]
            category = test_info["category"]
            test_name = test_info["test_file"]
            slug = test_name.replace("/", "_").replace(".in", "")

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
            benchmark_file = ci_test_data_dir / "pw_single_tests" / f"benchmark.out.git.inp={test_name}"
            reference_file = benchmark_file if benchmark_file.exists() else None

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

