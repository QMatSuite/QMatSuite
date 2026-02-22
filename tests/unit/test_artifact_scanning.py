"""Tests for artifact scanning."""
import pytest
from pathlib import Path

from qmatsuite.core.artifact_scanning import (
    scan_directory,
    scan_raw_directory,
    scan_raw_directory_for_provenance,
    should_ignore,
    get_engine_ignore_patterns,
)


class TestPathNormalization:
    """Paths should use POSIX separators."""
    
    def test_scan_returns_posix_paths(self, tmp_path):
        """Scanned paths use forward slashes."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "file.txt").write_text("content")
        
        result = scan_directory(subdir, base_dir=tmp_path)
        
        # Path should be POSIX (forward slashes)
        assert "subdir/file.txt" in result
        assert "\\" not in result["subdir/file.txt"].relative_path


class TestIgnorePatterns:
    """Engine ignore patterns work correctly."""
    
    def test_vasp_ignores_wavecar(self):
        patterns = get_engine_ignore_patterns("vasp")
        assert should_ignore("WAVECAR", patterns)
    
    def test_vasp_ignores_chgcar_for_analysis(self):
        """CHGCAR is ignored for analysis (performance)."""
        patterns = get_engine_ignore_patterns("vasp")
        assert should_ignore("CHGCAR", patterns)
    
    def test_qe_ignores_outdir(self):
        patterns = get_engine_ignore_patterns("qe")
        assert should_ignore("outdir/pwscf.save", patterns)


class TestProvenanceScanning:
    """Provenance scanning tracks all files."""
    
    def test_provenance_scan_no_engine_patterns(self, tmp_path):
        """Provenance scan does not apply engine ignore patterns."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        (raw_dir / "CHGCAR").write_text("charge")
        (raw_dir / "WAVECAR").write_text("wave")
        
        # Provenance scanning should include CHGCAR and WAVECAR
        result = scan_raw_directory_for_provenance(calc_dir)
        
        assert "raw/CHGCAR" in result
        assert "raw/WAVECAR" in result
    
    def test_analysis_scan_uses_engine_patterns(self, tmp_path):
        """Analysis scan applies engine ignore patterns."""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        (raw_dir / "CHGCAR").write_text("charge")
        (raw_dir / "OUTCAR").write_text("output")
        
        # Analysis scanning should exclude CHGCAR
        result = scan_raw_directory(calc_dir, "vasp")
        
        assert "raw/CHGCAR" not in result
        assert "raw/OUTCAR" in result

