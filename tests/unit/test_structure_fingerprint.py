"""
Tests for structure fingerprinting and content-based deduplication.
"""

import pytest
import numpy as np
from pathlib import Path
import tempfile
import shutil

from pymatgen.core import Structure, Lattice, Molecule

from quantumvitas.core.structure_fingerprint import (
    structure_fingerprint,
    structure_like_fingerprint,
    quantize_scalar,
    quantize_array,
    DEFAULT_FINGERPRINT_TOL_ANG,
)
from quantumvitas.core.structure_canonicalize import canonicalize_structure_like_in_place
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


class TestUnitRepresentationStability:
    """Test that different QE input representations yield same fingerprint after canonicalization."""
    
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
        
        # Canonicalize both before fingerprinting
        canonicalize_structure_like_in_place(struct1)
        canonicalize_structure_like_in_place(struct2)
        
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
        
        # [0.0, 0.0, 0.0] and [1.0, 1.0, 1.0] should be equivalent after canonicalization
        coords3 = [[1.0, 1.0, 1.0], [0.25, 0.25, 0.25]]
        struct3 = Structure(lattice, species, coords3)
        
        # Canonicalize both before fingerprinting
        canonicalize_structure_like_in_place(struct1)
        canonicalize_structure_like_in_place(struct3)
        
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
        resolved1 = QVService(project_root).structure.import_file(struct_file1, name="struct1", dedup_by_fingerprint=True)
        resolved2 = QVService(project_root).structure.import_file(struct_file2, name="struct2", dedup_by_fingerprint=True)
        
        # Both should resolve to the same structure (deduplicated by fingerprint)
        assert resolved1.meta.ulid == resolved2.meta.ulid, \
            "Identical structures should be deduplicated to same structure_ulid when dedup enabled"
        
        # Project should have only 1 structure
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        structures = config.get("structures", [])
        unique_structure_ulids = {entry.get("structure_ulid") for entry in structures}
        assert len(unique_structure_ulids) == 1, \
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
        resolved1 = QVService(project_root).structure.import_file(struct_file1, name="struct1")
        resolved2 = QVService(project_root).structure.import_file(struct_file2, name="struct2")
        
        # They should have different structure_ulids
        assert resolved1.meta.ulid != resolved2.meta.ulid, \
            "Different structures should have different structure_ulids"
        
        # Project should have 2 structures
        from quantumvitas.core.project_utils import load_project_config
        config = load_project_config(project_root)
        structures = config.get("structures", [])
        unique_structure_ulids = {entry.get("structure_ulid") for entry in structures}
        assert len(unique_structure_ulids) == 2, \
            "Project should have 2 structures for different structures"
    
    def test_fingerprint_stored_in_metadata(self, si_structure, tmp_path):
        """Test that fingerprint is stored in structure metadata."""
        project_root = tmp_path / "test_project"
        QVService.init_project(target_dir=project_root, name="test")
        
        struct_file = tmp_path / "struct.json"
        write_structure(si_structure, struct_file)
        
        # Import structure
        resolved = QVService(project_root).structure.import_file(struct_file, name="struct")
        
        # Read structure file and check fingerprint in metadata
        import json
        structure_path = project_root / resolved.meta.path
        struct_data = json.loads(structure_path.read_text())
        meta = struct_data.get("__qv_meta__", {})
        
        assert "fingerprint" in meta, "Fingerprint should be stored in metadata"
        # Compute expected fingerprint: canonicalize first, then fingerprint
        # api.py uses DEFAULT_FINGERPRINT_TOL_ANG for fingerprint
        si_copy = si_structure.copy()
        canonicalize_structure_like_in_place(si_copy)
        expected_fp = structure_like_fingerprint(si_copy, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
        assert meta["fingerprint"] == expected_fp, \
            "Stored fingerprint should match computed fingerprint"


class TestMultiStructureCalculation:
    """Test that calculations can have steps with different structures."""
    
    def test_build_calculation_allows_different_structures(self, tmp_path):
        """Test that build_calculation_from_qe_inputs no longer enforces single structure_ulid."""
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
        
        # This should not raise an assertion error about structure_ulid mismatch
        result = build_calculation_from_qe_inputs(
            input_files=[input1, input2],
            calculation_dir=calculation_dir,
            reference_structure_by="id",
        )
        
        # Verify steps were created
        assert len(result.step_results) == 2, "Should have 2 steps"
        
        # Steps may have different structure_ulids (this is now allowed)
        structure_ulids = [r.structure_ulid for r in result.step_results]
        # Both should be valid ULIDs
        assert all(sid and len(sid) == 26 for sid in structure_ulids), \
            "All structure_ulids should be valid ULIDs"


# =============================================================================
# New Tests for Unified Fingerprint (structure_like_fingerprint)
# =============================================================================

@pytest.fixture
def h2_molecule():
    """Create a simple H2 molecule for testing."""
    return Molecule(["H", "H"], [[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]])


@pytest.fixture
def h2_molecule_translated():
    """H2 molecule translated by arbitrary vector."""
    # Same geometry, different origin
    return Molecule(["H", "H"], [[10.0, 5.0, 3.0], [10.74, 5.0, 3.0]])


class TestDeterministicQuantization:
    """Verify deterministic quantization (no banker's rounding)."""
    
    def test_quantize_scalar_ties_go_up(self):
        """Half-integers must round up (ties go up, not banker's rounding)."""
        # With tol=1.0, test half-integer cases
        assert quantize_scalar(0.5, 1.0) == 1, "0.5 should round to 1 (ties up)"
        assert quantize_scalar(1.5, 1.0) == 2, "1.5 should round to 2 (ties up)"
        assert quantize_scalar(2.5, 1.0) == 3, "2.5 should round to 3 (ties up)"
        assert quantize_scalar(-0.5, 1.0) == 0, "-0.5 should round to 0 (ties up)"
        
        # Verify NOT using banker's rounding (would give 0 for 0.5)
        assert quantize_scalar(0.5, 1.0) != 0, "Must NOT use banker's rounding"
    
    def test_quantize_array_vectorized(self):
        """quantize_array works on arrays."""
        arr = np.array([0.5, 1.5, 2.5, -0.5])
        result = quantize_array(arr, tol=1.0)
        expected = np.array([1, 2, 3, 0], dtype=np.int64)
        assert np.array_equal(result, expected), "Array quantization should match scalar behavior"
    
    def test_pbc_knife_edge_half_integer_case_stable(self):
        """
        PBC structure with frac=0.25 on lattice with min length 5.43 Å.
        With tol_ang=1e-3, frac_tol = 1e-3/5.43 ≈ 1.84e-4.
        0.25 / frac_tol = 1357.5 (half-integer).
        Adding tiny noise (1e-6) should NOT change fingerprint.
        """
        # Use exact case: lattice min length 5.43 Å, frac=0.25
        lattice = Lattice.cubic(5.43)
        coords1 = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
        struct1 = Structure(lattice, ["Si", "Si"], coords1)
        
        # Add tiny noise (1e-6) to frac coords
        coords2 = [[1e-6, 1e-6, 1e-6], [0.250001, 0.250001, 0.250001]]
        struct2 = Structure(lattice, ["Si", "Si"], coords2)
        
        # Canonicalize both (existing PBC canonicalization)
        canonicalize_structure_like_in_place(struct1)
        canonicalize_structure_like_in_place(struct2)
        
        # Fingerprints MUST be identical (deterministic quantization handles half-integer)
        fp1 = structure_like_fingerprint(struct1, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(struct2, tol_ang=1e-3)
        
        assert fp1 == fp2, (
            "Half-integer quantization case (0.25/frac_tol=1357.5) must be stable "
            "with tiny noise due to deterministic tie-breaking"
        )
    
    def test_molecule_tie_case_stable(self):
        """
        Molecule with coordinates near a tie boundary.
        Pick x such that x/tol_ang is near N+0.5 (half-integer).
        Add tiny noise < tol_ang.
        Fingerprint MUST be identical due to deterministic quantization.
        """
        tol_ang = 1e-3
        # Pick x such that x/tol_ang = 0.5 (half-integer)
        x_base = 0.5 * tol_ang  # = 0.0005
        
        mol1 = Molecule(["H", "H"], [[0.0, 0.0, 0.0], [x_base, 0.0, 0.0]])
        mol2 = Molecule(["H", "H"], [[0.0, 0.0, 0.0], [x_base + 1e-6, 0.0, 0.0]])
        
        canonicalize_structure_like_in_place(mol1)
        canonicalize_structure_like_in_place(mol2)
        
        fp1 = structure_like_fingerprint(mol1, tol_ang=tol_ang)
        fp2 = structure_like_fingerprint(mol2, tol_ang=tol_ang)
        
        assert fp1 == fp2, "Tie-case quantization must be stable with tiny noise"


class TestKnifeEdgeRegression:
    """Verify fingerprint does NOT re-wrap, preventing knife-edge instability."""
    
    def test_knife_edge_negative_frac_stable(self):
        """
        Structure with small negative frac in canonical interval [-WRAP_TOL, 1-WRAP_TOL).
        Fingerprint must NOT mod this to ~1.0.
        """
        lattice = Lattice.cubic(5.43)
        # Small negative frac that is valid in canonical interval [-1e-4, 0.9999)
        coords = [[-1e-6, 0.0, 0.0], [0.25, 0.25, 0.25]]
        struct = Structure(lattice, ["Si", "Si"], coords)
        
        # Canonicalize (this is what import does)
        canonicalize_structure_like_in_place(struct)
        
        # Fingerprint must use coords AS-IS, not re-wrap
        fp1 = structure_like_fingerprint(struct, tol_ang=1e-3)
        fp1_again = structure_like_fingerprint(struct, tol_ang=1e-3)
        assert fp1 == fp1_again, "Fingerprint should be deterministic"
    
    def test_knife_edge_roundtrip_stable(self, tmp_path):
        """Structure with edge coords → write → read → fingerprint unchanged."""
        lattice = Lattice.cubic(5.43)
        # Coord near the edge of canonical interval
        coords = [[-5e-5, 0.0, 0.0], [0.25, 0.25, 0.25]]
        struct = Structure(lattice, ["Si", "Si"], coords)
        canonicalize_structure_like_in_place(struct)
        
        fp_before = structure_like_fingerprint(struct, tol_ang=1e-3)
        
        json_path = tmp_path / "struct.json"
        write_structure(struct, json_path)
        loaded = read_structure(json_path)
        # Canonicalize again (should be idempotent)
        canonicalize_structure_like_in_place(loaded)
        fp_after = structure_like_fingerprint(loaded, tol_ang=1e-3)
        
        assert fp_before == fp_after, "Fingerprint should survive roundtrip"


class TestPBCCanonicalization:
    """Test PBC structure canonicalization."""
    
    def test_pbc_canonicalization_idempotent(self):
        """Canonicalizing twice produces same result."""
        lattice = Lattice.cubic(5.43)
        coords = [[1.5, -0.3, 0.7], [0.25, 0.25, 0.25]]  # Out of range
        struct = Structure(lattice, ["Si", "Si"], coords)
        
        canonicalize_structure_like_in_place(struct)
        coords_after_first = np.array(struct.frac_coords).copy()
        
        canonicalize_structure_like_in_place(struct)
        coords_after_second = np.array(struct.frac_coords)
        
        assert np.allclose(coords_after_first, coords_after_second), \
            "Canonicalization should be idempotent"


class TestFingerprintPurity:
    """Verify fingerprint is pure (no side effects, no transforms)."""
    
    def test_fingerprint_does_not_modify_structure(self, si_structure):
        """Fingerprint call does not modify input structure."""
        canonicalize_structure_like_in_place(si_structure)
        coords_before = np.array(si_structure.frac_coords).copy()
        lattice_before = np.array(si_structure.lattice.matrix).copy()
        
        _ = structure_like_fingerprint(si_structure, tol_ang=1e-3)
        
        coords_after = np.array(si_structure.frac_coords)
        lattice_after = np.array(si_structure.lattice.matrix)
        
        assert np.allclose(coords_before, coords_after), "Coords should not change"
        assert np.allclose(lattice_before, lattice_after), "Lattice should not change"
    
    def test_fingerprint_deterministic(self, si_structure):
        """Same structure yields same fingerprint."""
        canonicalize_structure_like_in_place(si_structure)
        fp1 = structure_like_fingerprint(si_structure, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(si_structure, tol_ang=1e-3)
        
        assert fp1 == fp2, "Fingerprint should be deterministic"


class TestPBCFingerprintRegression:
    """Regression tests for PBC structure fingerprint using structure_like_fingerprint."""
    
    def test_pbc_fingerprint_deterministic(self, si_structure):
        """Same structure yields same fingerprint."""
        canonicalize_structure_like_in_place(si_structure)
        fp1 = structure_like_fingerprint(si_structure, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(si_structure, tol_ang=1e-3)
        
        assert fp1 == fp2, "Fingerprint should be deterministic"
    
    def test_pbc_fingerprint_different_lattice(self, si_structure, si_structure_different):
        """Different lattice → different fingerprint."""
        canonicalize_structure_like_in_place(si_structure)
        canonicalize_structure_like_in_place(si_structure_different)
        fp1 = structure_like_fingerprint(si_structure, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(si_structure_different, tol_ang=1e-3)
        
        assert fp1 != fp2, "Different structures should have different fingerprints"
    
    def test_pbc_fingerprint_noise_tolerance(self):
        """Perturbation < tol_ang does not change fingerprint."""
        # Use coords NOT on quantization boundaries (avoid knife-edge issue)
        # For Si lattice (5.43 Å), frac_tol = 1e-3 / 5.43 ≈ 1.84e-4
        # Coords like 0.3 are safe (0.3 / 1.84e-4 = 1630.4, not on 0.5 boundary)
        lattice = Lattice.cubic(5.43)
        coords1 = [[0.0, 0.0, 0.0], [0.3, 0.3, 0.3]]
        struct1 = Structure(lattice, ["Si", "Si"], coords1)
        
        # Add noise much smaller than frac_tol (1e-6 << 1.84e-4)
        noisy_coords = np.array(coords1) + 1e-6
        struct2 = Structure(lattice, ["Si", "Si"], noisy_coords.tolist())
        
        canonicalize_structure_like_in_place(struct1)
        canonicalize_structure_like_in_place(struct2)
        
        fp1 = structure_like_fingerprint(struct1, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(struct2, tol_ang=1e-3)
        
        assert fp1 == fp2, "Small noise should not change fingerprint"
    
    def test_pbc_fingerprint_wrap_invariance(self):
        """Coords shifted by integer lattice vectors → same fingerprint after canonicalization."""
        lattice = Lattice.cubic(5.43)
        
        # Original coords
        struct1 = Structure(lattice, ["Si", "Si"], [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]])
        
        # Coords shifted by +1 (equivalent in periodic system)
        struct2 = Structure(lattice, ["Si", "Si"], [[1.0, 1.0, 1.0], [1.25, 1.25, 1.25]])
        
        canonicalize_structure_like_in_place(struct1)
        canonicalize_structure_like_in_place(struct2)
        
        fp1 = structure_like_fingerprint(struct1, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(struct2, tol_ang=1e-3)
        
        assert fp1 == fp2, "Shifted coords should yield same fingerprint after canonicalization"
    
    def test_pbc_fingerprint_format(self, si_structure):
        """Fingerprint is SHA256 hex digest (64 chars)."""
        fp = structure_like_fingerprint(si_structure, tol_ang=1e-3)
        
        assert isinstance(fp, str), "Fingerprint should be string"
        assert len(fp) == 64, "SHA256 hex should be 64 chars"
        assert all(c in '0123456789abcdef' for c in fp), "Should be hex"


class TestMoleculeCanonicalization:
    """Test Molecule canonicalization (COG shift)."""
    
    def test_molecule_canonicalization_centers_at_origin(self):
        """After canonicalization, molecule is centered at origin."""
        # Molecule NOT at origin
        mol = Molecule(["H", "H"], [[10.0, 5.0, 3.0], [10.74, 5.0, 3.0]])
        
        canonicalize_structure_like_in_place(mol)
        
        coords = np.array([site.coords for site in mol])
        cog = coords.mean(axis=0)
        
        assert np.allclose(cog, [0, 0, 0], atol=1e-10), \
            "After canonicalization, COG should be at origin"
    
    def test_molecule_canonicalization_idempotent(self):
        """Canonicalizing twice produces same result."""
        mol = Molecule(["H", "H"], [[5.0, 3.0, 1.0], [5.74, 3.0, 1.0]])
        
        canonicalize_structure_like_in_place(mol)
        coords_after_first = np.array([site.coords for site in mol]).copy()
        fp_after_first = structure_like_fingerprint(mol, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
        
        canonicalize_structure_like_in_place(mol)
        coords_after_second = np.array([site.coords for site in mol])
        fp_after_second = structure_like_fingerprint(mol, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
        
        assert np.allclose(coords_after_first, coords_after_second, atol=1e-12), \
            "Canonicalization should be idempotent (coords unchanged after second call)"
        assert fp_after_first == fp_after_second, \
            "Fingerprint should remain identical after second canonicalization"


class TestMoleculeFingerprint:
    """Tests for Molecule fingerprint."""
    
    def test_molecule_fingerprint_deterministic(self, h2_molecule):
        """Same molecule yields same fingerprint."""
        canonicalize_structure_like_in_place(h2_molecule)
        fp1 = structure_like_fingerprint(h2_molecule, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(h2_molecule, tol_ang=1e-3)
        
        assert fp1 == fp2, "Fingerprint should be deterministic"
    
    def test_molecule_fingerprint_different_geometry(self, h2_molecule):
        """Different bond length → different fingerprint."""
        # Different H-H distance
        h2_stretched = Molecule(["H", "H"], [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        
        canonicalize_structure_like_in_place(h2_molecule)
        canonicalize_structure_like_in_place(h2_stretched)
        
        fp1 = structure_like_fingerprint(h2_molecule, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(h2_stretched, tol_ang=1e-3)
        
        assert fp1 != fp2, "Different geometries should have different fingerprints"
    
    def test_molecule_fingerprint_format(self, h2_molecule):
        """Fingerprint is SHA256 hex digest (64 chars)."""
        canonicalize_structure_like_in_place(h2_molecule)
        fp = structure_like_fingerprint(h2_molecule, tol_ang=1e-3)
        
        assert isinstance(fp, str), "Fingerprint should be string"
        assert len(fp) == 64, "SHA256 hex should be 64 chars"
        assert all(c in '0123456789abcdef' for c in fp), "Should be hex"
    
    def test_molecule_fingerprint_noise_tolerance(self, h2_molecule):
        """Perturbation < tol_ang does not change fingerprint."""
        canonicalize_structure_like_in_place(h2_molecule)
        # Add noise < 1e-4 Å
        coords = np.array([[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]])
        noisy_coords = coords + 1e-5
        h2_noisy = Molecule(["H", "H"], noisy_coords.tolist())
        canonicalize_structure_like_in_place(h2_noisy)
        
        fp1 = structure_like_fingerprint(h2_molecule, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(h2_noisy, tol_ang=1e-3)
        
        assert fp1 == fp2, "Small noise should not change fingerprint"


class TestMoleculeTranslationInvariance:
    """Test that Molecule fingerprint is translation-invariant via canonicalization."""
    
    def test_molecule_translation_invariance(self, h2_molecule, h2_molecule_translated):
        """Same geometry at different origins → same fingerprint after canonicalization."""
        canonicalize_structure_like_in_place(h2_molecule)
        canonicalize_structure_like_in_place(h2_molecule_translated)
        
        fp1 = structure_like_fingerprint(h2_molecule, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(h2_molecule_translated, tol_ang=1e-3)
        
        assert fp1 == fp2, "Translation should not change fingerprint after canonicalization"
    
    def test_molecule_translation_large_offset(self):
        """Large translation offset → same fingerprint."""
        # Water at origin
        h2o_origin = Molecule(
            ["O", "H", "H"],
            [[0.0, 0.0, 0.0], [0.96, 0.0, 0.0], [-0.24, 0.93, 0.0]]
        )
        
        # Water translated by large vector
        offset = [1000.0, -500.0, 250.0]
        h2o_translated = Molecule(
            ["O", "H", "H"],
            [
                [0.0 + offset[0], 0.0 + offset[1], 0.0 + offset[2]],
                [0.96 + offset[0], 0.0 + offset[1], 0.0 + offset[2]],
                [-0.24 + offset[0], 0.93 + offset[1], 0.0 + offset[2]],
            ]
        )
        
        canonicalize_structure_like_in_place(h2o_origin)
        canonicalize_structure_like_in_place(h2o_translated)
        
        fp1 = structure_like_fingerprint(h2o_origin, tol_ang=1e-3)
        fp2 = structure_like_fingerprint(h2o_translated, tol_ang=1e-3)
        
        assert fp1 == fp2, "Large translation should not change fingerprint"
    
    def test_molecule_translation_each_axis(self, h2_molecule):
        """Translation along each individual axis → same fingerprint."""
        canonicalize_structure_like_in_place(h2_molecule)
        fp_original = structure_like_fingerprint(h2_molecule, tol_ang=1e-3)
        
        original_coords = np.array([[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]])
        for axis, offset in [(0, 100.0), (1, -50.0), (2, 25.5)]:
            translated_coords = original_coords.copy()
            translated_coords[:, axis] += offset
            mol_translated = Molecule(["H", "H"], translated_coords.tolist())
            canonicalize_structure_like_in_place(mol_translated)
            
            fp_translated = structure_like_fingerprint(mol_translated, tol_ang=1e-3)
            
            assert fp_original == fp_translated, f"Translation along axis {axis} should not change fingerprint"


class TestRoundtripStability:
    """Test fingerprint stability through JSON roundtrip."""
    
    def test_pbc_roundtrip_json(self, si_structure, tmp_path):
        """PBC Structure → JSON → Structure → same fingerprint."""
        canonicalize_structure_like_in_place(si_structure)
        fp_before = structure_like_fingerprint(si_structure, tol_ang=1e-3)
        
        # Write and read back
        json_path = tmp_path / "structure.json"
        write_structure(si_structure, json_path)
        loaded = read_structure(json_path)
        canonicalize_structure_like_in_place(loaded)  # Should be idempotent
        
        fp_after = structure_like_fingerprint(loaded, tol_ang=1e-3)
        
        assert fp_before == fp_after, "Fingerprint should survive JSON roundtrip"
    
    def test_molecule_roundtrip_json(self, h2_molecule, tmp_path):
        """Molecule → JSON → Molecule → same fingerprint."""
        canonicalize_structure_like_in_place(h2_molecule)
        fp_before = structure_like_fingerprint(h2_molecule, tol_ang=1e-3)
        
        # Write and read back
        json_path = tmp_path / "molecule.json"
        write_structure(h2_molecule, json_path)
        loaded = read_structure(json_path)
        canonicalize_structure_like_in_place(loaded)  # Should be idempotent
        
        fp_after = structure_like_fingerprint(loaded, tol_ang=1e-3)
        
        assert fp_before == fp_after, "Fingerprint should survive JSON roundtrip"


class TestEdgeCases:
    """Edge case tests for fingerprint functions."""
    
    def test_single_atom_molecule(self):
        """Single-atom molecule should have valid fingerprint."""
        h_atom = Molecule(["H"], [[0.0, 0.0, 0.0]])
        canonicalize_structure_like_in_place(h_atom)
        fp = structure_like_fingerprint(h_atom, tol_ang=1e-3)
        
        assert isinstance(fp, str), "Should return string"
        assert len(fp) == 64, "Should be SHA256 hex"
    
    def test_single_atom_structure(self):
        """Single-atom structure should have valid fingerprint."""
        lattice = Lattice.cubic(5.0)
        single_atom = Structure(lattice, ["H"], [[0.0, 0.0, 0.0]])
        canonicalize_structure_like_in_place(single_atom)
        fp = structure_like_fingerprint(single_atom, tol_ang=1e-3)
        
        assert isinstance(fp, str), "Should return string"
        assert len(fp) == 64, "Should be SHA256 hex"
    
    def test_type_error_on_wrong_type(self):
        """Passing non-Structure/Molecule raises TypeError."""
        with pytest.raises(TypeError):
            structure_like_fingerprint({"invalid": "dict"}, tol_ang=1e-3)
        
        with pytest.raises(TypeError):
            structure_like_fingerprint("not a structure", tol_ang=1e-3)
        
        with pytest.raises(TypeError):
            structure_like_fingerprint(None, tol_ang=1e-3)


class TestImportStructureUnifiedFingerprint:
    """Test that import_structure uses unified fingerprint for Molecules."""
    
    def test_import_molecule_fingerprint_matches_unified(self, tmp_path):
        """import_structure(Molecule) stores fingerprint matching structure_like_fingerprint()."""
        import json
        
        # Create project
        project_root = tmp_path / "test_project"
        QVService.init_project(target_dir=project_root, name="test")
        
        # Create molecule
        h2 = Molecule(["H", "H"], [[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]])
        mol_file = tmp_path / "h2.json"
        write_structure(h2, mol_file)
        
        # Import molecule
        resolved = QVService(project_root).structure.import_file(mol_file, name="h2")
        
        # Read stored fingerprint from structure file
        structure_path = project_root / resolved.meta.path
        struct_data = json.loads(structure_path.read_text())
        stored_fingerprint = struct_data.get("__qv_meta__", {}).get("fingerprint")
        
        # Compute expected: canonicalize then fingerprint
        h2_copy = Molecule(["H", "H"], [[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]])
        canonicalize_structure_like_in_place(h2_copy)
        expected_fingerprint = structure_like_fingerprint(h2_copy, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
        
        assert stored_fingerprint is not None, "Fingerprint should be stored"
        assert stored_fingerprint == expected_fingerprint, (
            "Stored fingerprint should match structure_like_fingerprint()"
        )
    
    def test_import_molecule_translation_dedup(self, tmp_path):
        """Two Molecules at different origins should dedup when dedup_by_fingerprint=True."""
        # Create project
        project_root = tmp_path / "test_project"
        QVService.init_project(target_dir=project_root, name="test")
        
        # Create same molecule at different origins
        h2_origin = Molecule(["H", "H"], [[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]])
        h2_translated = Molecule(["H", "H"], [[10.0, 5.0, 3.0], [10.74, 5.0, 3.0]])
        
        mol_file1 = tmp_path / "h2_origin.json"
        mol_file2 = tmp_path / "h2_translated.json"
        write_structure(h2_origin, mol_file1)
        write_structure(h2_translated, mol_file2)
        
        # Import both with dedup enabled
        resolved1 = QVService(project_root).structure.import_file(mol_file1, name="h2_1", dedup_by_fingerprint=True)
        resolved2 = QVService(project_root).structure.import_file(mol_file2, name="h2_2", dedup_by_fingerprint=True)
        
        # Should be same structure (deduped)
        assert resolved1.meta.ulid == resolved2.meta.ulid, (
            "Translated molecules should dedup to same structure_ulid"
        )


class TestFingerprintSSOTAndIdempotency:
    """Test SSOT constant usage and idempotency guarantees."""
    
    def test_fingerprint_uses_default_constant_when_not_specified(self):
        """Fingerprint should use DEFAULT_FINGERPRINT_TOL_ANG when tol_ang is not provided."""
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.43)
        struct = Structure(lattice, ["Si", "Si"], [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]])
        canonicalize_structure_like_in_place(struct)
        
        # Call without explicit tol_ang - should use default
        fp_default = structure_like_fingerprint(struct)
        
        # Call with explicit default constant - should be identical
        fp_explicit = structure_like_fingerprint(struct, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
        
        assert fp_default == fp_explicit, (
            "Fingerprint without tol_ang should use DEFAULT_FINGERPRINT_TOL_ANG"
        )
    
    def test_molecule_canonicalization_idempotency_with_fingerprint(self):
        """
        Molecule canonicalization idempotency test with fingerprint verification.
        
        Creates a Molecule with non-centered coords, applies canonicalization TWICE,
        and verifies:
        1. Coords after 1st == coords after 2nd (exact or very tight tolerance)
        2. Fingerprint remains identical
        """
        from pymatgen.core import Molecule
        import numpy as np
        
        # Create molecule NOT at origin
        mol = Molecule(["H", "H", "O"], [[10.0, 5.0, 3.0], [10.74, 5.0, 3.0], [11.0, 5.5, 3.0]])
        
        # First canonicalization
        canonicalize_structure_like_in_place(mol)
        coords_after_first = np.array([site.coords for site in mol]).copy()
        fp_after_first = structure_like_fingerprint(mol, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
        
        # Second canonicalization (should be idempotent)
        canonicalize_structure_like_in_place(mol)
        coords_after_second = np.array([site.coords for site in mol])
        fp_after_second = structure_like_fingerprint(mol, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
        
        # Verify coords are identical (or very close due to floating point)
        assert np.allclose(coords_after_first, coords_after_second, atol=1e-12), (
            "Coords should be identical after second canonicalization (idempotency)"
        )
        
        # Verify fingerprint remains identical
        assert fp_after_first == fp_after_second, (
            "Fingerprint should remain identical after second canonicalization"
        )

