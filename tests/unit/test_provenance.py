"""Tests for provenance tracking."""
import pytest
from pathlib import Path

from quantumvitas.core.provenance import (
    ProvenanceMap,
    ProvenanceEntry,
    load_provenance,
    save_provenance,
    update_provenance_after_step,
    get_file_provenance,
)


class TestProvenanceMap:
    def test_empty_provenance(self, tmp_path):
        """Loading non-existent provenance returns empty map."""
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        prov = load_provenance(calc_dir)
        
        assert prov.files == {}
    
    def test_save_and_load(self, tmp_path):
        """Test save and load round-trip."""
        calc_dir = tmp_path / "calc"
        calc_dir.mkdir()
        
        prov = ProvenanceMap()
        prov.files["raw/scf.out"] = ProvenanceEntry(
            run_id="01JTEST",
            step_ulid="01JSTEP",
            produced_at="2026-01-19T10:00:00Z",
            size_bytes=1234,
            mtime=12345.0,
        )
        
        save_provenance(calc_dir, prov)
        loaded = load_provenance(calc_dir)
        
        assert "raw/scf.out" in loaded.files
        assert loaded.files["raw/scf.out"].run_id == "01JTEST"


class TestUpdateProvenance:
    def test_tracks_new_files(self, tmp_path):
        """Provenance tracks newly created files."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Create a file
        (raw_dir / "scf.out").write_text("output")
        
        # Update provenance
        changes = update_provenance_after_step(
            calc_dir=calc_dir,
            run_id="01JRUN1",
            step_ulid="01JSTEP1",
            engine="qe",
        )
        
        assert "raw/scf.out" in changes
        assert changes["raw/scf.out"] == "added"
        
        # Check provenance
        entry = get_file_provenance(calc_dir, "raw/scf.out")
        assert entry is not None
        assert entry.run_id == "01JRUN1"
    
    def test_tracks_modified_files(self, tmp_path):
        """Provenance updates when files are modified."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Create file
        test_file = raw_dir / "scf.out"
        test_file.write_text("output1")
        
        # First update
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        # Modify file
        test_file.write_text("output2 - modified")
        
        # Second update
        changes = update_provenance_after_step(calc_dir, "01JRUN2", "01JSTEP2", "qe")
        
        assert "raw/scf.out" in changes
        assert changes["raw/scf.out"] == "modified"
        
        entry = get_file_provenance(calc_dir, "raw/scf.out")
        assert entry.run_id == "01JRUN2"
    
    def test_ignores_outdir(self, tmp_path):
        """QE outdir/ is now tracked by provenance (philosophy change)."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        outdir = raw_dir / "outdir"
        outdir.mkdir(parents=True)
        
        # Create files
        (raw_dir / "scf.out").write_text("output")
        (outdir / "pwscf.save").write_text("save data")
        
        # Update
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        # Check - both are now tracked (provenance tracks ALL files)
        prov = load_provenance(calc_dir)
        assert "raw/scf.out" in prov.files
        # outdir is now tracked
        assert any("outdir" in p for p in prov.files)


class TestProvenanceScansAllFiles:
    """Provenance should track all files, including CHGCAR and outdir."""
    
    def test_provenance_tracks_chgcar(self, tmp_path):
        """CHGCAR should be tracked even for VASP engine."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Create CHGCAR (would be ignored by analysis scanning)
        (raw_dir / "CHGCAR").write_text("charge density")
        (raw_dir / "OUTCAR").write_text("output")
        
        # Update provenance with VASP engine
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "vasp")
        
        # Both files should be tracked
        prov = load_provenance(calc_dir)
        assert "raw/CHGCAR" in prov.files
        assert "raw/OUTCAR" in prov.files
    
    def test_provenance_tracks_qe_outdir(self, tmp_path):
        """Provenance now tracks outdir files too (for complete artifact tracking)."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        outdir = raw_dir / "outdir"
        outdir.mkdir(parents=True)
        
        # Create files
        (raw_dir / "scf.out").write_text("output")
        (outdir / "pwscf.save").write_text("save data")
        
        # Update
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        # Check - both are now tracked
        prov = load_provenance(calc_dir)
        assert "raw/scf.out" in prov.files
        assert any("outdir" in p for p in prov.files)  # Now tracked!
    
    def test_provenance_respects_additional_ignore(self, tmp_path):
        """User-configured ignore patterns are still respected."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        (raw_dir / "scf.out").write_text("output")
        (raw_dir / "test.tmp").write_text("temp")
        
        # Ignore *.tmp via additional_ignore
        update_provenance_after_step(
            calc_dir, "01JRUN1", "01JSTEP1", "qe",
            additional_ignore=["*.tmp"]
        )
        
        prov = load_provenance(calc_dir)
        assert "raw/scf.out" in prov.files
        assert "raw/test.tmp" not in prov.files  # Ignored by user config
    
    def test_provenance_restart_consistency(self, tmp_path):
        """After restart, new files get correct attribution."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        # Step 1
        (raw_dir / "scf.out").write_text("step1")
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP1", "qe")
        
        # Simulate restart by reloading
        prov1 = load_provenance(calc_dir)
        assert prov1.files["raw/scf.out"].step_ulid == "01JSTEP1"
        
        # Step 2 (after restart)
        (raw_dir / "bands.out").write_text("step2")
        update_provenance_after_step(calc_dir, "01JRUN1", "01JSTEP2", "qe")
        
        # Check attribution
        prov2 = load_provenance(calc_dir)
        assert prov2.files["raw/scf.out"].step_ulid == "01JSTEP1"  # Unchanged
        assert prov2.files["raw/bands.out"].step_ulid == "01JSTEP2"  # New

