"""
Unit tests for Wannier90 step materialization.

These tests verify that Wannier90 steps (w90_preproc, w90_run, pw2wannier90)
are materialized correctly using Wannier90 input generation, NOT QE input generation.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from quantumvitas.calculation.structure_steps import materialize_step_spec, StructureStepSpec
from quantumvitas.core.resources import ResourceMeta
from pymatgen.core import Structure, Lattice


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    tmpdir = tempfile.mkdtemp()
    yield Path(tmpdir)
    shutil.rmtree(tmpdir)


@pytest.fixture
def simple_structure():
    """Create a simple structure for testing."""
    lattice = Lattice.cubic(5.0)
    structure = Structure(lattice, ["Si"], [[0, 0, 0]])
    return structure


def test_w90_preproc_does_not_use_qe_validation(temp_dir, simple_structure):
    """
    Test that w90_preproc step materialization does NOT invoke QE pw schema validation.
    
    This is the core fix: w90_preproc parameters (seedname, num_wann, projections)
    should NOT be validated against QE 'pw' module schema.
    """
    # Create step spec with Wannier90 parameters
    meta = ResourceMeta(
        id="01TEST",
        name="w90_preproc",
        slug="w90_preproc",
        path="steps/w90_preproc.step.yaml",
        kind="step",
    )
    
    spec = StructureStepSpec(
        meta=meta,
        structure="structure.json",  # Not used for Wannier90, but required
        step_type="w90_preproc",
        parameters={
            "seedname": "diamond",
            "num_wann": 4,
            "num_bands": 8,
            "mp_grid": [4, 4, 4],
            "projections": "Si:sp3",
        },
    )
    
    # Create a minimal project structure for structure resolution
    # Write structure file
    structures_dir = temp_dir / "structures"
    structures_dir.mkdir(parents=True)
    structure_file = structures_dir / "structure.json"
    simple_structure.to(fmt="json", filename=str(structure_file))
    
    # Update spec to use absolute path
    spec.structure = str(structure_file)
    
    # Materialize step - should NOT raise "seedname not defined for pw" error
    try:
        generated_input, spec_obj = materialize_step_spec(
            spec=spec,
            output_dir=temp_dir / "raw",
            project_root=temp_dir,
        )
        
        # Should succeed without QE validation errors
        assert generated_input.exists()
        assert generated_input.suffix == ".win" or generated_input.name.endswith(".win")
        
        # Verify it's a valid .win file
        content = generated_input.read_text()
        assert "seedname" not in content.lower()  # seedname is not in .win format (used as filename)
        assert "num_wann" in content
        assert "num_bands" in content
        assert "diamond" in generated_input.name  # seedname used in filename
        
    except ValueError as e:
        if "not defined for module 'pw'" in str(e):
            pytest.fail(f"w90_preproc incorrectly validated against QE pw schema: {e}")
        raise


def test_w90_preproc_generates_win_file(temp_dir, simple_structure):
    """Test that w90_preproc generates a proper .win file."""
    meta = ResourceMeta(
        id="01TEST",
        name="w90_preproc",
        slug="w90_preproc",
        path="steps/w90_preproc.step.yaml",
        kind="step",
    )
    
    spec = StructureStepSpec(
        meta=meta,
        structure="structure.json",
        step_type="w90_preproc",
        parameters={
            "seedname": "test",
            "num_wann": 4,
            "num_bands": 8,
            "mp_grid": [2, 2, 2],
        },
    )
    
    structures_dir = temp_dir / "structures"
    structures_dir.mkdir(parents=True)
    structure_file = structures_dir / "structure.json"
    simple_structure.to(fmt="json", filename=str(structure_file))
    spec.structure = str(structure_file)
    
    generated_input, _ = materialize_step_spec(
        spec=spec,
        output_dir=temp_dir / "raw",
        project_root=temp_dir,
    )
    
    # Check file exists and has correct extension
    assert generated_input.exists()
    assert generated_input.name == "test.win" or generated_input.name.endswith(".win")
    
    # Check content
    content = generated_input.read_text()
    assert "num_wann        = 4" in content
    assert "num_bands       = 8" in content
    assert "mp_grid" in content or "2 2 2" in content
    # Should have unit cell and atoms from structure
    assert "unit_cell_cart" in content.lower() or "begin unit_cell_cart" in content.lower()
    assert "atoms_frac" in content.lower() or "begin atoms_frac" in content.lower()


def test_pw2wannier90_generates_pw2wan_file(temp_dir, simple_structure):
    """Test that pw2wannier90 generates a proper .pw2wan file."""
    meta = ResourceMeta(
        id="01TEST",
        name="pw2wannier90",
        slug="pw2wannier90",
        path="steps/pw2wannier90.step.yaml",
        kind="step",
    )
    
    # Create a minimal structure file for pw2wannier90 (even if not strictly needed)
    structures_dir = temp_dir / "structures"
    structures_dir.mkdir(parents=True)
    structure_file = structures_dir / "structure.json"
    simple_structure.to(fmt="json", filename=str(structure_file))
    
    spec = StructureStepSpec(
        meta=meta,
        structure=str(structure_file),  # Use absolute path
        step_type="pw2wannier90",
        parameters={
            "seedname": "test",
            "prefix": "pwscf",
            "outdir": "./outdir",
        },
    )
    
    generated_input, _ = materialize_step_spec(
        spec=spec,
        output_dir=temp_dir / "raw",
        project_root=temp_dir,
    )
    
    # Check file exists and has correct extension
    assert generated_input.exists()
    assert generated_input.name == "test.pw2wan" or generated_input.name.endswith(".pw2wan")
    
    # Check content
    content = generated_input.read_text()
    assert "&inputpp" in content
    assert "seedname" in content
    assert "prefix" in content
    assert "outdir" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

