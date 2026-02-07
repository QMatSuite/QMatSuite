"""Tests for CP2K output digest parser.

Validates CP2KDigest, CP2KOutputParser, and @register_parser integration.
Uses synthetic minimal output text fixtures.
"""

from __future__ import annotations

import pytest
from pathlib import Path

from quantumvitas.drivers.cp2k.parsers.output import (
    CP2KDigest,
    CP2KOutputParser,
    parse_cp2k_output_text,
)

# ── Fixtures ──────────────────────────────────────────────────────────────

ENERGY_OUTPUT = """\
 CP2K| version string:                                       CP2K version 2026.1
 CP2K| source code revision number:                                  git:5e54ba2

 GLOBAL| Run type                                                         ENERGY
 GLOBAL| Method name                                                        CP2K

 Total number of            - Atoms:                                           3

 SCF WAVEFUNCTION OPTIMIZATION

  Step     Update method      Time    Convergence         Total energy    Change
  ------------------------------------------------------------------------------
     1 P_Mix/Diag. 0.40E+00    0.1     0.68566201       -16.9630757863 -1.70E+01
     2 P_Mix/Diag. 0.40E+00    0.1     0.33526734       -17.0664566750 -1.03E-01
     3 P_Mix/Diag. 0.40E+00    0.1     0.20153410       -17.1283624963 -6.19E-02
     4 DIIS/Diag.  0.30E-02    0.1     0.04698728       -17.2000301471 -1.31E-02
     5 DIIS/Diag.  0.11E-03    0.1     0.00017131       -17.2196627890 -1.96E-02
     6 DIIS/Diag.  0.73E-04    0.1     0.00009828       -17.2196628002 -1.13E-08
     7 DIIS/Diag.  0.87E-04    0.1     0.00004960       -17.2196627994  8.14E-10
     8 DIIS/Diag.  0.26E-05    0.1     0.00000199       -17.2196628023 -2.89E-09

  *** SCF run converged in     8 steps ***

  Total energy:                                               -17.21966280231755

 !-----------------------------------------------------------------------------!
                     Mulliken Population Analysis

 #  Atom  Element  Kind  Atomic population                           Net charge
       1     O        1          6.234463                             -0.234463
       2     H        2          0.882769                              0.117231
       3     H        2          0.882769                              0.117231
 # Total charge                              8.000000                  0.000000

 ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]            -17.219662802317551

  **** **** ******  **  PROGRAM STARTED AT               2026-02-06 22:22:59.071
  **** **** ******  **  PROGRAM ENDED AT                 2026-02-06 22:23:25.321
"""

GEO_OPT_OUTPUT = """\
 CP2K| version string:                                       CP2K version 2026.1

 GLOBAL| Run type                                                       GEO_OPT
 GLOBAL| Method name                                                        CP2K

 Total number of            - Atoms:                                           3

 ***                     STARTING GEOMETRY OPTIMIZATION                      ***

  *** SCF run converged in    10 steps ***

 ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]            -17.219662802320954

 OPT| **************************************************************************
 OPT| Step number                                                              1
 OPT| Total energy [hartree]                                      -17.2196628023
 OPT| Used time [s]                                                        1.115
 OPT|
 OPT| Maximum step size                                             0.0500000000
 OPT| Maximum step size is converged                                          NO
 OPT|
 OPT| RMS step size                                                 0.0200000000
 OPT|
 OPT| Maximum gradient                                              0.0050000000
 OPT| Maximum gradient is converged                                           NO
 OPT|
 OPT| RMS gradient                                                  0.0030000000
 OPT| **************************************************************************

  *** SCF run converged in     7 steps ***

 ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]            -17.220094466500000

 OPT| **************************************************************************
 OPT| Step number                                                              2
 OPT| Total energy [hartree]                                      -17.2200944665
 OPT| Used time [s]                                                        5.000
 OPT|
 OPT| Maximum gradient                                              0.0001000000
 OPT| **************************************************************************

 GEOMETRY OPTIMIZATION COMPLETED

  **** **** ******  **  PROGRAM STARTED AT               2026-02-06 22:22:59.000
  **** **** ******  **  PROGRAM ENDED AT                 2026-02-06 22:23:34.500
"""

NOT_CONVERGED_OUTPUT = """\
 CP2K| version string:                                       CP2K version 2026.1

 GLOBAL| Run type                                                         ENERGY
 GLOBAL| Method name                                                        CP2K

 Total number of            - Atoms:                                           2

 SCF WAVEFUNCTION OPTIMIZATION

  Step     Update method      Time    Convergence         Total energy    Change
     1 P_Mix/Diag. 0.40E+00    0.1     0.68566201       -10.0000000000 -1.00E+01
     2 P_Mix/Diag. 0.40E+00    0.1     0.50000000       -10.5000000000 -5.00E-01

  *** SCF run NOT converged ***

 ENERGY| Total FORCE_EVAL ( QS ) energy [hartree]            -10.500000000000000
"""

EMPTY_OUTPUT = """\
Some random text with no CP2K markers
"""


# ── Tests ─────────────────────────────────────────────────────────────────


class TestCP2KDigest:
    """Test CP2KDigest dataclass."""

    def test_default_values(self):
        d = CP2KDigest()
        assert d.final_energy_eV is None
        assert d.n_atoms == 0
        assert d.converged_electronic is False
        assert d.converged_ionic is False

    def test_to_dict(self):
        d = CP2KDigest(final_energy_eV=-468.5, n_atoms=3)
        dd = d.to_dict()
        assert isinstance(dd, dict)
        assert dd["final_energy_eV"] == pytest.approx(-468.5)
        assert dd["n_atoms"] == 3

    def test_to_dict_json_serializable(self):
        import json
        d = CP2KDigest(final_energy_eV=-100.0, converged_electronic=True)
        text = json.dumps(d.to_dict())
        assert "-100.0" in text


class TestCP2KOutputParser:
    """Test CP2KOutputParser text parsing."""

    def test_energy_output(self):
        d = parse_cp2k_output_text(ENERGY_OUTPUT)
        assert d.cp2k_version == "2026.1"
        assert d.run_type == "ENERGY"
        assert d.n_atoms == 3
        assert d.converged_electronic is True
        assert d.n_electronic_steps == 8
        assert d.final_energy_eV is not None
        assert d.final_energy_eV == pytest.approx(-17.21966280 * 27.211386245988, rel=1e-6)
        assert d.energy_per_atom_eV is not None
        assert d.total_charge == pytest.approx(0.0, abs=0.01)

    def test_energy_timing(self):
        d = parse_cp2k_output_text(ENERGY_OUTPUT)
        assert d.elapsed_time_s is not None
        assert d.elapsed_time_s == pytest.approx(26.25, abs=1.0)

    def test_geo_opt_output(self):
        d = parse_cp2k_output_text(GEO_OPT_OUTPUT)
        assert d.run_type == "GEO_OPT"
        assert d.converged_ionic is True
        assert d.n_ionic_steps == 2
        assert d.final_energy_eV is not None
        # Last energy is from step 2
        assert d.final_energy_eV == pytest.approx(-17.2200944665 * 27.211386245988, rel=1e-6)

    def test_geo_opt_gradient(self):
        d = parse_cp2k_output_text(GEO_OPT_OUTPUT)
        assert d.max_force_eV_A is not None
        assert d.rms_gradient is not None

    def test_not_converged(self):
        d = parse_cp2k_output_text(NOT_CONVERGED_OUTPUT)
        assert d.converged_electronic is False
        assert d.n_atoms == 2

    def test_empty_output(self):
        d = parse_cp2k_output_text(EMPTY_OUTPUT)
        assert d.final_energy_eV is None
        assert d.converged_electronic is False
        assert d.n_atoms == 0

    def test_can_parse_with_out_file(self, tmp_path):
        parser = CP2KOutputParser()
        # No .out file
        assert parser.can_parse(tmp_path) is False
        # With .out file
        (tmp_path / "output.out").write_text(ENERGY_OUTPUT)
        assert parser.can_parse(tmp_path) is True

    def test_parse_from_directory(self, tmp_path):
        (tmp_path / "output.out").write_text(ENERGY_OUTPUT)
        parser = CP2KOutputParser()
        d = parser.parse(tmp_path)
        assert d.final_energy_eV is not None
        assert d.converged_electronic is True


class TestParserRegistration:
    """Test parser registry integration."""

    def test_registered_in_registry(self):
        from quantumvitas.parsers.registry import get_parser
        parser = get_parser("cp2k", "scf_digest")
        assert parser is not None
        assert parser.engine == "cp2k"
        assert parser.object_type == "scf_digest"

    def test_parser_class_attributes(self):
        parser = CP2KOutputParser()
        assert parser.engine == "cp2k"
        assert parser.object_type == "scf_digest"
