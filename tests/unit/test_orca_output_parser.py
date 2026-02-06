"""Tests for ORCA output parser.

Uses sample ORCA output text to test energy, convergence, and geometry extraction.
"""

from __future__ import annotations

import pytest

from quantumvitas.drivers.orca.parsers.output import (
    ORCADigest,
    ORCAOutputParser,
    parse_orca_output_text,
    HARTREE_TO_EV,
)


# Sample ORCA output text for a successful single-point calculation
SAMPLE_SP_OUTPUT = """
                                 *****************
                                 * O   R   C   A *
                                 *****************

                                            #,
                                           ###
...

Total Charge           Charge          ....     0
Multiplicity           Mult            ....     1

----------------------------
CARTESIAN COORDINATES (ANGSTROEM)
----------------------------
  O      0.000000    0.000000    0.117369
  H      0.000000    0.757918   -0.469476
  H      0.000000   -0.757918   -0.469476

-------------------
SCF ENERGY
-------------------

*                     SCF CONVERGED AFTER   8 CYCLES                     *

FINAL SINGLE POINT ENERGY       -76.359831578643

Timings for individual modules:

Sum of individual times         ...       3.528 sec (=   0.059 min)
Total run time: 0 days 0 hours 0 min 3 sec

****ORCA TERMINATED NORMALLY****
"""


SAMPLE_OPT_OUTPUT = """
                                 *****************
                                 * O   R   C   A *
                                 *****************

Total Charge           Charge          ....     0
Multiplicity           Mult            ....     1

                      *** STARTING GEOMETRY OPTIMIZATION ***

GEOMETRY OPTIMIZATION CYCLE   1

...

*                     SCF CONVERGED AFTER   8 CYCLES                     *

GEOMETRY OPTIMIZATION CYCLE   2

...

*                     SCF CONVERGED AFTER   6 CYCLES                     *

GEOMETRY OPTIMIZATION CYCLE   3

...

*                     SCF CONVERGED AFTER   5 CYCLES                     *

         *************************************************************
         *                HURRAY - THE OPTIMIZATION HAS CONVERGED                 *
         *************************************************************

----------------------------
CARTESIAN COORDINATES (ANGSTROEM)
----------------------------
  O      0.000000    0.000000    0.117000
  H      0.000000    0.758000   -0.469000
  H      0.000000   -0.758000   -0.469000

FINAL SINGLE POINT ENERGY       -76.361234567890

Total run time: 0 days 0 hours 1 min 23 sec

****ORCA TERMINATED NORMALLY****
"""


SAMPLE_FAILED_OUTPUT = """
                                 *****************
                                 * O   R   C   A *
                                 *****************

Total Charge           Charge          ....     0
Multiplicity           Mult            ....     1

-------------------
SCF ENERGY
-------------------

SCF NOT CONVERGED AFTER 125 CYCLES

ORCA finished by error termination in SCF
ORCA TERMINATED ABNORMALLY - SCF did not converge
"""


SAMPLE_OUTPUT_WITH_GEOMETRY = """
                                 *****************
                                 * O   R   C   A *
                                 *****************

----------------------------
CARTESIAN COORDINATES (ANGSTROEM)
----------------------------
  C      1.400000    0.000000    0.000000
  C      0.700000    1.212436    0.000000
  C     -0.700000    1.212436    0.000000
  C     -1.400000    0.000000    0.000000
  C     -0.700000   -1.212436    0.000000
  C      0.700000   -1.212436    0.000000
  H      2.494301    0.000000    0.000000
  H      1.247151    2.160167    0.000000
  H     -1.247151    2.160167    0.000000
  H     -2.494301    0.000000    0.000000
  H     -1.247151   -2.160167    0.000000
  H      1.247151   -2.160167    0.000000

*                     SCF CONVERGED AFTER   10 CYCLES                     *

FINAL SINGLE POINT ENERGY      -232.123456789012

Total run time: 0 days 0 hours 0 min 45 sec

****ORCA TERMINATED NORMALLY****
"""


class TestORCAOutputParser:
    """Tests for ORCAOutputParser._parse_output_text."""

    def test_parse_success_detection(self):
        """Should detect successful termination."""
        digest = parse_orca_output_text(SAMPLE_SP_OUTPUT)
        assert digest.success is True

    def test_parse_failed_detection(self):
        """Should detect failed calculation."""
        digest = parse_orca_output_text(SAMPLE_FAILED_OUTPUT)
        assert digest.success is False
        assert digest.converged_scf is False

    def test_parse_final_energy(self):
        """Should extract final energy in Hartree and eV."""
        digest = parse_orca_output_text(SAMPLE_SP_OUTPUT)
        assert digest.final_energy_Ha is not None
        assert abs(digest.final_energy_Ha - (-76.359831578643)) < 1e-10
        assert digest.final_energy_eV is not None
        assert abs(digest.final_energy_eV - (-76.359831578643 * HARTREE_TO_EV)) < 1e-6

    def test_parse_scf_cycles(self):
        """Should extract SCF cycle count."""
        digest = parse_orca_output_text(SAMPLE_SP_OUTPUT)
        assert digest.n_scf_cycles == 8
        assert digest.converged_scf is True

    def test_parse_opt_convergence(self):
        """Should detect geometry optimization convergence."""
        digest = parse_orca_output_text(SAMPLE_OPT_OUTPUT)
        assert digest.converged_geometry is True
        assert digest.n_opt_cycles == 3

    def test_parse_wall_time(self):
        """Should extract wall time in seconds."""
        digest = parse_orca_output_text(SAMPLE_SP_OUTPUT)
        assert digest.wall_time_s == 3

        digest2 = parse_orca_output_text(SAMPLE_OPT_OUTPUT)
        assert digest2.wall_time_s == 83  # 1 min 23 sec

    def test_parse_charge_multiplicity(self):
        """Should extract charge and multiplicity."""
        digest = parse_orca_output_text(SAMPLE_SP_OUTPUT)
        assert digest.charge == 0
        assert digest.multiplicity == 1

    def test_parse_geometry(self):
        """Should extract final Cartesian coordinates."""
        digest = parse_orca_output_text(SAMPLE_SP_OUTPUT)
        assert digest.final_species is not None
        assert digest.final_species == ["O", "H", "H"]
        assert digest.n_atoms == 3
        assert digest.final_cart_coords is not None
        assert len(digest.final_cart_coords) == 3
        # Check first atom (O)
        assert abs(digest.final_cart_coords[0][0] - 0.0) < 1e-6
        assert abs(digest.final_cart_coords[0][2] - 0.117369) < 1e-6

    def test_parse_benzene_geometry(self):
        """Should extract larger geometry (benzene)."""
        digest = parse_orca_output_text(SAMPLE_OUTPUT_WITH_GEOMETRY)
        assert digest.final_species is not None
        assert digest.n_atoms == 12
        assert digest.final_species.count("C") == 6
        assert digest.final_species.count("H") == 6

    def test_digest_to_dict(self):
        """ORCADigest.to_dict should return JSON-serializable dict."""
        digest = parse_orca_output_text(SAMPLE_SP_OUTPUT)
        d = digest.to_dict()
        assert isinstance(d, dict)
        assert d["success"] is True
        assert "final_energy_Ha" in d
        assert "final_species" in d


class TestORCAOutputParserDirectory:
    """Tests for ORCAOutputParser.parse with directory."""

    def test_parse_directory(self, tmp_path):
        """Should find and parse .out file in directory."""
        (tmp_path / "orca.out").write_text(SAMPLE_SP_OUTPUT)

        parser = ORCAOutputParser()
        assert parser.can_parse(tmp_path)

        digest = parser.parse(tmp_path)
        assert digest.success is True
        assert digest.final_energy_Ha is not None

    def test_parse_missing_output(self, tmp_path):
        """Should return error digest if no output file."""
        parser = ORCAOutputParser()
        assert not parser.can_parse(tmp_path)

        digest = parser.parse(tmp_path)
        assert digest.success is False
        assert digest.error_message is not None

    def test_can_parse_checks_orca_marker(self, tmp_path):
        """can_parse should check for ORCA markers in file."""
        # Write a non-ORCA .out file
        (tmp_path / "other.out").write_text("Some other output\n")
        parser = ORCAOutputParser()
        assert not parser.can_parse(tmp_path)

        # Write an ORCA .out file
        (tmp_path / "orca.out").write_text(SAMPLE_SP_OUTPUT)
        assert parser.can_parse(tmp_path)


class TestORCADigest:
    """Tests for ORCADigest dataclass."""

    def test_default_values(self):
        """ORCADigest should have sensible defaults."""
        digest = ORCADigest()
        assert digest.success is False
        assert digest.final_energy_Ha is None
        assert digest.n_atoms == 0
        assert digest.converged_scf is False

    def test_energy_conversion(self):
        """Energy should be consistent between Hartree and eV."""
        digest = parse_orca_output_text(SAMPLE_SP_OUTPUT)
        if digest.final_energy_Ha is not None and digest.final_energy_eV is not None:
            expected_eV = digest.final_energy_Ha * HARTREE_TO_EV
            assert abs(digest.final_energy_eV - expected_eV) < 1e-10
