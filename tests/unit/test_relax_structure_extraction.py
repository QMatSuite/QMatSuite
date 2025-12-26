"""
Tests for relax/vc-relax structure extraction from QE output.
"""

import pytest
from pathlib import Path
from quantumvitas.calculation.geometry import (
    read_final_geometry_from_output_text,
    structure_from_qe_geometry_snapshot,
)


def test_read_final_geometry_from_output_text():
    """Test parsing final coordinates block from QE output."""
    # Use the test data file
    output_file = Path(__file__).parent.parent / "data" / "3_Si_vc_relax" / "reference_output" / "si.vc_relax.out"
    
    if not output_file.exists():
        pytest.skip(f"Test data file not found: {output_file}")
    
    text = output_file.read_text()
    snapshot, species = read_final_geometry_from_output_text(text)
    
    # Verify basic structure
    assert len(species) == 2
    assert all(s == "Si" for s in species)
    assert len(snapshot.atomic_positions) == 2
    assert len(snapshot.cell_matrix) == 3
    assert all(len(row) == 3 for row in snapshot.cell_matrix)
    
    # Verify alat conversion
    assert snapshot.alat_angstrom > 0
    # alat from output is 14.0 Bohr, should be ~7.4 Angstrom
    assert 7.0 < snapshot.alat_angstrom < 8.0
    
    # Verify cell matrix is dimensionless (multiples of alat)
    # First row from output: -0.371818187   0.000000000   0.371818187
    assert abs(snapshot.cell_matrix[0][0] - (-0.371818187)) < 1e-6
    assert abs(snapshot.cell_matrix[0][1] - 0.0) < 1e-6
    assert abs(snapshot.cell_matrix[0][2] - 0.371818187) < 1e-6
    
    # Verify positions are dimensionless
    # First position: 0.000000000   0.000000000   0.000000000
    assert abs(snapshot.atomic_positions[0].vector[0] - 0.0) < 1e-6
    assert abs(snapshot.atomic_positions[0].vector[1] - 0.0) < 1e-6
    assert abs(snapshot.atomic_positions[0].vector[2] - 0.0) < 1e-6


def test_structure_from_qe_geometry_snapshot():
    """Test conversion from QEGeometrySnapshot to pymatgen Structure with canonization."""
    from quantumvitas.calculation.geometry import QEGeometrySnapshot, QEAtomicPosition
    
    # Create a simple snapshot (Si diamond structure)
    snapshot = QEGeometrySnapshot(
        alat_angstrom=5.431,  # Si lattice parameter in Angstrom
        cell_matrix=[
            [0.5, 0.5, 0.0],
            [0.5, 0.0, 0.5],
            [0.0, 0.5, 0.5],
        ],
        atomic_positions=[
            QEAtomicPosition("Si", (0.0, 0.0, 0.0)),
            QEAtomicPosition("Si", (0.25, 0.25, 0.25)),
        ],
    )
    species = ["Si", "Si"]
    
    structure = structure_from_qe_geometry_snapshot(snapshot, species)
    
    # Verify structure properties
    assert len(structure) == 2
    assert structure.composition.formula == "Si2"
    
    # Verify canonization was applied (fractional coords should be in canonical range)
    from quantumvitas.analysis.structure_viz import WRAP_TOL
    for site in structure:
        for coord in site.frac_coords:
            assert -WRAP_TOL <= coord < 1 - WRAP_TOL, f"Coordinate {coord} not in canonical range"
    
    # Verify cell is in Angstrom
    cell = structure.lattice.matrix
    # Cell should be scaled by alat
    # For Si, alat=5.431, so cell vectors should be ~2.7 Angstrom
    assert all(abs(cell[i][j]) < 10.0 for i in range(3) for j in range(3)), "Cell matrix should be in Angstrom"


def test_read_final_geometry_handles_multiple_blocks():
    """Test that parser correctly selects the LAST final coordinates block."""
    # Create a mock output with multiple blocks
    text = """
Begin final coordinates
CELL_PARAMETERS (alat= 10.0)
  1.0 0.0 0.0
  0.0 1.0 0.0
  0.0 0.0 1.0
ATOMIC_POSITIONS (alat)
Si 0.0 0.0 0.0
End final coordinates

Some intermediate output...

Begin final coordinates
CELL_PARAMETERS (alat= 14.0)
  -0.37 0.0 0.37
  0.0 0.37 0.37
  -0.37 0.37 0.0
ATOMIC_POSITIONS (alat)
Si 0.0 0.0 0.0
Si 0.186 0.186 0.186
End final coordinates
"""
    
    snapshot, species = read_final_geometry_from_output_text(text)
    
    # Should use the LAST block (alat=14.0, not 10.0)
    assert abs(snapshot.alat_angstrom - (14.0 * 0.52917721092)) < 1e-6
    assert len(species) == 2
    assert abs(snapshot.cell_matrix[0][0] - (-0.37)) < 1e-6


def test_read_final_geometry_raises_on_missing_block():
    """Test that parser raises clear error when no final coordinates block is found."""
    text = "Some QE output without final coordinates block"
    
    with pytest.raises(ValueError, match="No 'Begin final coordinates' block found"):
        read_final_geometry_from_output_text(text)


def test_read_final_geometry_handles_alat_without_explicit_value():
    """Test that parser can extract alat from elsewhere when CELL_PARAMETERS doesn't specify it."""
    text = """
celldm(1) = 14.0

Begin final coordinates
CELL_PARAMETERS (alat)
  1.0 0.0 0.0
  0.0 1.0 0.0
  0.0 0.0 1.0
ATOMIC_POSITIONS (alat)
Si 0.0 0.0 0.0
End final coordinates
"""
    
    snapshot, species = read_final_geometry_from_output_text(text)
    
    # Should extract alat from celldm(1) earlier in output
    assert abs(snapshot.alat_angstrom - (14.0 * 0.52917721092)) < 1e-6

