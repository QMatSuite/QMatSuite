"""
Tests for the analysis parsers module.

Uses real QE output files from tests/data/analysis_* directories.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from quantumvitas.analysis.parsers import (
    parse_scf_output,
    parse_dos_data,
    parse_bands_gnu,
    SCFResult,
    DOSData,
    BandStructureData,
)

# Test data directory (relative to repo root)
TEST_DATA_DIR = Path(__file__).parent.parent / "data"


class TestSCFParser:
    """Tests for SCF output parsing."""
    
    @pytest.fixture
    def scf_file(self) -> Path:
        return TEST_DATA_DIR / "analysis_scf" / "si.0_scf.out"
    
    def test_parse_scf_basic(self, scf_file: Path):
        """Test basic SCF parsing returns SCFResult."""
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        
        result = parse_scf_output(scf_file)
        assert isinstance(result, SCFResult)
    
    def test_scf_convergence(self, scf_file: Path):
        """Test that SCF parsing detects convergence correctly."""
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        
        result = parse_scf_output(scf_file)
        assert result.converged is True
    
    def test_scf_iterations(self, scf_file: Path):
        """Test that SCF iterations are extracted."""
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        
        result = parse_scf_output(scf_file)
        assert len(result.iterations) > 0
        # Each iteration should have valid energy
        for it in result.iterations:
            assert it.iteration > 0
            assert it.total_energy != 0
    
    def test_scf_total_energy(self, scf_file: Path):
        """Test that total energy is extracted."""
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        
        result = parse_scf_output(scf_file)
        assert result.total_energy is not None
        # Silicon total energy should be negative and in reasonable range
        assert result.total_energy < 0
        assert result.total_energy > -100  # Not unreasonably large
    
    def test_scf_fermi_energy(self, scf_file: Path):
        """Test Fermi/HOMO energy extraction."""
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        
        result = parse_scf_output(scf_file)
        # Should have either Fermi energy or HOMO
        assert result.fermi_energy is not None or result.homo is not None
    
    def test_scf_parameters(self, scf_file: Path):
        """Test calculation parameters are extracted."""
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        
        result = parse_scf_output(scf_file)
        assert result.n_electrons is not None
        assert result.n_kpoints is not None
        assert result.ecutwfc is not None
    
    def test_scf_to_dict(self, scf_file: Path):
        """Test JSON serialization."""
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        
        result = parse_scf_output(scf_file)
        data = result.to_dict()
        
        # Check units are included
        assert "units" in data
        assert data["units"]["energy"] == "Ry"
        assert data["units"]["fermi"] == "eV"
        
        # Should be JSON serializable
        json_str = json.dumps(data)
        assert len(json_str) > 0
    
    def test_scf_iteration_accuracy(self, scf_file: Path):
        """Test SCF accuracy values in iterations."""
        if not scf_file.exists():
            pytest.skip(f"Test data not found: {scf_file}")
        
        result = parse_scf_output(scf_file)
        # Accuracy should decrease (converge) over iterations
        if len(result.iterations) > 1:
            first_acc = result.iterations[0].scf_accuracy
            last_acc = result.iterations[-1].scf_accuracy
            # Last accuracy should be smaller (better)
            assert last_acc <= first_acc
    
    def test_scf_from_text(self):
        """Test parsing from text string."""
        # Minimal SCF output
        text = """
     iteration #  1     ecut=    40.00 Ry     beta= 0.70
     total energy              =     -22.83737472 Ry
     estimated scf accuracy    <       0.05261014 Ry
     
!    total energy              =     -22.83945243 Ry

     JOB DONE.
"""
        result = parse_scf_output(text)
        assert result.converged is True
        assert len(result.iterations) == 1
        assert result.total_energy == pytest.approx(-22.83945243)


class TestDOSParser:
    """Tests for DOS data parsing."""
    
    @pytest.fixture
    def dos_file(self) -> Path:
        return TEST_DATA_DIR / "analysis_dos" / "si.dos.dat"
    
    def test_parse_dos_basic(self, dos_file: Path):
        """Test basic DOS parsing returns DOSData."""
        if not dos_file.exists():
            pytest.skip(f"Test data not found: {dos_file}")
        
        result = parse_dos_data(dos_file)
        assert isinstance(result, DOSData)
    
    def test_dos_arrays_shape(self, dos_file: Path):
        """Test DOS arrays have correct shapes."""
        if not dos_file.exists():
            pytest.skip(f"Test data not found: {dos_file}")
        
        result = parse_dos_data(dos_file)
        assert len(result.energies) > 0
        assert len(result.dos) == len(result.energies)
        if result.idos is not None:
            assert len(result.idos) == len(result.energies)
    
    def test_dos_fermi_energy(self, dos_file: Path):
        """Test Fermi energy extraction from header."""
        if not dos_file.exists():
            pytest.skip(f"Test data not found: {dos_file}")
        
        result = parse_dos_data(dos_file)
        # DOS file should have Fermi energy in header
        assert result.fermi_energy is not None
    
    def test_dos_energy_range(self, dos_file: Path):
        """Test energy range is reasonable."""
        if not dos_file.exists():
            pytest.skip(f"Test data not found: {dos_file}")
        
        result = parse_dos_data(dos_file)
        e_min, e_max = result.energies.min(), result.energies.max()
        # Should span a reasonable energy range
        assert e_max - e_min > 1  # At least 1 eV range
        assert e_max - e_min < 100  # Not unreasonably large
    
    def test_dos_non_negative(self, dos_file: Path):
        """Test DOS values are non-negative."""
        if not dos_file.exists():
            pytest.skip(f"Test data not found: {dos_file}")
        
        result = parse_dos_data(dos_file)
        assert np.all(result.dos >= 0)
    
    def test_dos_to_dict(self, dos_file: Path):
        """Test JSON serialization."""
        if not dos_file.exists():
            pytest.skip(f"Test data not found: {dos_file}")
        
        result = parse_dos_data(dos_file)
        data = result.to_dict()
        
        # Check units are included
        assert "units" in data
        assert data["units"]["energy"] == "eV"
        
        # Check array lengths
        assert data["n_points"] == len(result.energies)
        
        # Should be JSON serializable
        json_str = json.dumps(data)
        assert len(json_str) > 0
    
    def test_dos_shift_to_fermi(self, dos_file: Path):
        """Test Fermi shift functionality."""
        if not dos_file.exists():
            pytest.skip(f"Test data not found: {dos_file}")
        
        result = parse_dos_data(dos_file)
        if result.fermi_energy is None:
            pytest.skip("No Fermi energy in this file")
        
        shifted = result.shift_to_fermi()
        assert shifted.fermi_energy == 0.0
        # Check that energies were actually shifted
        expected_shift = result.energies - result.fermi_energy
        np.testing.assert_array_almost_equal(shifted.energies, expected_shift)


class TestBandsParser:
    """Tests for band structure parsing."""
    
    @pytest.fixture
    def bands_file(self) -> Path:
        return TEST_DATA_DIR / "analysis_bands" / "si.bands.dat.gnu"
    
    @pytest.fixture
    def symmetry_file(self) -> Path:
        return TEST_DATA_DIR / "analysis_bands" / "si.3_bands.pp.out"
    
    def test_parse_bands_basic(self, bands_file: Path):
        """Test basic bands parsing returns BandStructureData."""
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        
        result = parse_bands_gnu(bands_file)
        assert isinstance(result, BandStructureData)
    
    def test_bands_dimensions(self, bands_file: Path):
        """Test band array dimensions."""
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        
        result = parse_bands_gnu(bands_file)
        assert result.n_bands > 0
        assert result.n_kpoints > 0
        assert result.energies.shape == (result.n_bands, result.n_kpoints)
        assert len(result.k_distances) == result.n_kpoints
    
    def test_bands_with_symmetry(self, bands_file: Path, symmetry_file: Path):
        """Test bands parsing with symmetry file."""
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        if not symmetry_file.exists():
            pytest.skip(f"Test data not found: {symmetry_file}")
        
        result = parse_bands_gnu(bands_file, symmetry_file=symmetry_file)
        assert len(result.high_symmetry_points) > 0
        # Check that high-sym points have labels
        for pt in result.high_symmetry_points:
            assert pt.label
            assert pt.k_distance is not None
    
    def test_bands_without_symmetry(self, bands_file: Path):
        """Test bands parsing without symmetry file."""
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        
        result = parse_bands_gnu(bands_file)
        # Should still work but with empty symmetry points
        assert result.high_symmetry_points == [] or len(result.high_symmetry_points) == 0
    
    def test_bands_k_distances_monotonic(self, bands_file: Path):
        """Test k-distances are monotonically increasing."""
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        
        result = parse_bands_gnu(bands_file)
        # k-distances should be monotonically increasing
        diffs = np.diff(result.k_distances)
        assert np.all(diffs >= 0)
    
    def test_bands_to_dict(self, bands_file: Path, symmetry_file: Path):
        """Test JSON serialization."""
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        
        result = parse_bands_gnu(
            bands_file, 
            symmetry_file=symmetry_file if symmetry_file.exists() else None
        )
        data = result.to_dict()
        
        # Check units are included
        assert "units" in data
        assert data["units"]["energy"] == "eV"
        
        # Check dimensions
        assert data["n_bands"] == result.n_bands
        assert data["n_kpoints"] == result.n_kpoints
        
        # Should be JSON serializable
        json_str = json.dumps(data)
        assert len(json_str) > 0
    
    def test_bands_shift_to_fermi(self, bands_file: Path):
        """Test Fermi shift functionality."""
        if not bands_file.exists():
            pytest.skip(f"Test data not found: {bands_file}")
        
        result = parse_bands_gnu(bands_file, fermi_energy=5.0)
        shifted = result.shift_to_fermi()
        
        assert shifted.fermi_energy == 0.0
        # Check energies were shifted
        expected_shift = result.energies - 5.0
        np.testing.assert_array_almost_equal(shifted.energies, expected_shift)

