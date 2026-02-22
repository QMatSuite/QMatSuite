"""Tests for ABINIT output digest parser.

Validates ABINITDigest + ABINITOutputParser against real .abo golden refs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.drivers.abinit.parsers.output import ABINITDigest, ABINITOutputParser

GOLDEN_DIR = Path(__file__).resolve().parents[3] / "docs" / "engines" / "abinit" / "golden_refs"

# Expected values from si_scf.abo golden reference:
# etotal = -8.86646490E+00 Ha => -241.2688 eV (approx)
# fermie = 2.13587267E-01 Ha => 5.812 eV (approx)
# pressure_GPa = -1.5674
# 0 WARNINGs, 4 COMMENTs
# natom = 2, version = 10.4.7-d
# 6 ETOT lines (SCF steps)
SI_SCF_ETOTAL_HA = -8.86646490
HA_TO_EV = 27.211386245988


class TestABINITDigestDataclass:
    """Test ABINITDigest defaults and to_dict."""

    def test_defaults(self):
        d = ABINITDigest()
        assert d.final_energy_eV is None
        assert d.n_atoms == 0
        assert d.converged_electronic is False
        assert d.n_datasets == 1

    def test_to_dict(self):
        d = ABINITDigest(final_energy_eV=-241.27, n_atoms=2)
        dct = d.to_dict()
        assert dct["final_energy_eV"] == pytest.approx(-241.27)
        assert dct["n_atoms"] == 2
        assert "converged_electronic" in dct


class TestABINITOutputParserSiSCF:
    """Test parser on si_scf.abo golden reference."""

    @pytest.fixture(scope="class")
    def digest(self) -> ABINITDigest:
        abo_path = GOLDEN_DIR / "si_scf.abo"
        if not abo_path.exists():
            pytest.skip("si_scf.abo golden ref not found")
        parser = ABINITOutputParser()
        text = abo_path.read_text(errors="replace")
        return parser._parse_abo_text(text)

    def test_version(self, digest):
        assert digest.abinit_version is not None
        assert "10.4" in digest.abinit_version

    def test_calculation_type(self, digest):
        assert digest.calculation_type == "scf"

    def test_energy(self, digest):
        expected_eV = SI_SCF_ETOTAL_HA * HA_TO_EV
        assert digest.final_energy_eV is not None
        assert digest.final_energy_eV == pytest.approx(expected_eV, abs=0.01)

    def test_energy_per_atom(self, digest):
        assert digest.energy_per_atom_eV is not None
        expected = SI_SCF_ETOTAL_HA * HA_TO_EV / 2
        assert digest.energy_per_atom_eV == pytest.approx(expected, abs=0.01)

    def test_n_atoms(self, digest):
        assert digest.n_atoms == 2

    def test_convergence(self, digest):
        assert digest.converged_electronic is True

    def test_scf_steps(self, digest):
        assert digest.n_electronic_steps == 6

    def test_fermi_energy(self, digest):
        expected = 0.213587267 * HA_TO_EV
        assert digest.fermi_energy_eV is not None
        assert digest.fermi_energy_eV == pytest.approx(expected, abs=0.01)

    def test_pressure(self, digest):
        assert digest.pressure_GPa is not None
        assert digest.pressure_GPa == pytest.approx(-1.5674, abs=0.001)

    def test_forces_zero(self, digest):
        # Si SCF has zero forces (equilibrium)
        assert digest.max_force_eV_A is not None
        assert digest.max_force_eV_A == pytest.approx(0.0, abs=1e-6)

    def test_warnings_comments(self, digest):
        assert digest.n_warnings == 0
        assert digest.n_comments == 4

    def test_elapsed_time(self, digest):
        assert digest.elapsed_time_s is not None
        assert digest.elapsed_time_s > 0

    def test_final_structure(self, digest):
        assert digest.final_lattice is not None
        assert len(digest.final_lattice) == 3
        assert digest.final_frac_coords is not None
        assert len(digest.final_frac_coords) == 2

    def test_volume(self, digest):
        assert digest.volume_A3 is not None
        # Si FCC primitive cell: ~40 A^3
        assert 35 < digest.volume_A3 < 45


class TestABINITOutputParserSiRelax:
    """Test parser on si_relax.abo golden reference."""

    @pytest.fixture(scope="class")
    def digest(self) -> ABINITDigest:
        abo_path = GOLDEN_DIR / "si_relax.abo"
        if not abo_path.exists():
            pytest.skip("si_relax.abo golden ref not found")
        parser = ABINITOutputParser()
        text = abo_path.read_text(errors="replace")
        return parser._parse_abo_text(text)

    def test_calculation_type(self, digest):
        assert digest.calculation_type in ("relax", "vc_relax")

    def test_energy_present(self, digest):
        assert digest.final_energy_eV is not None

    def test_convergence(self, digest):
        assert digest.converged_electronic is True


class TestABINITOutputParserSiBands:
    """Test parser on si_bands.abo golden reference."""

    @pytest.fixture(scope="class")
    def digest(self) -> ABINITDigest:
        abo_path = GOLDEN_DIR / "si_bands.abo"
        if not abo_path.exists():
            pytest.skip("si_bands.abo golden ref not found")
        parser = ABINITOutputParser()
        text = abo_path.read_text(errors="replace")
        return parser._parse_abo_text(text)

    def test_has_multiple_datasets(self, digest):
        assert digest.n_datasets >= 2

    def test_energy_present(self, digest):
        assert digest.final_energy_eV is not None


class TestABINITOutputParserCanParse:
    """Test can_parse detection."""

    def test_can_parse_golden(self, tmp_path):
        """can_parse returns True when .abo files exist."""
        (tmp_path / "test.abo").write_text("fake abo content")
        parser = ABINITOutputParser()
        assert parser.can_parse(tmp_path) is True

    def test_cannot_parse_empty(self, tmp_path):
        """can_parse returns False for empty directory."""
        parser = ABINITOutputParser()
        assert parser.can_parse(tmp_path) is False

    def test_parse_missing_returns_empty(self, tmp_path):
        """parse on empty dir returns empty digest."""
        parser = ABINITOutputParser()
        digest = parser.parse(tmp_path)
        assert digest.final_energy_eV is None
        assert digest.n_atoms == 0


class TestABINITOutputParserRegistration:
    """Test parser registry integration."""

    def test_registered_in_registry(self):
        from qmatsuite.parsers.registry import get_parser
        parser = get_parser("abinit", "scf_digest")
        assert parser is not None
        assert parser.engine == "abinit"
        assert parser.object_type == "scf_digest"
