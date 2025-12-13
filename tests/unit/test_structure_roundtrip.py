"""
Comprehensive round-trip tests for structure ↔ QE input conversion.

These tests verify that:
1. Structure → QE Input → Structure preserves structure integrity
2. QE Input → Structure → QE Input preserves QE input structure parts
3. Multiple formats (CIF, POSCAR, JSON) work correctly
4. Different step types and parameters are handled correctly
5. Edge cases (coordinate systems, fractional vs cartesian) work
"""

import json
from pathlib import Path

import pytest
import numpy as np
from pymatgen.core import Lattice, Structure

# Try to import MatSciTest (new) or PymatgenTest (deprecated)
try:
    from pymatgen.util.testing import MatSciTest as PymatgenTest
except ImportError:
    try:
        from pymatgen.util.testing import PymatgenTest
    except ImportError:
        PymatgenTest = None

from quantumvitas.io import (
    QEInputGenerator,
    QEInputParser,
    QECardType,
    read_structure,
    write_structure,
)
from quantumvitas.io.structure_io import (
    qe_input_from_structure,
    structure_from_qe_input,
)
from quantumvitas.core.resources import meta_from_name
from quantumvitas.calculation.structure_steps import (
    generate_qe_input_from_structure,
    generate_qe_input_from_spec,
    overrides_from_step_spec,
    StructureStepSpec,
)
from quantumvitas.calculation.input_runner import ParameterOverride


# Module-level fixtures for use across test classes
@pytest.fixture
def si_diamond_structure():
    """Simple Si diamond structure."""
    lattice = Lattice.cubic(5.43)
    structure = Structure(
        lattice,
        ["Si", "Si"],
        [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    )
    return structure


@pytest.fixture
def gaas_zincblende_structure():
    """GaAs zincblende structure."""
    lattice = Lattice.cubic(5.65)
    structure = Structure(
        lattice,
        ["Ga", "As"],
        [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    )
    return structure


@pytest.fixture
def complex_structure():
    """More complex structure with multiple elements (SrTiO3 perovskite-like)."""
    # Simple cubic perovskite-like structure using real elements
    lattice = Lattice.cubic(4.0)
    structure = Structure(
        lattice,
        ["Sr", "Ti", "O", "O", "O"],
        [
            [0.0, 0.0, 0.0],
            [0.5, 0.5, 0.5],
            [0.5, 0.0, 0.0],
            [0.0, 0.5, 0.0],
            [0.0, 0.0, 0.5],
        ],
    )
    return structure


class TestStructureToQEInputToStructure:
    """Round-trip: Structure → QE Input → Structure"""

    def test_si_roundtrip_basic(self, si_diamond_structure):
        """
        Test basic round-trip: Si structure → QE input → structure.

        Verifies that:
        - Structure is preserved (formula, number of sites, lattice)
        - Atomic positions are preserved (within tolerance)
        - Lattice parameters are preserved
        """
        original = si_diamond_structure

        # Structure → QE Input
        qe_input = qe_input_from_structure(original)

        # QE Input → Structure
        reconstructed = structure_from_qe_input(qe_input)

        # Verify structure integrity
        assert reconstructed.formula == original.formula
        assert len(reconstructed) == len(original)
        assert reconstructed.lattice.a == pytest.approx(original.lattice.a, abs=1e-6)
        assert reconstructed.lattice.b == pytest.approx(original.lattice.b, abs=1e-6)
        assert reconstructed.lattice.c == pytest.approx(original.lattice.c, abs=1e-6)

        # Verify atomic positions (within tolerance)
        for orig_site, recon_site in zip(original.sites, reconstructed.sites):
            assert orig_site.specie == recon_site.specie
            np.testing.assert_allclose(
                orig_site.coords, recon_site.coords, atol=1e-6
            )

    def test_gaas_roundtrip(self, gaas_zincblende_structure):
        """
        Test round-trip for multi-element structure (GaAs).

        Verifies that structures with multiple elements are handled correctly.
        """
        original = gaas_zincblende_structure

        qe_input = qe_input_from_structure(original)
        reconstructed = structure_from_qe_input(qe_input)

        assert reconstructed.formula == original.formula
        assert len(reconstructed) == len(original)

        # Verify composition
        assert set(reconstructed.composition.elements) == set(
            original.composition.elements
        )

        # Verify positions
        for orig_site, recon_site in zip(original.sites, reconstructed.sites):
            assert orig_site.specie == recon_site.specie
            np.testing.assert_allclose(
                orig_site.coords, recon_site.coords, atol=1e-6
            )

    def test_complex_structure_roundtrip(self, complex_structure):
        """
        Test round-trip for complex structure with many sites.

        Verifies that structures with multiple sites and elements work correctly.
        """
        original = complex_structure

        qe_input = qe_input_from_structure(original)
        reconstructed = structure_from_qe_input(qe_input)

        assert reconstructed.formula == original.formula
        assert len(reconstructed) == len(original)

        # Verify all sites match
        for orig_site, recon_site in zip(original.sites, reconstructed.sites):
            assert orig_site.specie == recon_site.specie
            np.testing.assert_allclose(
                orig_site.coords, recon_site.coords, atol=1e-6
            )

    def test_roundtrip_with_step_type(self, si_diamond_structure):
        """
        Test round-trip with different step types.

        Verifies that step type doesn't affect structure preservation.
        """
        original = si_diamond_structure

        for step_type in ["scf", "nscf", "relax", "vc-relax", "bands"]:
            qe_input = generate_qe_input_from_structure(
                structure=original, step_type=step_type
            )

            # Verify step type is set correctly
            control = qe_input.get_namelist("CONTROL")
            assert control.get("calculation") == step_type

            # Verify structure is preserved
            reconstructed = structure_from_qe_input(qe_input)
            assert reconstructed.formula == original.formula
            assert len(reconstructed) == len(original)
            np.testing.assert_allclose(
                original.lattice.matrix, reconstructed.lattice.matrix, atol=1e-6
            )

    def test_roundtrip_with_parameter_overrides(self, si_diamond_structure):
        """
        Test round-trip with parameter overrides.

        Verifies that parameter overrides don't affect structure preservation.
        """
        original = si_diamond_structure

        overrides = [
            ParameterOverride(name="ecutwfc", value=60, section="SYSTEM"),
            ParameterOverride(name="ecutrho", value=240, section="SYSTEM"),
            ParameterOverride(name="degauss", value=0.01, section="SYSTEM"),
        ]

        qe_input = generate_qe_input_from_structure(
            structure=original, step_type="scf", parameter_overrides=overrides
        )

        # Verify parameters were applied
        system = qe_input.get_namelist("SYSTEM")
        assert system.get("ecutwfc") == 60
        assert system.get("ecutrho") == 240
        assert system.get("degauss") == 0.01

        # Verify structure is preserved
        reconstructed = structure_from_qe_input(qe_input)
        assert reconstructed.formula == original.formula
        np.testing.assert_allclose(
            original.lattice.matrix, reconstructed.lattice.matrix, atol=1e-6
        )


class TestQEInputToStructureToQEInput:
    """Round-trip: QE Input → Structure → QE Input"""

    def test_qe_input_roundtrip_basic(self, tmp_path):
        """
        Test round-trip: QE Input → Structure → QE Input.

        Verifies that structure parts of QE input are preserved.
        """
        # Create original QE input file
        original_content = """&CONTROL
    calculation = 'scf'
    prefix = 'si'
/
&SYSTEM
    ecutwfc = 30.0
    ecutrho = 120.0
/
&ELECTRONS
/
ATOMIC_SPECIES
Si  28.085  Si.upf
ATOMIC_POSITIONS angstrom
Si  0.0  0.0  0.0
Si  1.3575  1.3575  1.3575
CELL_PARAMETERS angstrom
   5.430000  0.000000  0.000000
   0.000000  5.430000  0.000000
   0.000000  0.000000  5.430000
K_POINTS automatic
4 4 4 0 0 0
"""
        original_file = tmp_path / "si.scf.in"
        original_file.write_text(original_content)

        # Parse original QE input
        original_qe_input = QEInputParser.parse_file(original_file)

        # Extract structure
        structure = structure_from_qe_input(original_qe_input)

        # Generate new QE input from structure
        new_qe_input = qe_input_from_structure(structure)

        # Verify structure cards match
        orig_species = original_qe_input.get_card(QECardType.ATOMIC_SPECIES)
        new_species = new_qe_input.get_card(QECardType.ATOMIC_SPECIES)
        assert orig_species is not None
        assert new_species is not None
        assert len(orig_species.data) == len(new_species.data)
        assert orig_species.data[0][0] == new_species.data[0][0]  # Element symbol

        orig_positions = original_qe_input.get_card(QECardType.ATOMIC_POSITIONS)
        new_positions = new_qe_input.get_card(QECardType.ATOMIC_POSITIONS)
        assert orig_positions is not None
        assert new_positions is not None
        assert len(orig_positions.data) == len(new_positions.data)

        # Verify positions match (within tolerance)
        for orig_row, new_row in zip(orig_positions.data, new_positions.data):
            assert orig_row[0] == new_row[0]  # Element symbol
            np.testing.assert_allclose(
                [float(orig_row[1]), float(orig_row[2]), float(orig_row[3])],
                [float(new_row[1]), float(new_row[2]), float(new_row[3])],
                atol=1e-6,
            )

        # Verify cell parameters match
        orig_cell = original_qe_input.get_card(QECardType.CELL_PARAMETERS)
        new_cell = new_qe_input.get_card(QECardType.CELL_PARAMETERS)
        assert orig_cell is not None
        assert new_cell is not None
        for orig_row, new_row in zip(orig_cell.data, new_cell.data):
            np.testing.assert_allclose(
                [float(x) for x in orig_row],
                [float(x) for x in new_row],
                atol=1e-6,
            )


class TestFormatRoundtrip:
    """Round-trip through different file formats"""

    def test_cif_to_structure_to_qe_input_to_structure_to_cif(
        self, tmp_path, si_diamond_structure
    ):
        """
        Test complete round-trip: CIF → Structure → QE Input → Structure → CIF.

        Verifies that format conversions preserve structure integrity.
        """
        original = si_diamond_structure

        # Structure → CIF
        cif_file = tmp_path / "si.cif"
        write_structure(original, cif_file, format="cif")

        # CIF → Structure
        structure_from_cif = read_structure(cif_file, format="cif")

        # Structure → QE Input
        qe_input = qe_input_from_structure(structure_from_cif)

        # QE Input → Structure
        structure_from_qe = structure_from_qe_input(qe_input)

        # Structure → CIF
        cif_file2 = tmp_path / "si_roundtrip.cif"
        write_structure(structure_from_qe, cif_file2, format="cif")

        # Verify final structure matches original
        assert structure_from_qe.formula == original.formula
        assert len(structure_from_qe) == len(original)
        np.testing.assert_allclose(
            original.lattice.matrix, structure_from_qe.lattice.matrix, atol=1e-5
        )

    def test_json_to_structure_to_qe_input_to_structure_to_json(
        self, tmp_path, si_diamond_structure
    ):
        """
        Test complete round-trip: JSON → Structure → QE Input → Structure → JSON.

        JSON is the canonical format, so this should be lossless.
        """
        original = si_diamond_structure

        # Structure → JSON
        json_file = tmp_path / "si.json"
        write_structure(original, json_file, format="json")

        # JSON → Structure
        structure_from_json = read_structure(json_file, format="json")

        # Structure → QE Input
        qe_input = qe_input_from_structure(structure_from_json)

        # QE Input → Structure
        structure_from_qe = structure_from_qe_input(qe_input)

        # Structure → JSON
        json_file2 = tmp_path / "si_roundtrip.json"
        write_structure(structure_from_qe, json_file2, format="json")

        # Verify final structure matches original
        assert structure_from_qe.formula == original.formula
        assert len(structure_from_qe) == len(original)
        np.testing.assert_allclose(
            original.lattice.matrix, structure_from_qe.lattice.matrix, atol=1e-6
        )

        # Verify JSON files are equivalent (structure-wise)
        data1 = json.loads(json_file.read_text())
        data2 = json.loads(json_file2.read_text())
        assert len(data1["sites"]) == len(data2["sites"])

    def test_poscar_to_structure_to_qe_input_to_structure_to_poscar(
        self, tmp_path, si_diamond_structure
    ):
        """
        Test complete round-trip: POSCAR → Structure → QE Input → Structure → POSCAR.

        Verifies POSCAR format handling.
        """
        original = si_diamond_structure

        # Structure → POSCAR
        poscar_file = tmp_path / "POSCAR"
        write_structure(original, poscar_file, format="poscar")

        # POSCAR → Structure
        structure_from_poscar = read_structure(poscar_file, format="vasp")

        # Structure → QE Input
        qe_input = qe_input_from_structure(structure_from_poscar)

        # QE Input → Structure
        structure_from_qe = structure_from_qe_input(qe_input)

        # Verify final structure matches original
        assert structure_from_qe.formula == original.formula
        assert len(structure_from_qe) == len(original)
        np.testing.assert_allclose(
            original.lattice.matrix, structure_from_qe.lattice.matrix, atol=1e-5
        )


class TestStepSpecRoundtrip:
    """Round-trip with StructureStepSpec"""

    def test_structure_to_spec_to_qe_input_to_structure(
        self, tmp_path, si_diamond_structure
    ):
        """
        Test round-trip: Structure → Step Spec → QE Input → Structure.

        Verifies that step specifications work correctly.
        """
        original = si_diamond_structure

        # Create step spec
        spec = StructureStepSpec(
            meta=meta_from_name("step", name="nscf", path="nscf.step.yaml"),
            structure="si",
            step_type="nscf",
            parameters={
                "SYSTEM": {"ecutwfc": 60, "ecutrho": 240},
                "ELECTRONS": {"mixing_beta": 0.7},
            },
        )

        # Generate QE input from spec
        qe_input, _ = generate_qe_input_from_spec(original, spec)

        # Verify parameters were applied
        control = qe_input.get_namelist("CONTROL")
        assert control.get("calculation") == "nscf"

        system = qe_input.get_namelist("SYSTEM")
        assert system.get("ecutwfc") == 60
        assert system.get("ecutrho") == 240

        electrons = qe_input.get_namelist("ELECTRONS")
        assert electrons.get("mixing_beta") == 0.7

        # Verify structure is preserved
        reconstructed = structure_from_qe_input(qe_input)
        assert reconstructed.formula == original.formula
        assert len(reconstructed) == len(original)
        np.testing.assert_allclose(
            original.lattice.matrix, reconstructed.lattice.matrix, atol=1e-6
        )

    def test_spec_yaml_roundtrip(self, tmp_path, si_diamond_structure):
        """
        Test round-trip: Structure → Step Spec YAML → QE Input → Structure.

        Verifies that YAML step specs work correctly.
        """
        import yaml

        original = si_diamond_structure

        # Create step spec YAML (DAG model: should NOT contain structure_id)
        spec = StructureStepSpec(
            meta=meta_from_name("step", name="scf", path="step.yaml"),
            structure="",  # Empty legacy field (not written to YAML)
            step_type="scf",
            parameters={
                "SYSTEM": {"ecutwfc": 60},
            },
        )
        spec_file = tmp_path / "step.yaml"
        spec_dict = spec.to_dict()
        # DAG model: Step YAML should NOT contain structure_id
        assert "structure_id" not in spec_dict, "Step YAML should not contain structure_id (DAG model)"
        spec_file.write_text(yaml.safe_dump(spec_dict))

        # Load spec from YAML
        spec = StructureStepSpec.from_yaml(spec_file)
        # Verify YAML does not contain structure_id
        spec_yaml_text = spec_file.read_text()
        assert "structure_id:" not in spec_yaml_text, "Step YAML should not contain structure_id (DAG model)"

        # Generate QE input
        qe_input, _ = generate_qe_input_from_spec(original, spec)

        # Verify structure is preserved
        reconstructed = structure_from_qe_input(qe_input)
        assert reconstructed.formula == original.formula
        np.testing.assert_allclose(
            original.lattice.matrix, reconstructed.lattice.matrix, atol=1e-6
        )


class TestEdgeCases:
    """Edge cases and special scenarios"""

    def test_fractional_coordinates(self, tmp_path):
        """
        Test round-trip with fractional coordinates in QE input.

        Verifies that fractional coordinates are handled correctly.
        """
        # Create QE input with fractional coordinates
        qe_input_content = """&CONTROL
    calculation = 'scf'
/
&SYSTEM
/
&ELECTRONS
/
ATOMIC_SPECIES
Si  28.085  Si.upf
ATOMIC_POSITIONS crystal
Si  0.0  0.0  0.0
Si  0.25  0.25  0.25
CELL_PARAMETERS angstrom
   5.430000  0.000000  0.000000
   0.000000  5.430000  0.000000
   0.000000  0.000000  5.430000
K_POINTS automatic
4 4 4 0 0 0
"""
        qe_file = tmp_path / "si_fractional.in"
        qe_file.write_text(qe_input_content)

        # Parse and extract structure
        qe_input = QEInputParser.parse_file(qe_file)
        structure = structure_from_qe_input(qe_input)

        # Verify structure is correct
        assert structure.formula == "Si2"
        assert len(structure) == 2

        # Convert back to QE input
        new_qe_input = qe_input_from_structure(structure)

        # Verify structure is preserved
        reconstructed = structure_from_qe_input(new_qe_input)
        assert reconstructed.formula == structure.formula
        np.testing.assert_allclose(
            structure.lattice.matrix, reconstructed.lattice.matrix, atol=1e-6
        )

    def test_bohr_units(self, tmp_path):
        """
        Test round-trip with Bohr units in CELL_PARAMETERS.

        Verifies that unit conversion is handled correctly.
        """
        # Create structure
        lattice = Lattice.cubic(5.43)
        structure = Structure(
            lattice,
            ["Si", "Si"],
            [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
        )

        # Generate QE input
        qe_input = qe_input_from_structure(structure)

        # Manually modify to use Bohr units
        cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
        assert cell_card is not None
        cell_card.option = "bohr"
        # Convert angstrom to Bohr (1 Bohr ≈ 0.529177 Å)
        bohr_to_angstrom = 0.52917721092
        for row in cell_card.data:
            for i in range(len(row)):
                row[i] = float(row[i]) / bohr_to_angstrom

        # Extract structure (should convert back to angstrom)
        reconstructed = structure_from_qe_input(qe_input)

        # Verify structure matches original
        assert reconstructed.formula == structure.formula
        np.testing.assert_allclose(
            structure.lattice.matrix, reconstructed.lattice.matrix, atol=1e-5
        )

    def test_non_cubic_lattice(self):
        """
        Test round-trip with non-cubic lattice (orthorhombic).

        Verifies that non-cubic lattices are handled correctly.
        """
        # Create orthorhombic structure with real elements
        lattice = Lattice.orthorhombic(4.0, 5.0, 6.0)
        structure = Structure(
            lattice,
            ["Si", "Ge"],
            [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]],
        )

        # Round-trip
        qe_input = qe_input_from_structure(structure)
        reconstructed = structure_from_qe_input(qe_input)

        # Verify lattice parameters
        assert reconstructed.lattice.a == pytest.approx(4.0, abs=1e-6)
        assert reconstructed.lattice.b == pytest.approx(5.0, abs=1e-6)
        assert reconstructed.lattice.c == pytest.approx(6.0, abs=1e-6)

    def test_pymatgen_test_structures(self):
        """
        Test round-trip with pymatgen test structures.

        Uses pymatgen's built-in test structures to verify compatibility.
        """
        # Get a test structure from pymatgen (try MatSciTest first, fallback to PymatgenTest)
        try:
            from pymatgen.util.testing import MatSciTest
            test_structure = MatSciTest.get_structure("Li2O")
        except (ImportError, AttributeError):
            try:
                test_structure = PymatgenTest.get_structure("Li2O")
            except Exception:
                # Fallback if test structure not available
                lattice = Lattice.cubic(4.0)
                test_structure = Structure(
                    lattice,
                    ["Li", "Li", "O"],
                    [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5], [0.25, 0.25, 0.25]],
                )

        original = test_structure

        # Round-trip
        qe_input = qe_input_from_structure(original)
        reconstructed = structure_from_qe_input(qe_input)

        # Verify structure integrity
        assert reconstructed.formula == original.formula
        assert len(reconstructed) == len(original)
        np.testing.assert_allclose(
            original.lattice.matrix, reconstructed.lattice.matrix, atol=1e-5
        )


class TestMultipleRoundtrips:
    """Multiple consecutive round-trips"""

    def test_multiple_roundtrips_preserve_structure(self, si_diamond_structure):
        """
        Test that multiple round-trips don't accumulate errors.

        Verifies that repeated conversions don't degrade structure quality.
        """
        original = si_diamond_structure
        current = original

        # Perform 5 round-trips
        for i in range(5):
            qe_input = qe_input_from_structure(current)
            current = structure_from_qe_input(qe_input)

        # Verify final structure matches original
        assert current.formula == original.formula
        assert len(current) == len(original)
        np.testing.assert_allclose(
            original.lattice.matrix, current.lattice.matrix, atol=1e-5
        )

        # Verify positions are still accurate
        for orig_site, curr_site in zip(original.sites, current.sites):
            np.testing.assert_allclose(
                orig_site.coords, curr_site.coords, atol=1e-5
            )

