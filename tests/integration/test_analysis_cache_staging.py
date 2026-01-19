"""
Integration tests for analysis cache with staging compatibility.

Tests that provenance is updated correctly after staging operations.
"""
import pytest
from pathlib import Path
import shutil

from quantumvitas.core.provenance import (
    update_provenance_after_step,
    load_provenance,
)


class TestProvenanceStagingCompatibility:
    """Test provenance tracks staged files correctly."""
    
    def test_provenance_after_staging_chgcar(self, tmp_path):
        """
        Simulate: step1 creates CHGCAR, step2 staging copies it.
        Provenance should track final locations.
        """
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        step1_dir = raw_dir / "step1"
        step2_dir = raw_dir / "step2"
        step1_dir.mkdir(parents=True)
        step2_dir.mkdir(parents=True)
        
        # Step 1: Create CHGCAR
        (step1_dir / "OUTCAR").write_text("step1 output")
        (step1_dir / "CHGCAR").write_text("charge density")
        
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "vasp")
        
        # Simulate staging: copy CHGCAR to step2
        shutil.copy(step1_dir / "CHGCAR", step2_dir / "CHGCAR")
        (step2_dir / "OUTCAR").write_text("step2 output")
        
        # Update provenance after step2 (which includes staging)
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP2", "vasp")
        
        # Check: both CHGCARs are tracked
        prov = load_provenance(calc_dir)
        
        assert "raw/step1/CHGCAR" in prov.files
        assert "raw/step2/CHGCAR" in prov.files
        
        # step2 CHGCAR should be attributed to step2
        assert prov.files["raw/step2/CHGCAR"].step_ulid == "01JSTEP2"
    
    def test_provenance_updated_after_staging_not_before(self, tmp_path):
        """
        Provenance update occurs after staging completes.
        Files that don't exist yet shouldn't appear in provenance.
        """
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Initial state: no files
        prov = load_provenance(calc_dir)
        assert len(prov.files) == 0
        
        # Simulate step execution
        (raw_dir / "scf.out").write_text("output")
        
        # Update provenance
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        prov = load_provenance(calc_dir)
        assert "raw/scf.out" in prov.files

