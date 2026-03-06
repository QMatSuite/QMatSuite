"""
Unit tests for Wannier90 step materialization.

These tests verify that Wannier90 steps (wannierprep, wannier, pw2wannier)
are materialized correctly using Wannier90 input generation, NOT QE input generation.
"""

import pytest
import tempfile
import shutil
from pathlib import Path

from qmatsuite.calculation.structure_steps import materialize_step_spec, StructureStepSpec
from qmatsuite.core.resources import ResourceMeta
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
    Test that wannierprep step materialization does NOT invoke QE pw schema validation.
    
    This is the core fix: wannierprep parameters (seedname, num_wann, projections)
    should NOT be validated against QE 'pw' module schema.
    """
    # Create step spec with Wannier90 parameters
    meta = ResourceMeta(ulid="01TEST",
        name="wannierprep",
        slug="wannierprep",
        path="steps/wannierprep.step.yaml",
        kind="step",
    )
    
    spec = StructureStepSpec(
        meta=meta,
        structure="structure.json",  # Not used for Wannier90, but required
        step_type_spec="w90_wannierprep",
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
            pytest.fail(f"wannierprep incorrectly validated against QE pw schema: {e}")
        raise


def test_wannierprep_generates_win_file(temp_dir, simple_structure):
    """Test that wannierprep generates a proper .win file."""
    meta = ResourceMeta(ulid="01TEST",
        name="wannierprep",
        slug="wannierprep",
        path="steps/wannierprep.step.yaml",
        kind="step",
    )
    
    spec = StructureStepSpec(
        meta=meta,
        structure="structure.json",
        step_type_spec="w90_wannierprep",
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
    meta = ResourceMeta(ulid="01TEST",
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
        step_type_spec="qe_pw2wannier",
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
    # E2: pw2wannier90 input file should be pw2wan.in (not test.pw2wan)
    assert generated_input.exists()
    assert generated_input.name == "pw2wan.in", f"Expected pw2wan.in, got {generated_input.name}"
    
    # Check content
    content = generated_input.read_text()
    assert "&inputpp" in content
    assert "seedname" in content
    # E1: prefix/outdir are injected at execution, may or may not be in generated input
    # But seedname must be present (controls output file names)
    assert "test" in content, "seedname should be in pw2wan input content"


def test_wannier90_win_passthrough_parameters(temp_dir, simple_structure):
    """Unknown W90 keys should be transparently passed through to .win."""
    meta = ResourceMeta(ulid="01TEST",
        name="wannier",
        slug="wannier",
        path="steps/wannier.step.yaml",
        kind="step",
    )

    structures_dir = temp_dir / "structures"
    structures_dir.mkdir(parents=True)
    structure_file = structures_dir / "structure.json"
    simple_structure.to(fmt="json", filename=str(structure_file))

    spec = StructureStepSpec(
        meta=meta,
        structure=str(structure_file),
        step_type_spec="w90_wannier",
        parameters={
            "parameters": {
                "seedname": "si_soc",
                "num_wann": 4,
                "spinors": True,
                "auto_projections": True,
                "berry": True,
                "berry_task": "'ahc'",
                "fermi_energy": 12.5,
            }
        },
    )

    generated_input, _ = materialize_step_spec(
        spec=spec,
        output_dir=temp_dir / "raw",
        project_root=temp_dir,
    )

    content = generated_input.read_text()
    assert "spinors = .true." in content
    assert "auto_projections = .true." in content
    assert "berry = .true." in content
    assert "berry_task = 'ahc'" in content
    assert "fermi_energy = 12.5" in content


def test_pw2wannier90_passthrough_inputpp_parameters(temp_dir, simple_structure):
    """Unknown INPUTPP keys should be transparently passed through to pw2wan.in."""
    meta = ResourceMeta(ulid="01TEST",
        name="pw2wannier90",
        slug="pw2wannier90",
        path="steps/pw2wannier90.step.yaml",
        kind="step",
    )

    structures_dir = temp_dir / "structures"
    structures_dir.mkdir(parents=True)
    structure_file = structures_dir / "structure.json"
    simple_structure.to(fmt="json", filename=str(structure_file))

    spec = StructureStepSpec(
        meta=meta,
        structure=str(structure_file),
        step_type_spec="qe_pw2wannier",
        parameters={
            "parameters": {
                "seedname": "fe_soc",
                "write_unk": True,
                "scdm_proj": True,
                "scdm_entanglement": "'isolated'",
            }
        },
    )

    generated_input, _ = materialize_step_spec(
        spec=spec,
        output_dir=temp_dir / "raw",
        project_root=temp_dir,
    )

    content = generated_input.read_text()
    assert "write_unk = .true." in content
    assert "scdm_proj = .true." in content
    assert "scdm_entanglement = 'isolated'" in content


def test_postwannier_reuses_existing_seed_win(temp_dir, simple_structure):
    """postwannier should reuse existing seedname .win and overlay new parameters."""
    raw_dir = temp_dir / "raw"
    raw_dir.mkdir(parents=True)
    existing = raw_dir / "fe.win"
    existing.write_text("num_wann        = 18\nnum_iter        = 200\n")

    meta = ResourceMeta(ulid="01TEST",
        name="postwannier",
        slug="postwannier",
        path="steps/postwannier.step.yaml",
        kind="step",
    )

    structures_dir = temp_dir / "structures"
    structures_dir.mkdir(parents=True)
    structure_file = structures_dir / "structure.json"
    simple_structure.to(fmt="json", filename=str(structure_file))

    spec = StructureStepSpec(
        meta=meta,
        structure=str(structure_file),
        step_type_spec="w90_postwannier",
        parameters={
            "parameters": {
                "berry": True,
                "berry_task": "'ahc'",
            }
        },
    )

    generated_input, _ = materialize_step_spec(
        spec=spec,
        output_dir=raw_dir,
        project_root=temp_dir,
    )

    assert generated_input.name == "fe.win"
    content = generated_input.read_text()
    assert "num_wann        = 18" in content
    assert "num_iter        = 200" in content  # must survive postwannier overlay
    assert "berry = .true." in content
    assert "berry_task = 'ahc'" in content


def test_postwannier_preserves_num_iter_from_wannier(temp_dir, simple_structure):
    """postwannier must NOT overwrite num_iter in shared .win file.

    The wannier step writes num_iter (e.g. 200) for spread minimisation.
    postwannier shares the same .win and may have num_iter=0 in its
    parameters (postw90.x doesn't need iterations).  The materialiser
    must preserve the wannier step's value.
    """
    raw_dir = temp_dir / "raw"
    raw_dir.mkdir(parents=True)

    # Simulate .win written by the wannier step
    existing = raw_dir / "fe.win"
    existing.write_text("num_wann        = 18\nnum_iter        = 200\n")

    structures_dir = temp_dir / "structures"
    structures_dir.mkdir(parents=True)
    structure_file = structures_dir / "structure.json"
    simple_structure.to(fmt="json", filename=str(structure_file))

    meta = ResourceMeta(
        ulid="01TEST",
        name="postwannier",
        slug="postwannier",
        path="steps/postwannier.step.yaml",
        kind="step",
    )

    # postwannier step explicitly sets num_iter=0 (agent thinks postw90
    # doesn't need iterations) — this must NOT corrupt the .win file.
    spec = StructureStepSpec(
        meta=meta,
        structure=str(structure_file),
        step_type_spec="w90_postwannier",
        parameters={
            "parameters": {
                "berry": True,
                "berry_task": "'ahc'",
                "num_iter": 0,
            }
        },
    )

    generated_input, _ = materialize_step_spec(
        spec=spec,
        output_dir=raw_dir,
        project_root=temp_dir,
    )

    content = generated_input.read_text()
    assert "num_iter        = 200" in content, (
        f"postwannier overwrote num_iter — expected 200, got:\n{content}"
    )
    assert "berry = .true." in content


def test_postwannier_preserves_num_iter_when_not_set(temp_dir, simple_structure):
    """postwannier without num_iter in params preserves existing .win value."""
    raw_dir = temp_dir / "raw"
    raw_dir.mkdir(parents=True)

    existing = raw_dir / "fe.win"
    existing.write_text("num_wann        = 18\nnum_iter        = 200\n")

    structures_dir = temp_dir / "structures"
    structures_dir.mkdir(parents=True)
    structure_file = structures_dir / "structure.json"
    simple_structure.to(fmt="json", filename=str(structure_file))

    meta = ResourceMeta(
        ulid="01TEST",
        name="postwannier",
        slug="postwannier",
        path="steps/postwannier.step.yaml",
        kind="step",
    )

    spec = StructureStepSpec(
        meta=meta,
        structure=str(structure_file),
        step_type_spec="w90_postwannier",
        parameters={
            "parameters": {
                "berry": True,
                "berry_task": "'ahc'",
            }
        },
    )

    generated_input, _ = materialize_step_spec(
        spec=spec,
        output_dir=raw_dir,
        project_root=temp_dir,
    )

    content = generated_input.read_text()
    assert "num_iter        = 200" in content, (
        f"postwannier lost num_iter — expected 200, got:\n{content}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
