"""
Example tests demonstrating structure I/O usage patterns.

These tests serve as both documentation and validation of the structure I/O API.
"""

import json
from pathlib import Path

import pytest
from pymatgen.core import Lattice, Structure

from quantumvitas.io import (
    QEInputGenerator,
    QEInputParser,
    read_structure,
    write_structure,
)
from quantumvitas.io.structure_io import (
    STRUCTURE_DATA_KEY,
    STRUCTURE_META_KEY,
    qe_input_from_structure,
)


@pytest.fixture
def sample_si_structure():
    """Create a simple Si diamond structure for testing."""
    lattice = Lattice.cubic(5.43)
    structure = Structure(
        lattice,
        ["Si", "Si"],
        [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    )
    return structure


class TestReadWriteStructure:
    """Examples of reading and writing structures."""

    def test_read_write_json_roundtrip(self, tmp_path, sample_si_structure):
        """
        Example: Read and write structure in JSON format (canonical format).

        JSON is the recommended format for project storage as it preserves
        all structure metadata and is easily readable/editable.
        """
        json_file = tmp_path / "si.json"

        # Write structure to JSON
        metadata = {
            "ulid": "demo-structure",
            "name": "Si demo",
            "slug": "si-demo",
            "path": "structures/si.json",
            "kind": "structure",
        }
        write_structure(sample_si_structure, json_file, format="json", metadata=metadata)

        # Verify JSON content
        data = json.loads(json_file.read_text())
        assert STRUCTURE_META_KEY in data
        payload = data[STRUCTURE_DATA_KEY]
        assert payload["@module"] == "pymatgen.core.structure"
        assert len(payload["sites"]) == 2

        # Read structure back
        loaded = read_structure(json_file, format="json")
        assert loaded.formula == "Si2"
        assert len(loaded) == 2
        assert loaded.lattice.a == pytest.approx(5.43)

    def test_read_write_cif(self, tmp_path, sample_si_structure):
        """
        Example: Export structure to CIF format for external tools.

        CIF is widely supported by crystallographic software.
        """
        cif_file = tmp_path / "si.cif"

        # Write to CIF
        write_structure(sample_si_structure, cif_file, format="cif")

        # Verify file exists and has CIF header
        content = cif_file.read_text()
        assert "data_" in content
        assert "_cell_length_a" in content

        # Read back from CIF
        loaded = read_structure(cif_file, format="cif")
        assert loaded.formula == "Si2"

    def test_read_write_poscar(self, tmp_path, sample_si_structure):
        """
        Example: Export structure to VASP POSCAR format.

        POSCAR format is commonly used for VASP calculations.
        """
        poscar_file = tmp_path / "POSCAR"

        # Write to POSCAR
        write_structure(sample_si_structure, poscar_file, format="poscar")

        # Verify POSCAR format
        content = poscar_file.read_text()
        lines = content.strip().split("\n")
        assert lines[0].strip() == "Si2"  # Comment line
        # POSCAR format has scale factor on line 1, then lattice vectors
        assert len(lines) > 5  # Should have multiple lines

        # Read back
        loaded = read_structure(poscar_file, format="vasp")
        assert loaded.formula == "Si2"

    def test_auto_detect_format_from_extension(self, tmp_path, sample_si_structure):
        """
        Example: Format auto-detection from file extension.

        The format is automatically detected from the file extension,
        so you don't need to specify it explicitly.
        """
        # Write with different extensions
        json_file = tmp_path / "si.json"
        cif_file = tmp_path / "si.cif"
        poscar_file = tmp_path / "POSCAR"

        write_structure(sample_si_structure, json_file, format="json")
        write_structure(sample_si_structure, cif_file, format="cif")
        write_structure(sample_si_structure, poscar_file, format="poscar")

        # Read back without specifying format
        json_loaded = read_structure(json_file)
        cif_loaded = read_structure(cif_file)
        poscar_loaded = read_structure(poscar_file, format="vasp")

        assert json_loaded.formula == "Si2"
        assert cif_loaded.formula == "Si2"
        assert poscar_loaded.formula == "Si2"


class TestQEInputFromStructure:
    """Examples of generating QE inputs from structures."""

    def test_generate_minimal_qe_input(self, tmp_path, sample_si_structure):
        """
        Example: Generate a minimal QE input from a structure.

        This creates a basic pw.x input with:
        - Default calculation='scf'
        - Structure cards (ATOMIC_SPECIES, ATOMIC_POSITIONS, CELL_PARAMETERS)
        - Default K_POINTS mesh
        """
        # Generate QE input
        qe_input = qe_input_from_structure(sample_si_structure)

        # Verify namelists
        control = qe_input.get_namelist("CONTROL")
        assert control is not None
        assert control.get("calculation") == "scf"

        system = qe_input.get_namelist("SYSTEM")
        assert system is not None

        # Verify cards
        atomic_species = qe_input.get_card(qe_input.cards[0].card_type)
        assert atomic_species is not None

        atomic_positions = qe_input.get_card(qe_input.cards[1].card_type)
        assert atomic_positions is not None
        assert atomic_positions.option == "crystal"  # QE input generator now uses crystal (fractional) coordinates

        cell_parameters = qe_input.get_card(qe_input.cards[2].card_type)
        assert cell_parameters is not None
        assert cell_parameters.option == "angstrom"

        k_points = qe_input.get_card(qe_input.cards[3].card_type)
        assert k_points is not None
        assert k_points.option == "automatic"

        # Write to file
        output_file = tmp_path / "si.pw.in"
        QEInputGenerator.write_file(qe_input, output_file)

        # Verify file content
        content = output_file.read_text()
        assert "&CONTROL" in content
        assert "calculation = 'scf'" in content
        assert "ATOMIC_SPECIES" in content
        assert "ATOMIC_POSITIONS" in content
        assert "crystal" in content  # ATOMIC_POSITIONS uses crystal (fractional) format
        assert "CELL_PARAMETERS" in content
        assert "angstrom" in content  # CELL_PARAMETERS still uses angstrom
        assert "K_POINTS" in content

    def test_generate_qe_input_with_multiple_elements(self, tmp_path):
        """
        Example: Generate QE input for a multi-element structure.

        The function correctly handles structures with multiple elements.
        """
        # Create GaAs structure
        lattice = Lattice.cubic(5.65)
        structure = Structure(
            lattice,
            ["Ga", "As"],
            [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
        )

        # Generate QE input
        qe_input = qe_input_from_structure(structure)

        # Verify atomic species
        atomic_species = qe_input.get_card(qe_input.cards[0].card_type)
        assert len(atomic_species.data) == 2
        assert atomic_species.data[0][0] == "Ga"
        assert atomic_species.data[1][0] == "As"

        # Write and verify
        output_file = tmp_path / "gaas.pw.in"
        QEInputGenerator.write_file(qe_input, output_file)
        content = output_file.read_text()
        assert "Ga" in content
        assert "As" in content


class TestReadStructureFromQEInput:
    """Examples of extracting structures from QE input files."""

    def test_read_structure_from_qe_input(self, tmp_path, sample_si_structure):
        """
        Example: Read structure from an existing QE input file.

        This is useful when you have a QE input and want to extract
        the structure for use in other calculations.
        """
        # First, create a QE input from structure
        qe_input = qe_input_from_structure(sample_si_structure)
        qe_file = tmp_path / "si.scf.in"
        QEInputGenerator.write_file(qe_input, qe_file)

        # Now read structure back from QE input
        loaded_structure = read_structure(qe_file, format="qe")

        # Verify structure matches
        assert loaded_structure.formula == "Si2"
        assert len(loaded_structure) == 2
        assert loaded_structure.lattice.a == pytest.approx(5.43)

    def test_roundtrip_structure_through_qe_input(self, tmp_path, sample_si_structure):
        """
        Example: Complete roundtrip: Structure -> QE Input -> Structure.

        This demonstrates that structure information is preserved
        when converting to/from QE input format.
        """
        # Structure -> QE Input
        qe_input = qe_input_from_structure(sample_si_structure)
        qe_file = tmp_path / "si.scf.in"
        QEInputGenerator.write_file(qe_input, qe_file)

        # QE Input -> Structure
        loaded = read_structure(qe_file, format="qe")

        # Verify roundtrip
        assert loaded.formula == sample_si_structure.formula
        assert len(loaded) == len(sample_si_structure)
        assert loaded.lattice.a == pytest.approx(sample_si_structure.lattice.a)


class TestRealWorldExamples:
    """Real-world usage examples combining multiple functions."""

    def test_import_structure_and_generate_input(self, tmp_path, sample_si_structure):
        """
        Example: Complete calculation of importing structure and generating QE input.

        This mimics what `qv import-structure` and `qv run-structure` do internally.
        """
        # Step 1: Save structure to project (like qv import-structure)
        structures_dir = tmp_path / "structures"
        structures_dir.mkdir()
        structure_file = structures_dir / "si.json"
        write_structure(sample_si_structure, structure_file, format="json")

        # Step 2: Load structure (like qv run-structure)
        loaded_structure = read_structure(structure_file, format="json")

        # Step 3: Generate QE input
        qe_input = qe_input_from_structure(loaded_structure)

        # Step 4: Write QE input
        qe_file = tmp_path / "si.pw.in"
        QEInputGenerator.write_file(qe_input, qe_file)

        # Verify
        assert qe_file.exists()
        content = qe_file.read_text()
        assert "Si" in content
        assert "ATOMIC_SPECIES" in content

    def test_modify_structure_and_regenerate(self, tmp_path, sample_si_structure):
        """
        Example: Modify structure (e.g., scale lattice) and regenerate QE input.

        This shows how to programmatically modify structures before generating inputs.
        """
        # Scale lattice
        scaled_lattice = Lattice.cubic(5.50)  # Slightly larger
        modified_structure = Structure(
            scaled_lattice,
            sample_si_structure.species,
            sample_si_structure.cart_coords,
        )

        # Generate new QE input
        qe_input = qe_input_from_structure(modified_structure)
        qe_file = tmp_path / "si_scaled.pw.in"
        QEInputGenerator.write_file(qe_input, qe_file)

        # Verify new lattice parameter
        content = qe_file.read_text()
        assert "5.5" in content or "5.50" in content

