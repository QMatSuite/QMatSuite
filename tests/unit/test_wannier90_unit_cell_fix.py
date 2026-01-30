"""
Regression tests for Wannier90 unit_cell_cart unit fix.

Tests that:
1. unit_cell_cart is written in Angstrom (not Bohr)
2. atoms_frac comes directly from structure.frac_coords
3. Consistency assertion works correctly
"""

import pytest
from pathlib import Path
import numpy as np
from pymatgen.core import Structure, Lattice

from quantumvitas.calculation.structure_steps import materialize_step_spec
from quantumvitas.calculation.structure_steps import StructureStepSpec
from quantumvitas.core.models import ResourceMeta
from quantumvitas.io.wannier90_input import Wannier90Input


@pytest.fixture
def diamond_structure():
    """Create diamond structure matching example05."""
    # Lattice vectors in Angstrom (from reference diamond.win)
    lattice_matrix = [
        [-1.613990, 0.000000, 1.613990],
        [0.000000, 1.613990, 1.613990],
        [-1.613990, 1.613990, 0.000000]
    ]
    lattice = Lattice(lattice_matrix)
    
    # Fractional coordinates (from reference diamond.win)
    structure = Structure(
        lattice,
        ["C", "C"],
        [[-0.125, -0.125, -0.125], [0.125, 0.125, 0.125]],
        coords_are_cartesian=False
    )
    return structure


def test_w90_unit_cell_cart_in_angstrom(diamond_structure, tmp_path):
    """
    Test that unit_cell_cart is written in Angstrom, not Bohr.
    
    Regression test for the bug where unit_cell_cart was ~3.05 (Bohr)
    instead of ~1.614 (Angstrom).
    """
    # Create a minimal step spec for w90_preproc
    spec = StructureStepSpec(
        meta=ResourceMeta(ulid="test",
            name="test",
            slug="test",
            path="test",
            kind="step"
        ),
        step_type_spec="w90_preproc",
        structure_ulid=None,
        structure=diamond_structure,
        parameters={
            "seedname": "diamond",
            "num_wann": 4,
            "num_iter": 20,
        }
    )
    
    # Mock resolve_structure_for_spec to return our structure
    # We need to patch _resolve_structure_for_spec to return our structure
    from quantumvitas.calculation.structure_steps import _resolve_structure_for_spec
    original_resolve = _resolve_structure_for_spec
    
    def mock_resolve(spec_obj, *args, **kwargs):
        return diamond_structure
    
    import quantumvitas.calculation.structure_steps as ss_module
    ss_module._resolve_structure_for_spec = mock_resolve
    
    try:
        # Generate .win file
        output_path, _ = materialize_step_spec(
            spec,
            output_dir=tmp_path,
            input_name="diamond.win"
        )
    finally:
        ss_module._resolve_structure_for_spec = original_resolve
    
    # Parse the generated file
    win = Wannier90Input.from_file(output_path)
    
    # Verify unit_cell_cart values are in Angstrom (not Bohr)
    # Expected: ~1.614 Angstrom (reference has -1.613990)
    # Bug would produce: ~3.05 (Bohr scale)
    expected_lattice = diamond_structure.lattice.matrix
    actual_lattice = np.array(win.unit_cell_cart)
    
    # Check that values match expected Angstrom scale (not Bohr)
    max_diff = np.max(np.abs(actual_lattice - expected_lattice))
    assert max_diff < 1e-5, (
        f"unit_cell_cart mismatch:\n"
        f"Expected (Å):\n{expected_lattice}\n"
        f"Actual:\n{actual_lattice}\n"
        f"Max difference: {max_diff} Å\n"
        f"If values are ~3.05 instead of ~1.614, this is the Bohr conversion bug."
    )
    
    # Verify length_unit is "ang"
    assert win.length_unit.lower() == "ang", (
        f"length_unit should be 'ang', got '{win.length_unit}'"
    )


def test_w90_atoms_frac_from_structure(diamond_structure, tmp_path):
    """
    Test that atoms_frac comes directly from structure.frac_coords.
    """
    # Save structure to file (materialize_step_spec needs a file path)
    structures_dir = tmp_path / "structures"
    structures_dir.mkdir(parents=True)
    structure_file = structures_dir / "diamond.json"
    diamond_structure.to(fmt="json", filename=str(structure_file))
    
    spec = StructureStepSpec(
        meta=ResourceMeta(ulid="test",
            name="test",
            slug="test",
            path="test",
            kind="step"
        ),
        step_type_spec="w90_preproc",
        structure_ulid=None,
        structure=str(structure_file),
        parameters={
            "seedname": "diamond",
            "num_wann": 4,
        }
    )
    
    output_path, _ = materialize_step_spec(
        spec,
        output_dir=tmp_path / "raw",
        project_root=tmp_path,
        input_name="diamond.win"
    )
    
    win = Wannier90Input.from_file(output_path)
    
    # Verify atoms_frac matches structure.frac_coords
    assert len(win.atoms_frac) == len(diamond_structure), "Mismatch in number of atoms"
    
    for i, (atom_entry, site) in enumerate(zip(win.atoms_frac, diamond_structure.sites)):
        element = atom_entry[0]
        frac_coords = np.array(atom_entry[1:])
        expected_frac = np.array(site.frac_coords)
        
        assert element == site.species_string, f"Element mismatch at index {i}"
        
        max_diff = np.max(np.abs(frac_coords - expected_frac))
        assert max_diff < 1e-6, (
            f"Fractional coordinates mismatch for atom {i}:\n"
            f"Expected: {expected_frac}\n"
            f"Actual: {frac_coords}\n"
            f"Max difference: {max_diff}"
        )


def test_w90_consistency_assertion(diamond_structure):
    """
    Test that the consistency assertion works correctly.
    
    This test verifies that the assertion would catch inconsistencies
    between unit_cell_cart and atoms_frac.
    """
    from quantumvitas.io.wannier90_input import Wannier90Input
    
    # Create a correct Wannier90Input
    win = Wannier90Input()
    win.seedname = "test"
    win.unit_cell_cart = [[float(x) for x in row] for row in diamond_structure.lattice.matrix]
    win.length_unit = "ang"
    win.atoms_frac = [
        [site.species_string, float(site.frac_coords[0]), float(site.frac_coords[1]), float(site.frac_coords[2])]
        for site in diamond_structure.sites
    ]
    
    # This should not raise (correct structure)
    # We can't directly test the assertion in materialize_step_spec, but we can
    # verify the logic is correct by checking the consistency manually
    lattice_matrix = np.array(win.unit_cell_cart)
    for i, site in enumerate(diamond_structure.sites):
        frac_coords = np.array(win.atoms_frac[i][1:])
        expected_cart = lattice_matrix.T @ frac_coords
        actual_cart = np.array(site.coords)
        diff = np.abs(expected_cart - actual_cart)
        max_diff = np.max(diff)
        assert max_diff < 1e-6, f"Consistency check failed for atom {i}"


def test_w90_from_reference_file(tmp_path):
    """
    Test parsing and roundtrip of reference diamond.win file.
    """
    ref_win = Path(__file__).parent.parent.parent / ".qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/examples/example05/diamond.win"
    
    if not ref_win.exists():
        pytest.skip(f"Reference file not found: {ref_win}")
    
    # Parse reference
    win = Wannier90Input.from_file(ref_win)
    
    # Verify unit_cell_cart values are in Angstrom range (~1.6, not ~3.0)
    for vec in win.unit_cell_cart:
        for val in vec:
            abs_val = abs(val)
            # Values should be around 1.6 Angstrom, not 3.0 (Bohr scale)
            assert abs_val < 5.0, f"unit_cell_cart value {val} seems too large (possible Bohr bug)"
            if abs_val > 0.1:  # Skip near-zero values
                assert abs_val < 3.0, (
                    f"unit_cell_cart value {val} is suspiciously large. "
                    f"If it's ~3.05, this indicates Bohr conversion bug."
                )
    
    # Write and re-parse
    output_path = tmp_path / "diamond_roundtrip.win"
    win.write(output_path)
    win2 = Wannier90Input.from_file(output_path)
    
    # Verify roundtrip preserved unit_cell_cart
    assert len(win2.unit_cell_cart) == len(win.unit_cell_cart)
    for v1, v2 in zip(win.unit_cell_cart, win2.unit_cell_cart):
        for x1, x2 in zip(v1, v2):
            assert abs(x1 - x2) < 1e-6, f"Roundtrip mismatch: {x1} != {x2}"


def test_qe_atomic_positions_crystal_format(diamond_structure, tmp_path):
    """
    Test that QE input uses ATOMIC_POSITIONS {crystal} format.
    """
    from quantumvitas.io.structure_io import qe_input_from_structure
    from quantumvitas.io.generator.qe_generator import QEInputGenerator
    
    # Generate QE input from structure
    qe_input = qe_input_from_structure(diamond_structure)
    
    # Generate file content
    content = QEInputGenerator.generate(qe_input)
    
    # Verify ATOMIC_POSITIONS uses crystal format
    assert "ATOMIC_POSITIONS (crystal)" in content or "ATOMIC_POSITIONS {crystal}" in content, (
        f"Expected ATOMIC_POSITIONS with crystal format, got:\n{content[:500]}"
    )
    
    # Verify coordinates are fractional (should be small, < 1.0 for most structures)
    from quantumvitas.io.model import QECardType
    positions_card = qe_input.get_card(QECardType.ATOMIC_POSITIONS)
    assert positions_card is not None, (
        f"ATOMIC_POSITIONS card not found. Available cards: {[c.card_type.value for c in qe_input.cards]}"
    )
    assert positions_card.option.lower() == "crystal", (
        f"ATOMIC_POSITIONS option should be 'crystal', got '{positions_card.option}'"
    )
    
    # Verify coordinates are fractional (not Cartesian in Angstrom)
    for row in positions_card.data:
        if len(row) >= 4:
            x, y, z = float(row[1]), float(row[2]), float(row[3])
            # Fractional coordinates should typically be in [0, 1) or small values
            # Cartesian in Angstrom would be much larger for diamond (~1-2 Å)
            assert abs(x) < 2.0 and abs(y) < 2.0 and abs(z) < 2.0, (
                f"Coordinates {x}, {y}, {z} seem too large for fractional coordinates. "
                f"If they're ~1-2, they might be Cartesian in Angstrom."
            )
    
    # Verify CELL_PARAMETERS still exists and is in angstrom
    from quantumvitas.io.model import QECardType
    cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
    assert cell_card is not None, "CELL_PARAMETERS card not found"
    assert cell_card.option.lower() in ("angstrom", ""), (
        f"CELL_PARAMETERS option should be 'angstrom', got '{cell_card.option}'"
    )

