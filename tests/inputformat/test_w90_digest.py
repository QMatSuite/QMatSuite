"""Tests for Wannier90 output digest (W90Digest + W90OutputParser).

Validates the .wout parser against inline test outputs and real .wout
reference files from the QE bundled Wannier90 examples.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.drivers.w90.parsers.output import (
    W90Digest,
    W90OutputParser,
    parse_wout_text,
)


# ──────────────────────────────────────────────────────────────────────────
# Inline .wout test strings
# ──────────────────────────────────────────────────────────────────────────

SUCCESS_WOUT = """\
             +---------------------------------------------------+
             |                   WANNIER90                       |
             +---------------------------------------------------+

 *---------------------------------- MAIN ------------------------------------*
 |  Number of Wannier Functions               :                 4             |
 |  Number of input Bloch states              :                 4             |
 *----------------------------------------------------------------------------*
 *------------------------------- WANNIERISE ---------------------------------*
 +--------------------------------------------------------------------+<-- CONV
 | Iter  Delta Spread     RMS Gradient      Spread (Ang^2)      Time  |<-- CONV
 +--------------------------------------------------------------------+<-- CONV

 ------------------------------------------------------------------------------
 Initial State
  WF centre and spread    1  ( -0.000151,  0.000151,  0.000151 )     4.43516037
  WF centre and spread    2  ( -0.549699,  0.549699, -0.292073 )     1.31831922
  WF centre and spread    3  (  0.292073,  0.549699,  0.549699 )     1.31831922
  WF centre and spread    4  ( -0.549699, -0.292073,  0.549699 )     1.31831920

      0     0.839E+01     0.0000000000        8.3901180085       0.00  <-- CONV
      1     0.337E+00     1.6286961478        8.7274756849       0.00  <-- CONV
     20    -0.273E-02     0.2039493351        4.3809634608       0.09  <-- CONV
 ------------------------------------------------------------------------------
 Final State
  WF centre and spread    1  (  0.414831, -0.415013, -0.414837 )     1.17685030
  WF centre and spread    2  ( -0.408031,  0.407817, -0.397915 )     1.06787005
  WF centre and spread    3  (  0.397919,  0.407806,  0.408017 )     1.06786000
  WF centre and spread    4  ( -0.408443, -0.397788,  0.408441 )     1.06838311
  Sum of centres and spreads ( -0.003724,  0.002822,  0.003706 )     4.38096346

         Spreads (Ang^2)       Omega I      =     1.954618313
        ================       Omega D      =     0.183011671
                               Omega OD     =     2.243333477
    Final Spread (Ang^2)       Omega Total  =     4.380963461
 ------------------------------------------------------------------------------
 Time for wannierise            0.088 (sec)
 Total Execution Time           0.220 (sec)

 All done: wannier90 exiting
"""

ERROR_WOUT = """\
             +---------------------------------------------------+
             |                   WANNIER90                       |
             +---------------------------------------------------+

 Error: something went terribly wrong with the calculation
 Exiting......
"""

DISENTANGLE_WOUT = """\
             +---------------------------------------------------+
             |                   WANNIER90                       |
             +---------------------------------------------------+

 *---------------------------------- MAIN ------------------------------------*
 |  Number of Wannier Functions               :                 7             |
 |  Number of input Bloch states              :                12             |
 *----------------------------------------------------------------------------*

                  <<< Disentanglement >>>

 +---------------------------------------------------------------------+<-- DIS
 |  Iter     Omega_I(i-1)      Omega_I(i)      Delta (frac.)    Time   |<-- DIS
 +---------------------------------------------------------------------+<-- DIS
       1      24.85432010      19.23456789       2.920E-01      0.01   <-- DIS
      60      14.56789012      14.56789012       1.234E-13      0.10   <-- DIS

                Disentanglement converged after   60 iterations.

 *------------------------------- WANNIERISE ---------------------------------*
 +--------------------------------------------------------------------+<-- CONV
 | Iter  Delta Spread     RMS Gradient      Spread (Ang^2)      Time  |<-- CONV
 +--------------------------------------------------------------------+<-- CONV

      0     0.200E+02     0.0000000000       20.1234567890       0.00  <-- CONV
    200    -0.100E-08     0.0000012345       14.5678901234       0.50  <-- CONV
 ------------------------------------------------------------------------------
 Final State
  WF centre and spread    1  (  0.100000,  0.200000,  0.300000 )     2.08112730
  WF centre and spread    2  (  0.400000,  0.500000,  0.600000 )     2.08112731
  Sum of centres and spreads (  0.500000,  0.700000,  0.900000 )     4.16225461

         Spreads (Ang^2)       Omega I      =    10.123456789
        ================       Omega D      =     1.234567890
                               Omega OD     =     3.209866345
    Final Spread (Ang^2)       Omega Total  =    14.567891024
 ------------------------------------------------------------------------------
 Total Execution Time           1.500 (sec)

 All done: wannier90 exiting
"""

MINIMAL_WOUT = """\
 All done: wannier90 exiting
"""


# ──────────────────────────────────────────────────────────────────────────
# Inline log parsing tests
# ──────────────────────────────────────────────────────────────────────────


class TestWoutParsing:
    """Unit tests for parse_wout_text."""

    def test_success_detected(self):
        d = parse_wout_text(SUCCESS_WOUT)
        assert d.success is True
        assert d.error_message is None

    def test_num_wann(self):
        d = parse_wout_text(SUCCESS_WOUT)
        assert d.num_wann == 4

    def test_num_bands(self):
        d = parse_wout_text(SUCCESS_WOUT)
        assert d.num_bands == 4

    def test_final_spreads(self):
        d = parse_wout_text(SUCCESS_WOUT)
        assert abs(d.final_spread_total - 4.380963461) < 1e-6
        assert abs(d.final_spread_i - 1.954618313) < 1e-6
        assert abs(d.final_spread_d - 0.183011671) < 1e-6
        assert abs(d.final_spread_od - 2.243333477) < 1e-6

    def test_spread_sum(self):
        """Omega I + Omega D + Omega OD = Omega Total."""
        d = parse_wout_text(SUCCESS_WOUT)
        computed = d.final_spread_i + d.final_spread_d + d.final_spread_od
        assert abs(computed - d.final_spread_total) < 1e-4

    def test_wf_centres(self):
        d = parse_wout_text(SUCCESS_WOUT)
        assert d.wf_centres is not None
        assert len(d.wf_centres) == 4
        assert abs(d.wf_centres[0][0] - 0.414831) < 1e-5
        assert abs(d.wf_centres[0][1] - (-0.415013)) < 1e-5

    def test_wf_spreads(self):
        d = parse_wout_text(SUCCESS_WOUT)
        assert d.wf_spreads is not None
        assert len(d.wf_spreads) == 4
        assert abs(d.wf_spreads[0] - 1.17685030) < 1e-6
        assert abs(d.wf_spreads[3] - 1.06838311) < 1e-6

    def test_num_iter_completed(self):
        d = parse_wout_text(SUCCESS_WOUT)
        assert d.num_iter_completed == 20

    def test_wall_time(self):
        d = parse_wout_text(SUCCESS_WOUT)
        assert abs(d.wall_time_s - 0.220) < 1e-3

    def test_converged(self):
        d = parse_wout_text(SUCCESS_WOUT)
        assert d.converged is True

    def test_error_detected(self):
        d = parse_wout_text(ERROR_WOUT)
        assert d.success is False
        assert d.error_message is not None

    def test_empty_wout(self):
        d = parse_wout_text("")
        assert d.success is False

    def test_minimal_success(self):
        d = parse_wout_text(MINIMAL_WOUT)
        assert d.success is True
        assert d.num_wann is None
        assert d.final_spread_total is None

    def test_disentanglement_converged(self):
        d = parse_wout_text(DISENTANGLE_WOUT)
        assert d.success is True
        assert d.disentanglement_converged is True
        assert d.num_wann == 7
        assert d.num_bands == 12

    def test_disentanglement_spreads(self):
        d = parse_wout_text(DISENTANGLE_WOUT)
        assert abs(d.final_spread_total - 14.567891024) < 1e-6
        assert abs(d.final_spread_i - 10.123456789) < 1e-6

    def test_disentanglement_iterations(self):
        d = parse_wout_text(DISENTANGLE_WOUT)
        assert d.num_iter_completed == 200

    def test_disentanglement_wall_time(self):
        d = parse_wout_text(DISENTANGLE_WOUT)
        assert abs(d.wall_time_s - 1.500) < 1e-3

    def test_to_dict(self):
        d = parse_wout_text(SUCCESS_WOUT)
        dd = d.to_dict()
        assert isinstance(dd, dict)
        assert dd["success"] is True
        assert dd["num_wann"] == 4
        assert isinstance(dd["wf_centres"], list)
        assert isinstance(dd["wf_spreads"], list)

    def test_to_dict_json_serializable(self):
        import json
        d = parse_wout_text(SUCCESS_WOUT)
        dd = d.to_dict()
        text = json.dumps(dd)
        assert isinstance(text, str)


# ──────────────────────────────────────────────────────────────────────────
# W90OutputParser class tests
# ──────────────────────────────────────────────────────────────────────────


class TestOutputParserClass:
    """Tests for W90OutputParser can_parse and parse methods."""

    def test_can_parse_true(self, tmp_path):
        (tmp_path / "diamond.wout").write_text(SUCCESS_WOUT)
        parser = W90OutputParser()
        assert parser.can_parse(tmp_path) is True

    def test_can_parse_false(self, tmp_path):
        parser = W90OutputParser()
        assert parser.can_parse(tmp_path) is False

    def test_parse_directory(self, tmp_path):
        (tmp_path / "gaas.wout").write_text(SUCCESS_WOUT)
        parser = W90OutputParser()
        d = parser.parse(tmp_path)
        assert d.success is True
        assert d.num_wann == 4

    def test_parse_missing_wout(self, tmp_path):
        parser = W90OutputParser()
        d = parser.parse(tmp_path)
        assert d.success is False
        assert "No .wout" in d.error_message

    def test_parser_registration(self):
        from qmatsuite.parsers.registry import get_parser
        parser_cls = get_parser("w90", "scf_digest")
        assert parser_cls is not None
        assert parser_cls is W90OutputParser


# ──────────────────────────────────────────────────────────────────────────
# Validation against real .wout reference (if available)
# ──────────────────────────────────────────────────────────────────────────

_REAL_WOUT = (
    Path(__file__).resolve().parent.parent / "data" / "wannier90_examples"
    / "reference" / "diamond.sa.wout"
)


@pytest.mark.skipif(
    not _REAL_WOUT.is_file(),
    reason="Real .wout reference not available",
)
class TestRealWoutReference:
    """Validate digest against real diamond.sa.wout from QE examples."""

    def test_real_wout_success(self):
        text = _REAL_WOUT.read_text(errors="replace")
        d = parse_wout_text(text)
        assert d.success is True

    def test_real_wout_num_wann(self):
        text = _REAL_WOUT.read_text(errors="replace")
        d = parse_wout_text(text)
        assert d.num_wann == 4

    def test_real_wout_spreads(self):
        text = _REAL_WOUT.read_text(errors="replace")
        d = parse_wout_text(text)
        assert d.final_spread_total is not None
        assert abs(d.final_spread_total - 4.380963461) < 0.01
        assert abs(d.final_spread_i - 1.954618313) < 0.01

    def test_real_wout_wf_centres(self):
        text = _REAL_WOUT.read_text(errors="replace")
        d = parse_wout_text(text)
        assert d.wf_centres is not None
        assert len(d.wf_centres) == 4

    def test_real_wout_iterations(self):
        text = _REAL_WOUT.read_text(errors="replace")
        d = parse_wout_text(text)
        assert d.num_iter_completed == 20

    def test_real_wout_wall_time(self):
        text = _REAL_WOUT.read_text(errors="replace")
        d = parse_wout_text(text)
        assert d.wall_time_s is not None
        assert d.wall_time_s > 0
