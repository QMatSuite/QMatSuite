from pathlib import Path

import pytest

from quantumvitas.workflow.geometry import (
    read_geometry_from_input,
    read_geometry_from_output,
    compare_geometries,
)
from quantumvitas.workflow import build_step_spec_from_qe_input, materialize_step_spec


pytestmark = pytest.mark.quick


@pytest.fixture(scope="module")
def ci_test_data_dir() -> Path:
    project_root = Path(__file__).parent.parent.parent
    ci_test_data = project_root / "tests" / "integration" / "ci_test_data"
    if not ci_test_data.exists():
        pytest.skip(f"CI test data not found: {ci_test_data}")
    return ci_test_data


def test_pw_scf_ibrav_geometry_roundtrip(ci_test_data_dir: Path, tmp_path: Path):
    """
    Validate that materialized inputs preserve the lattice geometry
    described in the reference QE outputs.
    """
    pw_scf_ibrav_dir = ci_test_data_dir / "pw_scf_ibrav"
    if not pw_scf_ibrav_dir.exists():
        pytest.skip(f"pw_scf_ibrav directory not found: {pw_scf_ibrav_dir}")

    project_root = Path(__file__).parent.parent.parent
    inputs = sorted(
        f for f in pw_scf_ibrav_dir.glob("*.in") if "benchmark" not in f.name
    )
    assert inputs, "No input files found in pw_scf_ibrav"

    failures = []
    for input_file in inputs:
        slug = input_file.stem
        working_dir = tmp_path / slug
        steps_dir = working_dir / "steps"
        structures_dir = working_dir / "structures"
        raw_dir = working_dir / "raw"
        steps_dir.mkdir(parents=True, exist_ok=True)
        structures_dir.mkdir(parents=True, exist_ok=True)

        step_spec = build_step_spec_from_qe_input(
            input_file,
            destination_dir=steps_dir,
            structure_dir=structures_dir,
            reference_structure_by="path",
        )

        generated_input, _ = materialize_step_spec(
            step_spec.spec_path,
            output_dir=raw_dir,
            workflow_dir=working_dir,
            project_root=project_root,
        )

        generated_geometry = read_geometry_from_input(generated_input)
        reference_file = (
            pw_scf_ibrav_dir / f"benchmark.out.git.inp={input_file.name}"
        )
        assert reference_file.exists(), f"Reference file missing: {reference_file}"
        reference_geometry = read_geometry_from_output(reference_file)

        success, message = compare_geometries(
            generated_geometry,
            reference_geometry,
            cell_atol=1e-5,
            position_atol=1e-4,
        )
        if not success:
            failures.append(f"{input_file.name}: {message}")

    if failures:
        pytest.fail("Geometry mismatches:\n" + "\n".join(failures))

