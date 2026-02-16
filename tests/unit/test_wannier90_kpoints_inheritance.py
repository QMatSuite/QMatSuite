"""
Regression tests for Wannier90 kpoints inheritance from nscf step.

Tests that:
1. .win kpoints match nscf kpoints order exactly
2. kpoints are canonicalized correctly (snap near 0/1)
3. Consistency checks work (mp_grid count vs kpoints count)
"""

import pytest
from pathlib import Path
import tempfile
import yaml
from pymatgen.core import Structure, Lattice

from quantumvitas.calculation.structure_steps import materialize_step_spec, StructureStepSpec
from quantumvitas.core.models import ResourceMeta
from quantumvitas.io.wannier90_input import Wannier90Input
from quantumvitas.calculation.wannier90_kpoints import (
    extract_kpoints_from_qe_input,
    canonicalize_kpoint,
    format_kpoint_for_w90,
    find_nscf_input_file,
    extract_kpoints_from_nscf_step,
    infer_mp_grid_from_kpoints,
)
from quantumvitas.io.parser.qe_parser import QEInputParser


@pytest.fixture
def diamond_nscf_input():
    """Reference diamond.nscf input file."""
    nscf_path = Path(__file__).parent.parent.parent / ".qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/examples/example05/diamond.nscf"
    if not nscf_path.exists():
        pytest.skip(f"Reference nscf file not found: {nscf_path}")
    return nscf_path


def test_extract_kpoints_from_nscf(diamond_nscf_input):
    """Test that kpoints are extracted correctly from nscf input."""
    kpoints = extract_kpoints_from_qe_input(diamond_nscf_input)
    
    assert kpoints is not None, "Failed to extract kpoints from nscf"
    assert len(kpoints) == 64, f"Expected 64 kpoints, got {len(kpoints)}"
    
    # Verify first kpoint
    assert kpoints[0] == [0.0, 0.0, 0.0], f"First kpoint should be [0, 0, 0], got {kpoints[0]}"
    
    # Verify second kpoint (critical: should be 0, 0.25, 0)
    assert kpoints[1] == [0.0, 0.25, 0.0], (
        f"Second kpoint should be [0, 0.25, 0] (y fastest), got {kpoints[1]}"
    )
    
    # Verify third kpoint
    assert kpoints[2] == [0.0, 0.5, 0.0], f"Third kpoint should be [0, 0.5, 0], got {kpoints[2]}"


def test_canonicalize_kpoint():
    """Test kpoint canonicalization (snap near 0 and 1)."""
    # Test near 0
    kpt = [1e-13, 0.25, 0.5]
    canonical = canonicalize_kpoint(kpt)
    assert canonical[0] == 0.0, f"Near-zero should snap to 0, got {canonical[0]}"
    
    # Test near 1
    kpt = [1.0 - 1e-13, 0.25, 0.5]
    canonical = canonicalize_kpoint(kpt)
    assert canonical[0] == 0.0, f"Near-1 should snap to 0, got {canonical[0]}"
    
    # Test near -1
    kpt = [-1.0 + 1e-13, 0.25, 0.5]
    canonical = canonicalize_kpoint(kpt)
    assert canonical[0] == 0.0, f"Near--1 should snap to 0, got {canonical[0]}"
    
    # Test normal value
    kpt = [0.25, 0.5, 0.75]
    canonical = canonicalize_kpoint(kpt)
    assert canonical == [0.25, 0.5, 0.75], f"Normal value should not change, got {canonical}"


def test_format_kpoint_for_w90():
    """Test kpoint formatting for Wannier90 .win file."""
    kpt = [0.0, 0.25, 0.5]
    formatted = format_kpoint_for_w90(kpt)
    
    # Should have 10 decimal places and proper spacing
    assert "0.0000000000" in formatted, "Should format with 10 decimal places"
    assert "0.2500000000" in formatted, "Should format 0.25 correctly"
    assert "0.5000000000" in formatted, "Should format 0.5 correctly"


def test_w90_kpoints_match_nscf_order(diamond_nscf_input, tmp_path):
    """
    Test that .win kpoints match nscf kpoints order exactly.
    
    This is the critical regression test: .win kpoints must be in the same order
    as nscf kpoints to avoid pw2wannier90 "k-point 2 is wrong" errors.
    """
    # Create a minimal calculation directory structure
    calc_dir = tmp_path / "test_calc"
    calc_dir.mkdir()
    steps_dir = calc_dir / "steps"
    steps_dir.mkdir()
    raw_dir = calc_dir / "raw"
    raw_dir.mkdir()
    
    # Copy nscf input to raw directory (simulating materialized step)
    import shutil
    nscf_in_raw = raw_dir / "nscf.in"
    shutil.copy(diamond_nscf_input, nscf_in_raw)
    
    # Create calculation.yaml with nscf step (SPEC representation)
    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text(yaml.dump({
        "meta": {"ulid": "01TEST", "name": "test", "slug": "test", "path": "test", "kind": "calculation"},
        "steps": [
            {"step_ulid": "01NSCF", "step_type_spec": "qe_nscf", "input": "nscf.in"}
        ]
    }))
    
    # Extract kpoints from nscf
    nscf_kpoints = extract_kpoints_from_qe_input(nscf_in_raw)
    assert nscf_kpoints is not None and len(nscf_kpoints) > 0
    
    # Create diamond structure
    lattice_matrix = [
        [-1.613990, 0.000000, 1.613990],
        [0.000000, 1.613990, 1.613990],
        [-1.613990, 1.613990, 0.000000]
    ]
    lattice = Lattice(lattice_matrix)
    structure = Structure(
        lattice,
        ["C", "C"],
        [[-0.125, -0.125, -0.125], [0.125, 0.125, 0.125]],
        coords_are_cartesian=False
    )
    
    # Save structure
    structures_dir = tmp_path / "structures"
    structures_dir.mkdir()
    structure_file = structures_dir / "diamond.json"
    structure.to(fmt="json", filename=str(structure_file))
    
    # Create wannierprep step spec
    spec = StructureStepSpec(
        meta=ResourceMeta(ulid="01W90",
            name="wannierprep",
            slug="wannierprep",
            path="steps/wannierprep.step.yaml",
            kind="step"
        ),
        step_type_spec="w90_wannierprep",
        structure_ulid=None,
        structure=str(structure_file),
        parameters={
            "seedname": "diamond",
            "num_wann": 4,
            "num_iter": 20,
            "mp_grid": [4, 4, 4],
        }
    )
    
    # Generate .win file
    output_path, _ = materialize_step_spec(
        spec,
        output_dir=raw_dir,
        project_root=tmp_path,
        calculation_dir=calc_dir,
        input_name="diamond.win"
    )
    
    # Parse generated .win file
    win = Wannier90Input.from_file(output_path)
    
    # Verify kpoints match nscf (exact order)
    assert win.kpoints is not None and len(win.kpoints) > 0, "No kpoints in generated .win"
    assert len(win.kpoints) == len(nscf_kpoints), (
        f"Kpoints count mismatch: .win has {len(win.kpoints)}, nscf has {len(nscf_kpoints)}"
    )
    
    # Verify first 8 kpoints match exactly (order is critical)
    for i in range(min(8, len(win.kpoints))):
        win_kpt = win.kpoints[i]
        nscf_kpt = nscf_kpoints[i]
        
        # Allow small floating point differences
        for j in range(3):
            diff = abs(win_kpt[j] - nscf_kpt[j])
            assert diff < 1e-10, (
                f"Kpoint {i+1} mismatch at coordinate {j}: "
                f".win={win_kpt}, nscf={nscf_kpt}, diff={diff}"
            )
    
    # Critical: verify second kpoint is [0, 0.25, 0] (not generated order)
    assert win.kpoints[1] == [0.0, 0.25, 0.0], (
        f"Second kpoint must be [0, 0.25, 0] (nscf order), got {win.kpoints[1]}. "
        f"This indicates order mismatch with nscf."
    )


@pytest.mark.parametrize(
    "step_entry",
    [
        {"step_ulid": "01NSCF", "step_type_gen": "nscf", "input": "nscf.in"},
        {"step_ulid": "01NSCF", "step_type_spec": "qe_nscf", "input": "nscf.in"},
    ],
)
def test_find_nscf_input_file(tmp_path, step_entry):
    """Test finding nscf input file for both GEN and SPEC step schemas."""
    calc_dir = tmp_path / "calc"
    calc_dir.mkdir()
    raw_dir = calc_dir / "raw"
    raw_dir.mkdir()
    
    # Create calculation.yaml
    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text(yaml.dump({
        "meta": {"ulid": "01TEST", "name": "test", "slug": "test", "path": "test", "kind": "calculation"},
        "steps": [step_entry]
    }))
    
    # Create nscf.in in raw directory
    nscf_file = raw_dir / "nscf.in"
    nscf_file.write_text("&CONTROL\ncalculation = 'nscf'\n/\n")
    
    # Test finding it
    found = find_nscf_input_file(calc_dir, working_dir=raw_dir)
    assert found == nscf_file, f"Should find nscf.in in raw_dir, got {found}"


def test_extract_kpoints_from_nscf_step(tmp_path):
    """Test extracting kpoints from nscf step in calculation."""
    calc_dir = tmp_path / "calc"
    calc_dir.mkdir()
    raw_dir = calc_dir / "raw"
    raw_dir.mkdir()
    
    # Create calculation.yaml (SPEC representation)
    calc_yaml = calc_dir / "calculation.yaml"
    calc_yaml.write_text(yaml.dump({
        "meta": {"ulid": "01TEST", "name": "test", "slug": "test", "path": "test", "kind": "calculation"},
        "steps": [
            {"step_ulid": "01NSCF", "step_type_spec": "qe_nscf", "input": "nscf.in"}
        ]
    }))
    
    # Create minimal nscf.in with kpoints
    nscf_file = raw_dir / "nscf.in"
    nscf_content = """&CONTROL
calculation = 'nscf'
/
&SYSTEM
ibrav = 0
nat = 2
ntyp = 1
/
K_POINTS {crystal}
4
0.0 0.0 0.0 0.25
0.0 0.25 0.0 0.25
0.0 0.5 0.0 0.25
0.25 0.0 0.0 0.25
"""
    nscf_file.write_text(nscf_content)
    
    # Extract kpoints
    kpoints = extract_kpoints_from_nscf_step(calc_dir, working_dir=raw_dir)
    
    assert kpoints is not None, "Should extract kpoints from nscf step"
    assert len(kpoints) == 4, f"Expected 4 kpoints, got {len(kpoints)}"
    assert kpoints[0] == [0.0, 0.0, 0.0], "First kpoint should be [0, 0, 0]"
    assert kpoints[1] == [0.0, 0.25, 0.0], "Second kpoint should be [0, 0.25, 0] (order preserved)"


def test_infer_mp_grid_from_kpoints():
    """Infer a regular Monkhorst-Pack grid from explicit kpoints."""
    kpoints = [
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 0.5],
        [0.0, 0.5, 0.0],
        [0.0, 0.5, 0.5],
        [0.5, 0.0, 0.0],
        [0.5, 0.0, 0.5],
        [0.5, 0.5, 0.0],
        [0.5, 0.5, 0.5],
    ]
    inferred = infer_mp_grid_from_kpoints(kpoints)
    assert inferred == [2, 2, 2], inferred


def test_infer_mp_grid_from_kpoints_irregular_returns_none():
    """Non-rectangular kpoint sets should not produce an inferred grid."""
    kpoints = [
        [0.0, 0.0, 0.0],
        [0.2, 0.0, 0.0],
        [0.4, 0.1, 0.0],
    ]
    inferred = infer_mp_grid_from_kpoints(kpoints)
    assert inferred is None, inferred
