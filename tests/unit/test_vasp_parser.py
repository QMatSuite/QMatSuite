"""Unit tests for VASP output parser."""

import pytest
from pathlib import Path
from quantumvitas.engine.vasp_parser import (
    parse_oszicar,
    parse_outcar,
    parse_vasp_output,
)


class TestVASPOSZICARParser:
    """Test OSZICAR parser."""
    
    def test_parse_oszicar_extracts_iterations(self, tmp_path):
        """Test parsing OSZICAR iterations."""
        oszicar_content = """       N       E                     dE             d eps       ncg     rms          rms(c)
DAV:   1    -0.307508816106E+01   -0.30751E+01   -0.12475E+03   732   0.285E+02
DAV:   2    -0.488669577224E+01   -0.18116E+01   -0.17027E+01  1008   0.280E+01
DAV:   3    -0.489753529435E+01   -0.10840E-01   -0.10837E-01   756   0.231E+00
   1 F= -.48774144E+01 E0= -.48758836E+01  d E =-.306172E-02
"""
        oszicar_path = tmp_path / "OSZICAR"
        oszicar_path.write_text(oszicar_content)
        
        result = parse_oszicar(oszicar_path)
        
        assert len(result["iterations"]) == 3
        assert result["final_energy"] == pytest.approx(-4.8774144, abs=1e-6)
        assert result["final_energy_0k"] == pytest.approx(-4.8758836, abs=1e-6)
        assert result["converged"] is True  # Should be close
    
    def test_parse_oszicar_missing_file(self, tmp_path):
        """Test parsing missing OSZICAR."""
        oszicar_path = tmp_path / "OSZICAR"
        
        result = parse_oszicar(oszicar_path)
        
        assert result["iterations"] == []
        assert result["final_energy"] is None
        assert result["converged"] is False


class TestVASPOUTCARParser:
    """Test OUTCAR parser."""
    
    def test_parse_outcar_extracts_energy(self, tmp_path):
        """Test parsing OUTCAR energy."""
        outcar_content = """
  FREE ENERGIE OF THE ION-ELECTRON SYSTEM (eV)
  ---------------------------------------------------
  free  energy   TOTEN  =        -4.87741443 eV

  energy  without entropy=       -4.87435271  energy(sigma->0) =       -4.87588357

                  Total CPU time used (sec):        0.530
                            User time (sec):        0.441
                          System time (sec):        0.089
                         Elapsed time (sec):        0.470

 POSITION                                       TOTAL-FORCE (eV/Angst)
 -----------------------------------------------------------------------------------
      0.00000      0.00000      0.00000         0.000000     -0.000000     -0.000000
 -----------------------------------------------------------------------------------
    total drift:                               -0.000000     -0.000000      0.000000
"""
        outcar_path = tmp_path / "OUTCAR"
        outcar_path.write_text(outcar_content)
        
        result = parse_outcar(outcar_path)
        
        assert result["total_energy"] == pytest.approx(-4.87741443, abs=1e-6)
        assert result["energy_without_entropy"] == pytest.approx(-4.87435271, abs=1e-6)
        assert result["energy_sigma_0"] == pytest.approx(-4.87588357, abs=1e-6)
        assert result["walltime"] == pytest.approx(0.470, abs=1e-3)
        assert result["converged"] is True  # Drift is small
    
    def test_parse_outcar_missing_file(self, tmp_path):
        """Test parsing missing OUTCAR."""
        outcar_path = tmp_path / "OUTCAR"
        
        result = parse_outcar(outcar_path)
        
        assert result["total_energy"] is None
        assert result["walltime"] is None
        assert result["converged"] is False


class TestVASPOutputParser:
    """Test combined VASP output parser."""
    
    def test_parse_vasp_output_combines_sources(self, tmp_path):
        """Test parsing VASP output from both files."""
        # Write OSZICAR
        oszicar_content = """       N       E                     dE             d eps       ncg     rms          rms(c)
DAV:   1    -0.307508816106E+01   -0.30751E+01   -0.12475E+03   732   0.285E+02
   1 F= -.48774144E+01 E0= -.48758836E+01  d E =-.306172E-02
"""
        (tmp_path / "OSZICAR").write_text(oszicar_content)
        
        # Write OUTCAR
        outcar_content = """
  FREE ENERGIE OF THE ION-ELECTRON SYSTEM (eV)
  ---------------------------------------------------
  free  energy   TOTEN  =        -4.87741443 eV

  energy  without entropy=       -4.87435271  energy(sigma->0) =       -4.87588357

                         Elapsed time (sec):        0.470

    total drift:                               -0.000000     -0.000000      0.000000
"""
        (tmp_path / "OUTCAR").write_text(outcar_content)
        
        result = parse_vasp_output(tmp_path)
        
        assert result["success"] is True
        assert result["energy"] == pytest.approx(-4.87741443, abs=1e-6)  # Prefer OUTCAR
        assert result["converged"] is True
        assert result["walltime"] == pytest.approx(0.470, abs=1e-3)
        assert result["iterations"] == 1
    
    def test_parse_vasp_output_fallback_to_oszicar(self, tmp_path):
        """Test fallback to OSZICAR when OUTCAR missing energy."""
        # Write OSZICAR only
        oszicar_content = """       N       E                     dE             d eps       ncg     rms          rms(c)
DAV:   1    -0.307508816106E+01   -0.30751E+01   -0.12475E+03   732   0.285E+02
   1 F= -.48774144E+01 E0= -.48758836E+01  d E =-.306172E-02
"""
        (tmp_path / "OSZICAR").write_text(oszicar_content)
        
        # Write minimal OUTCAR (no TOTEN)
        (tmp_path / "OUTCAR").write_text("Some content without TOTEN")
        
        result = parse_vasp_output(tmp_path)
        
        assert result["success"] is True
        assert result["energy"] == pytest.approx(-4.8774144, abs=1e-6)  # From OSZICAR
        assert result["iterations"] == 1
    
    def test_parse_vasp_output_missing_files(self, tmp_path):
        """Test parsing when files are missing."""
        result = parse_vasp_output(tmp_path)
        
        assert result["success"] is False
        assert result["energy"] is None
        assert result["converged"] is False





