"""Unit tests for ORCA property.txt parser."""
import pytest
from pathlib import Path


FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "orca"


class TestPropertyParser:
    """Tests for property.txt parsing."""

    def test_parse_scf_energy(self):
        """Parse SCF energy from property file."""
        from qmatsuite.engines.orca.property_parser import parse_orca_property_txt

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf.property.txt")

        assert "SCF_Energy" in result
        assert "totalEnergy" in result["SCF_Energy"]
        energy = result["SCF_Energy"]["totalEnergy"]
        assert isinstance(energy, (float, list))
        # Handle both single value and array
        if isinstance(energy, list):
            energy = energy[0]
        assert energy < 0  # Energy should be negative
        assert abs(energy - (-75.960994341814)) < 1e-6

    def test_parse_final_energy(self):
        """Parse final energy from Single_Point_Data block."""
        from qmatsuite.engines.orca.property_parser import parse_orca_property_txt

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf.property.txt")

        assert "Single_Point_Data" in result
        assert "FinalEnergy" in result["Single_Point_Data"]
        energy = result["Single_Point_Data"]["FinalEnergy"]
        assert abs(energy - (-75.960994341814)) < 1e-6

    def test_parse_calculation_status(self):
        """Parse calculation status."""
        from qmatsuite.engines.orca.property_parser import parse_orca_property_txt

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf.property.txt")

        assert "Calculation_Status" in result
        status = result["Calculation_Status"]
        assert status.get("Status") == "NORMAL TERMINATION"
        assert status.get("version") == "6.1.1"

    def test_parse_calculation_info(self):
        """Parse calculation info (electrons, basis functions, etc.)."""
        from qmatsuite.engines.orca.property_parser import parse_orca_property_txt

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf.property.txt")

        assert "Calculation_Info" in result
        info = result["Calculation_Info"]
        assert info.get("NumOfAtoms") == 3
        assert info.get("NumOfElectrons") == 10
        assert info.get("NumOfBasisFuncts") == 24
        assert info.get("Charge") == 0
        assert info.get("Mult") == 1

    def test_parse_dipole_moment(self):
        """Parse dipole moment."""
        from qmatsuite.engines.orca.property_parser import parse_orca_property_txt

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf.property.txt")

        assert "SCF_Dipole_Moment" in result
        dipole = result["SCF_Dipole_Moment"]
        assert "dipoleMagnitude" in dipole
        assert dipole["dipoleMagnitude"] > 0

    def test_parse_property_txt_string(self):
        """Parse property content from string."""
        from qmatsuite.engines.orca.property_parser import parse_property_txt_string

        content = '''$SCF_Energy
   &GeometryIndex 1
   &Method [&Type "String"] "SCF"
   &totalEnergy [&Type "ArrayOfDoubles", &Dim (1,1)] "Total energy of each state"
                                                         0

0                                     -7.5960994341813887e+01
   &Mult [&Type "ArrayOfIntegers", &Dim (1,1)] "Multiplicity of each state"
                                                         0

0                                                        1
$End
'''
        result = parse_property_txt_string(content)

        assert "SCF_Energy" in result
        assert "totalEnergy" in result["SCF_Energy"]

    def test_missing_file_raises(self):
        """Missing file should raise FileNotFoundError."""
        from qmatsuite.engines.orca.property_parser import parse_orca_property_txt

        with pytest.raises(FileNotFoundError):
            parse_orca_property_txt(Path("/nonexistent/file.property.txt"))

    def test_empty_file_returns_empty_dict(self):
        """Empty file should return empty dict."""
        from qmatsuite.engines.orca.property_parser import parse_property_txt_string

        result = parse_property_txt_string("")
        assert result == {}

    def test_get_energy_helper(self):
        """Test convenience function to get energy."""
        from qmatsuite.engines.orca.property_parser import (
            parse_orca_property_txt,
            get_energy,
        )

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf.property.txt")
        energy = get_energy(result)

        assert energy is not None
        assert abs(energy - (-75.960994341814)) < 1e-6

    def test_is_converged_helper(self):
        """Test convenience function to check convergence."""
        from qmatsuite.engines.orca.property_parser import (
            parse_orca_property_txt,
            is_converged,
        )

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf.property.txt")
        converged = is_converged(result)

        assert converged is True


class TestTDDFTPropertyParser:
    """Tests for TDDFT property.txt parsing."""

    def test_parse_tddft_property_file(self):
        """Parse TDDFT property file."""
        from qmatsuite.engines.orca.property_parser import parse_orca_property_txt

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf_td.property.txt")

        # Should have CIS_Energies block
        assert "CIS_Energies" in result
        assert "CIS_Absorption_Spectrum" in result

    def test_parse_cis_energies(self):
        """Parse CIS excited state energies."""
        from qmatsuite.engines.orca.property_parser import parse_orca_property_txt

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf_td.property.txt")

        cis_energies = result.get("CIS_Energies", {})
        # Ground state energy
        assert "e0" in cis_energies
        assert cis_energies["e0"] < 0  # Should be negative
        # Total energies of excited states
        assert "totalEnergy" in cis_energies

    def test_get_tddft_excitations(self):
        """Test TDDFT excitation extraction."""
        from qmatsuite.engines.orca.property_parser import (
            parse_orca_property_txt,
            get_tddft_excitations,
        )

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf_td.property.txt")
        tddft_data = get_tddft_excitations(result)

        assert tddft_data is not None
        assert "ground_state_energy" in tddft_data
        assert "excitation_energies_ev" in tddft_data
        assert "nroots" in tddft_data
        assert tddft_data["nroots"] == 3

        # Excitation energies should be positive (higher than ground state)
        for e in tddft_data["excitation_energies_ev"]:
            assert e > 0

    def test_tddft_mode_detection(self):
        """Test TDDFT mode detection (CIS, TDA, etc.)."""
        from qmatsuite.engines.orca.property_parser import (
            parse_orca_property_txt,
            get_tddft_excitations,
        )

        result = parse_orca_property_txt(FIXTURES_DIR / "water_scf_td.property.txt")
        tddft_data = get_tddft_excitations(result)

        assert tddft_data is not None
        assert "mode" in tddft_data
        # Our test uses TDA/CIS
        assert "CIS" in tddft_data["mode"] or "TDA" in tddft_data["mode"]
