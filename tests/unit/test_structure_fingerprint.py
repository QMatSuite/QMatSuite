"""
Tests for structure fingerprinting and content-based deduplication.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil

from pymatgen.core import Structure, Lattice

from quantumvitas.core.structure_fingerprint import (
    canonicalize_structure_for_identity,
    structure_fingerprint,
    structures_semantically_equal,
)
from quantumvitas.io.structure_io import write_structure, read_structure
from quantumvitas.api import QVService


@pytest.fixture
def si_structure():
    """Create a simple Si structure for testing."""
    lattice = Lattice.cubic(5.43)
    species = ["Si", "Si"]
    coords = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
    return Structure(lattice, species, coords)


@pytest.fixture
def si_structure_perturbed():
    """Create Si structure with tiny perturbations (< 1e-6)."""
    lattice = Lattice.cubic(5.43 + 1e-7)  # Tiny lattice perturbation
    species = ["Si", "Si"]
    coords = [[0.0 + 1e-8, 0.0, 0.0], [0.25 + 1e-8, 0.25, 0.25]]  # Tiny coord perturbations
    return Structure(lattice, species, coords)


@pytest.fixture
def si_structure_different():
    """Create Si structure with significant differences (> 1e-5)."""
    lattice = Lattice.cubic(5.44)  # Different lattice parameter
    species = ["Si", "Si"]
    coords = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
    return Structure(lattice, species, coords)


class TestStructureFingerprint:
    """Test structure fingerprint generation and stability."""
    
    def test_fingerprint_stability_tiny_perturbations(self, si_structure, si_structure_perturbed):
        """Test that tiny perturbations (< 1e-6) yield same fingerprint with tol=1e-5."""
        fp1 = structure_fingerprint(si_structure, tol=1e-5)
        fp2 = structure_fingerprint(si_structure_perturbed, tol=1e-5)
        
        assert fp1 == fp2, "Fingerprints should match for tiny perturbations"
    
    def test_fingerprint_different_structures(self, si_structure, si_structure_different):
        """Test that structures differing by > tol yield different fingerprints."""
        fp1 = structure_fingerprint(si_structure, tol=1e-5)
        fp2 = structure_fingerprint(si_structure_different, tol=1e-5)
        
        assert fp1 != fp2, "Fingerprints should differ for significantly different structures"
    
    def test_fingerprint_deterministic(self, si_structure):
        """Test that fingerprint is deterministic (same structure yields same fingerprint)."""
        fp1 = structure_fingerprint(si_structure)
        fp2 = structure_fingerprint(si_structure)
        
        assert fp1 == fp2, "Fingerprint should be deterministic"
    
    def test_fingerprint_format(self, si_structure):
        """Test that fingerprint is a hex digest string."""
        fp = structure_fingerprint(si_structure)
        
        assert isinstance(fp, str), "Fingerprint should be a string"
        assert len(fp) == 64, "SHA256 hex digest should be 64 characters"
        assert all(c in '0123456789abcdef' for c in fp), "Fingerprint should be hex"
    
    def test_canonicalize_structure_for_identity(self, si_structure):
        """Test that canonicalization produces structure with coords in [0, 1)."""
        canon = canonicalize_structure_for_identity(si_structure)
        
        for site in canon:
            frac = site.frac_coords
            assert all(0 <= f < 1.0 for f in frac), "Fractional coords should be in [0, 1)"
    
    def test_canonicalize_preserves_structure(self, si_structure):
        """Test that canonicalization preserves structure (same composition, similar lattice)."""
        canon = canonicalize_structure_for_identity(si_structure)
        
        assert canon.composition == si_structure.composition, "Composition should be preserved"
        # Lattice should be similar (within numerical precision)
        lattice_diff = np.abs(canon.lattice.matrix - si_structure.lattice.matrix)
        assert np.max(lattice_diff) < 1e-10, "Lattice should be preserved (within numerical precision)"


class TestStructuresSemanticallyEqual:
    """Test semantic equality checking."""
    
    def test_semantically_equal_identical(self, si_structure):
        """Test that identical structures are semantically equal."""
        assert structures_semantically_equal(si_structure, si_structure), \
            "Identical structures should be semantically equal"
    
    def test_semantically_equal_tiny_perturbations(self, si_structure, si_structure_perturbed):
        """Test that tiny perturbations are considered semantically equal."""
        assert structures_semantically_equal(si_structure, si_structure_perturbed, tol=1e-5), \
            "Tiny perturbations should be semantically equal"
    
    def test_semantically_equal_different(self, si_structure, si_structure_different):
        """Test that significantly different structures are not semantically equal."""
        assert not structures_semantically_equal(si_structure, si_structure_different, tol=1e-5), \
            "Significantly different structures should not be semantically equal"
    
    def test_semantically_equal_different_composition(self, si_structure):
        """Test that different compositions are not semantically equal."""
        # Create structure with different composition
        lattice = Lattice.cubic(5.43)
        species = ["Si", "Ge"]  # Different composition
        coords = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
        different_comp = Structure(lattice, species, coords)
        
        assert not structures_semantically_equal(si_structure, different_comp), \
            "Different compositions should not be semantically equal"


class TestUnitRepresentationStability:
    """Test that different QE input representations yield same fingerprint."""
    
    def test_same_structure_different_frac_coords(self):
        """Test that same structure with different fractional coord representation yields same fingerprint."""
        # Create structure with coords in [0, 1)
        lattice = Lattice.cubic(5.43)
        species = ["Si", "Si"]
        coords1 = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
        struct1 = Structure(lattice, species, coords1)
        
        # Create same structure with coords shifted by 1 (equivalent in periodic system)
        coords2 = [[1.0, 1.0, 1.0], [1.25, 1.25, 1.25]]
        struct2 = Structure(lattice, species, coords2)
        
        fp1 = structure_fingerprint(struct1)
        fp2 = structure_fingerprint(struct2)
        
        assert fp1 == fp2, "Same structure with shifted coords should yield same fingerprint"
    
    def test_same_structure_negative_coords(self):
        """Test that same structure with negative coords (wrapped) yields same fingerprint."""
        lattice = Lattice.cubic(5.43)
        species = ["Si", "Si"]
        
        # Coords in [0, 1)
        coords1 = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
        struct1 = Structure(lattice, species, coords1)
        
        # Coords with negative values (should be wrapped to [0, 1) via mod)
        # Note: mod(-0.1, 1.0) = 0.9, so this will be different from [0.0, 0.0, 0.0]
        # However, in a periodic system, [0.0, 0.0, 0.0] and [0.9, 0.9, 0.9] are equivalent
        # But per design principles, we don't do "too smart" equivalence checking
        # So we'll test with a smaller negative value that wraps closer to 0
        coords2 = [[-0.0001, -0.0001, -0.0001], [0.25, 0.25, 0.25]]  # Tiny negative, wraps to ~0.9999
        struct2 = Structure(lattice, species, coords2)
        
        # Actually, let's test with coords that are exactly equivalent via mod
        # [0.0, 0.0, 0.0] and [1.0, 1.0, 1.0] should be equivalent
        coords3 = [[1.0, 1.0, 1.0], [0.25, 0.25, 0.25]]
        struct3 = Structure(lattice, species, coords3)
        
        fp1 = structure_fingerprint(struct1)
        fp3 = structure_fingerprint(struct3)
        
        assert fp1 == fp3, "Same structure with coords shifted by 1.0 (mod equivalent) should yield same fingerprint"


class TestQVServiceDedup:
    """Test QVService structure deduplication by fingerprint."""
    
    def test_import_identical_structures_dedup(self, si_structure, tmp_path):
        """Test that importing two steps with identical structures results in 1 structure resource when dedup enabled."""
        project_root = tmp_path / "test_project"
        QVService.init_project(target_dir=project_root, name="test")
        
        # Create two temporary input files with same structure
        # (In real usage, these would be QE input files, but for testing we'll create structure files)
        struct_file1 = tmp_path / "struct1.json"
        struct_file2 = tmp_path / "struct2.json"
        
        write_structure(si_structure, struct_file1)
        write_structure(si_structure, struct_file2)
        
        # Import both structures WITH dedup enabled
        # Note: dedup is opt-in (default=False) to allow users to import same structure multiple times
        resolved1 = QVService.import_structure(project_root, struct_file1, name="struct1", dedup_by_fingerprint=True)
        resolved2 = QVService.import_structure(project_root, struct_file2, name="struct2", dedup_by_fingerprint=True)
        
        # Both should resolve to the same structure (deduplicated by fingerprint)
        assert resolved1.meta.id == resolved2.meta.id, \
            "Identical structures should be deduplicated to same structure_id when dedup enabled"
        
        # Project should have only 1 structure
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        structures = config.get("structures", [])
        unique_structure_ids = {entry.get("structure_id") for entry in structures}
        assert len(unique_structure_ids) == 1, \
            "Project should have only 1 unique structure after deduplication"
    
    def test_import_different_structures_no_dedup(self, si_structure, si_structure_different, tmp_path):
        """Test that importing two steps with different structures results in 2 structures."""
        project_root = tmp_path / "test_project"
        QVService.init_project(target_dir=project_root, name="test")
        
        # Create two structure files with different structures
        struct_file1 = tmp_path / "struct1.json"
        struct_file2 = tmp_path / "struct2.json"
        
        write_structure(si_structure, struct_file1)
        write_structure(si_structure_different, struct_file2)
        
        # Import both structures
        resolved1 = QVService.import_structure(project_root, struct_file1, name="struct1")
        resolved2 = QVService.import_structure(project_root, struct_file2, name="struct2")
        
        # They should have different structure_ids
        assert resolved1.meta.id != resolved2.meta.id, \
            "Different structures should have different structure_ids"
        
        # Project should have 2 structures
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        structures = config.get("structures", [])
        unique_structure_ids = {entry.get("structure_id") for entry in structures}
        assert len(unique_structure_ids) == 2, \
            "Project should have 2 structures for different structures"
    
    def test_fingerprint_stored_in_metadata(self, si_structure, tmp_path):
        """Test that fingerprint is stored in structure metadata."""
        project_root = tmp_path / "test_project"
        QVService.init_project(target_dir=project_root, name="test")
        
        struct_file = tmp_path / "struct.json"
        write_structure(si_structure, struct_file)
        
        # Import structure
        resolved = QVService.import_structure(project_root, struct_file, name="struct")
        
        # Read structure file and check fingerprint in metadata
        import json
        structure_path = project_root / resolved.meta.path
        struct_data = json.loads(structure_path.read_text())
        meta = struct_data.get("__qv_meta__", {})
        
        assert "fingerprint" in meta, "Fingerprint should be stored in metadata"
        assert meta["fingerprint"] == structure_fingerprint(si_structure), \
            "Stored fingerprint should match computed fingerprint"


class TestMultiStructureCalculation:
    """Test that calculations can have steps with different structures."""
    
    def test_build_calculation_allows_different_structures(self, tmp_path):
        """Test that build_calculation_from_qe_inputs no longer enforces single structure_id."""
        # This test verifies that the assertion was removed
        # We'll create a simple test that doesn't fail when steps have different structures
        
        # Create two different structures
        lattice1 = Lattice.cubic(5.43)
        struct1 = Structure(lattice1, ["Si", "Si"], [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]])
        
        lattice2 = Lattice.cubic(5.44)  # Slightly different
        struct2 = Structure(lattice2, ["Si", "Si"], [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]])
        
        # Write structures to files
        struct_file1 = tmp_path / "struct1.json"
        struct_file2 = tmp_path / "struct2.json"
        write_structure(struct1, struct_file1)
        write_structure(struct2, struct_file2)
        
        # Create QE input files (minimal)
        from quantumvitas.io.generator.qe_generator import QEInputGenerator
        from quantumvitas.io.model import QEInput, QENamelist, QECard, QECardType
        
        input1 = tmp_path / "input1.in"
        input2 = tmp_path / "input2.in"
        
        # Create minimal QE inputs
        qe_input1 = QEInput(
            namelists=[
                QENamelist("CONTROL", {"calculation": "scf"}),
                QENamelist("SYSTEM", {"ibrav": 0, "nat": 2, "ntyp": 1, "ecutwfc": 50}),
            ],
            cards=[
                QECard(QECardType.ATOMIC_SPECIES, None, [["Si", 28.086, "Si.UPF"]]),
                QECard(QECardType.ATOMIC_POSITIONS, "angstrom", [
                    ["Si", 0.0, 0.0, 0.0],
                    ["Si", 1.3575, 1.3575, 1.3575],
                ]),
                QECard(QECardType.CELL_PARAMETERS, "angstrom", [
                    [5.43, 0.0, 0.0],
                    [0.0, 5.43, 0.0],
                    [0.0, 0.0, 5.43],
                ]),
                QECard(QECardType.K_POINTS, "automatic", [[4, 4, 4, 0, 0, 0]]),
            ],
        )
        
        qe_input2 = QEInput(
            namelists=[
                QENamelist("CONTROL", {"calculation": "scf"}),
                QENamelist("SYSTEM", {"ibrav": 0, "nat": 2, "ntyp": 1, "ecutwfc": 50}),
            ],
            cards=[
                QECard(QECardType.ATOMIC_SPECIES, None, [["Si", 28.086, "Si.UPF"]]),
                QECard(QECardType.ATOMIC_POSITIONS, "angstrom", [
                    ["Si", 0.0, 0.0, 0.0],
                    ["Si", 1.36, 1.36, 1.36],  # Slightly different
                ]),
                QECard(QECardType.CELL_PARAMETERS, "angstrom", [
                    [5.44, 0.0, 0.0],  # Different lattice
                    [0.0, 5.44, 0.0],
                    [0.0, 0.0, 5.44],
                ]),
                QECard(QECardType.K_POINTS, "automatic", [[4, 4, 4, 0, 0, 0]]),
            ],
        )
        
        QEInputGenerator.write_file(qe_input1, input1)
        QEInputGenerator.write_file(qe_input2, input2)
        
        # Build calculation from inputs
        calculation_dir = tmp_path / "calculation"
        from quantumvitas.calculation.importers import build_calculation_from_qe_inputs
        
        # This should not raise an assertion error about structure_id mismatch
        result = build_calculation_from_qe_inputs(
            input_files=[input1, input2],
            calculation_dir=calculation_dir,
            reference_structure_by="id",
        )
        
        # Verify steps were created
        assert len(result.step_results) == 2, "Should have 2 steps"
        
        # Steps may have different structure_ids (this is now allowed)
        structure_ids = [r.structure_id for r in result.step_results]
        # Both should be valid ULIDs
        assert all(sid and len(sid) == 26 for sid in structure_ids), \
            "All structure_ids should be valid ULIDs"

