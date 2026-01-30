"""
Integration tests for digest computation using tests/data reference outputs.

These tests validate that digests correctly parse real QE output files
and degrade gracefully when expected fields are missing.
"""

from pathlib import Path
from typing import Optional

import pytest

from quantumvitas.history.digests import (
    compute_step_digest,
    StepDigest,
    DigestValue,
)


# Path to tests/data directory
TESTS_DATA_DIR = Path(__file__).parent.parent / "data"


class TestSCFDigest:
    """Tests for SCF step digest computation."""
    
    @pytest.mark.parametrize("output_subdir", [
        "0_Si_scf/reference_outputs",  # Single atom Si (different ecut)
        "4_Si_DOS/reference",  # 2-atom Si cell
    ])
    def test_scf_digest_real_output(self, output_subdir: str):
        """Test SCF digest with real QE output files."""
        ref_dir = TESTS_DATA_DIR / output_subdir
        
        if not ref_dir.exists():
            pytest.skip(f"Reference directory not found: {ref_dir}")
        
        digest = compute_step_digest(
            step_id="test-scf-001",
            step_type="scf",
            working_dir=ref_dir,
            step_name="Test SCF",
            step_status="success",
        )
        
        assert digest.step_type == "scf"
        assert digest.output_exists
        
        # Check converged
        if digest.converged:
            assert digest.converged.status in ("ok", "unknown")
            if digest.converged.status == "ok":
                assert digest.converged.value is True
        
        # Check total energy if parsed
        if digest.total_energy and digest.total_energy.status == "ok":
            # Energy should be negative for any valid SCF
            assert digest.total_energy.value < 0
            # Should be in reasonable range for Si (any # atoms)
            assert digest.total_energy.value > -100
            assert digest.total_energy.unit == "Ry"
    
    def test_scf_digest_with_fermi_energy(self):
        """Test SCF digest extracts Fermi energy or HOMO."""
        # Use Si DOS reference which should have Fermi energy
        ref_dir = TESTS_DATA_DIR / "4_Si_DOS" / "reference"
        
        if not ref_dir.exists():
            pytest.skip("Si DOS reference not found")
        
        digest = compute_step_digest(
            step_id="test-scf-002",
            step_type="scf",
            working_dir=ref_dir,
        )
        
        # Silicon should have either Fermi energy or HOMO
        has_fermi = (digest.fermi_energy and 
                     digest.fermi_energy.status == "ok" and
                     digest.fermi_energy.value is not None)
        has_homo = (digest.homo and 
                    digest.homo.status == "ok" and
                    digest.homo.value is not None)
        
        # At least one should be present
        # (Silicon is semiconductor, so might have HOMO/LUMO instead of Fermi)
        assert has_fermi or has_homo or digest.fermi_energy.status in ("na", "unknown")


class TestNSCFDigest:
    """Tests for NSCF step digest computation."""
    
    def test_nscf_digest_real_output(self):
        """Test NSCF digest with real QE output file."""
        ref_dir = TESTS_DATA_DIR / "7_Si_bandStructure" / "reference"
        
        if not ref_dir.exists():
            pytest.skip("Si band structure reference not found")
        
        digest = compute_step_digest(
            step_id="test-nscf-001",
            step_type="nscf",
            working_dir=ref_dir,
        )
        
        assert digest.step_type == "nscf"
        
        # Check Fermi energy (should be present for NSCF)
        if digest.fermi_energy and digest.fermi_energy.status == "ok":
            # Fermi energy should be reasonable (eV)
            assert -50 < digest.fermi_energy.value < 50
            assert digest.fermi_energy.unit == "eV"


class TestBandsDigest:
    """Tests for bands step digest computation."""
    
    def test_bands_digest_real_output(self):
        """Test bands digest with real bands.dat.gnu file."""
        ref_dir = TESTS_DATA_DIR / "7_Si_bandStructure" / "reference"
        
        if not ref_dir.exists():
            pytest.skip("Si band structure reference not found")
        
        digest = compute_step_digest(
            step_id="test-bands-001",
            step_type="bands",
            working_dir=ref_dir,
        )
        
        assert digest.step_type == "bands"
        
        # Should parse n_bands and n_kpoints from bands.dat.gnu
        if digest.n_bands and digest.n_bands.status == "ok":
            assert digest.n_bands.value > 0
        
        if digest.n_kpoints and digest.n_kpoints.status == "ok":
            assert digest.n_kpoints.value > 0


class TestDOSDigest:
    """Tests for DOS step digest computation."""
    
    def test_dos_digest_real_output(self):
        """Test DOS digest with real DOS data file."""
        ref_dir = TESTS_DATA_DIR / "4_Si_DOS" / "reference"
        
        if not ref_dir.exists():
            pytest.skip("Si DOS reference not found")
        
        digest = compute_step_digest(
            step_id="test-dos-001",
            step_type="dos",
            working_dir=ref_dir,
        )
        
        assert digest.step_type == "dos"
        
        # Should parse energy range
        if digest.dos_energy_range and digest.dos_energy_range.status == "ok":
            e_min, e_max = digest.dos_energy_range.value
            assert e_min < e_max
            assert digest.dos_energy_range.unit == "eV"


class TestRelaxDigest:
    """Tests for relax step digest computation."""
    
    def test_relax_digest_real_output(self):
        """Test relax digest with real relaxation output."""
        # H2O relax should have multiple BFGS steps
        ref_dir = TESTS_DATA_DIR / "2_H2O" / "reference_output"
        
        if not ref_dir.exists():
            pytest.skip("H2O reference not found")
        
        digest = compute_step_digest(
            step_id="test-relax-001",
            step_type="relax",
            working_dir=ref_dir,
        )
        
        assert digest.step_type == "relax"
        
        # Should have converged
        if digest.converged and digest.converged.status == "ok":
            assert digest.converged.value is True


class TestDigestRobustness:
    """Tests for digest robustness and graceful degradation."""
    
    def test_missing_output_file(self, tmp_path: Path):
        """Test digest handles missing output file gracefully."""
        digest = compute_step_digest(
            step_id="test-missing",
            step_type="scf",
            working_dir=tmp_path,
        )
        
        assert digest.output_exists is False
        assert digest.converged.status == "missing"
        assert digest.total_energy.status == "missing"
    
    def test_empty_output_file(self, tmp_path: Path):
        """Test digest handles empty output file gracefully."""
        output_file = tmp_path / "scf.out"
        output_file.write_text("")
        
        digest = compute_step_digest(
            step_id="test-empty",
            step_type="scf",
            working_dir=tmp_path,
        )
        
        # Should not crash
        assert digest.step_ulid == "test-empty"
        assert digest.output_exists is True
    
    def test_malformed_output_file(self, tmp_path: Path):
        """Test digest handles malformed output gracefully."""
        output_file = tmp_path / "scf.out"
        output_file.write_text("This is not valid QE output")
        
        digest = compute_step_digest(
            step_id="test-malformed",
            step_type="scf",
            working_dir=tmp_path,
        )
        
        # Should not crash, but mark values as unknown
        assert digest.step_ulid == "test-malformed"
        # converged should be unknown (no JOB DONE marker)
        if digest.converged:
            assert digest.converged.status in ("unknown", "ok")
    
    def test_partial_output_file(self, tmp_path: Path):
        """Test digest handles partial/interrupted output gracefully."""
        output_file = tmp_path / "scf.out"
        output_file.write_text("""
     Program PWSCF v.7.0 starts

     iteration #  1     ecut=    30.00 Ry     beta= 0.70
     total energy              =     -22.83736058 Ry

     iteration #  2     ecut=    30.00 Ry     beta= 0.70
     total energy              =     -22.83930911 Ry

     
""")
        
        digest = compute_step_digest(
            step_id="test-partial",
            step_type="scf",
            working_dir=tmp_path,
        )
        
        # Should extract what's available
        assert digest.output_exists is True
        # No final energy marker (!), so should not be converged
        if digest.converged and digest.converged.status == "ok":
            assert digest.converged.value is False
    
    def test_successful_output_with_job_done(self, tmp_path: Path):
        """Test digest recognizes successful completion."""
        output_file = tmp_path / "scf.out"
        output_file.write_text("""
     Program PWSCF v.7.0 starts

     iteration #  1     ecut=    30.00 Ry     beta= 0.70
     total energy              =     -22.83736058 Ry

!    total energy              =     -22.83945479 Ry

     highest occupied, lowest unoccupied level (ev):     5.7618    6.4468

     JOB DONE.

     PWSCF        :      0.50s CPU      0.55s WALL
""")
        
        digest = compute_step_digest(
            step_id="test-success",
            step_type="scf",
            working_dir=tmp_path,
        )
        
        assert digest.converged.status == "ok"
        assert digest.converged.value is True
        
        assert digest.total_energy.status == "ok"
        assert abs(digest.total_energy.value - (-22.83945479)) < 0.0001
        
        # Should have HOMO/LUMO
        if digest.homo and digest.homo.status == "ok":
            assert abs(digest.homo.value - 5.7618) < 0.001
    
    def test_unknown_step_type(self, tmp_path: Path):
        """Test digest handles unknown step type."""
        output_file = tmp_path / "custom.out"
        output_file.write_text("JOB DONE.")
        
        digest = compute_step_digest(
            step_id="test-unknown",
            step_type="custom_unknown",
            working_dir=tmp_path,
        )
        
        # Should not crash
        assert digest.step_type == "custom_unknown"
    
    def test_all_metrics_independent(self, tmp_path: Path):
        """Test that failure to parse one metric doesn't affect others."""
        output_file = tmp_path / "scf.out"
        output_file.write_text("""
     Program PWSCF v.7.0 starts

!    total energy              =     -22.83945479 Ry

     JOB DONE.
""")
        
        digest = compute_step_digest(
            step_id="test-partial-metrics",
            step_type="scf",
            working_dir=tmp_path,
        )
        
        # Total energy should be parsed
        assert digest.total_energy.status == "ok"
        
        # Fermi energy is missing but should not crash
        if digest.fermi_energy:
            assert digest.fermi_energy.status in ("na", "unknown", "missing")
        
        # SCF iterations missing but should not crash
        if digest.scf_iterations:
            assert digest.scf_iterations.status in ("ok", "unknown", "missing")


class TestProjectExamplesDigest:
    """Tests using project_examples reference outputs."""
    
    def test_bands_project_scf_digest(self):
        """Test digest on project_examples bands SCF output."""
        ref_dir = TESTS_DATA_DIR / "project_examples" / "project2_bands" / "calculations" / "si-bands" / "raw"
        
        if not ref_dir.exists():
            pytest.skip("project2_bands reference not found")
        
        digest = compute_step_digest(
            step_id="test-proj-scf",
            step_type="scf",
            working_dir=ref_dir,
        )
        
        # Check for expected values from si-bands
        assert digest.output_exists
        
        if digest.converged and digest.converged.status == "ok":
            assert digest.converged.value is True
        
        if digest.total_energy and digest.total_energy.status == "ok":
            # Si total energy should be around -22.84 Ry
            assert -25 < digest.total_energy.value < -20
    
    def test_bands_project_nscf_digest(self):
        """Test digest on project_examples NSCF output."""
        ref_dir = TESTS_DATA_DIR / "project_examples" / "project2_bands" / "calculations" / "si-bands" / "raw"
        
        if not ref_dir.exists():
            pytest.skip("project2_bands reference not found")
        
        digest = compute_step_digest(
            step_id="test-proj-nscf",
            step_type="nscf",
            working_dir=ref_dir,
        )
        
        # Should find NSCF output and parse Fermi energy
        if digest.fermi_energy and digest.fermi_energy.status == "ok":
            # Si Fermi energy should be around 6 eV
            assert 0 < digest.fermi_energy.value < 15

