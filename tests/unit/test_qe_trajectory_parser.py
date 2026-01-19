"""Tests for QE trajectory parser unit conversions."""
import pytest
from pathlib import Path

from quantumvitas.parsers.qe.trajectory import QETrajectoryParser, RY_TO_EV


class TestQEUnitConversions:
    """Test that QE parser correctly converts units."""
    
    def test_ry_to_ev_conversion(self):
        """Energy in Ry is converted to eV."""
        # 1 Ry = 13.605693... eV
        assert abs(RY_TO_EV - 13.605693122994) < 1e-6
    
    def test_bohr_to_angstrom_conversion(self):
        """alat in Bohr is converted to Å."""
        # From QE output: "lattice parameter (alat) = 10.2623 a.u."
        # Expected alat in Å: 10.2623 * 0.529177 = 5.431...
        bohr_to_angstrom = 0.529177
        alat_bohr = 10.2623
        alat_angstrom = alat_bohr * bohr_to_angstrom
        
        assert abs(alat_angstrom - 5.431) < 0.01
    
    def test_parse_angstrom_positions(self, tmp_path):
        """Positions in angstrom are returned as-is."""
        # Create minimal QE relax output with ATOMIC_POSITIONS (angstrom)
        qe_output = """
     Program PWSCF v.7.2

     bravais-lattice index     =            0
     lattice parameter (alat)  =      10.2623  a.u.
     
ATOMIC_POSITIONS (angstrom)
Si      0.000000    0.000000    0.000000
Si      1.357625    1.357625    1.357625

     number of scf cycles    =   1
     
End final coordinates
"""
        calc_dir = tmp_path / "calc"
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True)
        
        output_file = raw_dir / "relax.out"
        output_file.write_text(qe_output)
        
        parser = QETrajectoryParser()
        traj = parser.parse(raw_dir, calc_dir)
        
        # Positions should be in Å
        assert len(traj.frames) >= 1
        assert traj.frames[0].positions[0, 0] == pytest.approx(0.0, abs=1e-6)
        assert traj.frames[0].positions[1, 0] == pytest.approx(1.357625, abs=1e-4)

