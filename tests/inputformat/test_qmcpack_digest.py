"""Tests for QMCPACK output digest parser.

Tests the QMCPACKDigest and QMCPACKOutputParser in
src/qmatsuite/drivers/qmcpack/parsers/output.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.drivers.qmcpack.parsers.output import (
    QMCPACKDigest,
    QMCPACKOutputParser,
    parse_qmcpack_stdout_text,
)

# ---------------------------------------------------------------------------
# Inline stdout fragments for unit testing
# ---------------------------------------------------------------------------

VMC_STDOUT_SUCCESS = """\
  Input file(s): qmc_input.xml
================================================================
                        QMCPACK 4.1.0
================================================================
  Global options

  Total number of MPI ranks = 1
  Number of ranks in group  = 1

=========================================================
  Start VMCBatched
  File Root He.s000
=========================================================
VMCBatched Driver running with
             total_walkers     = 14
             walkers_per_rank  = [14]

                         steps = 50
                        blocks = 100

VMC Warmup completed in 5.9760e-03 secs
====================================================
  End of a VMC section
    QMC counter        = 0
    time step          = 0.1
    reference energy   = -2.83818
    reference variance = 0.152471
====================================================
  VMCBatched Execution time = 1.0638e+00 secs
  Total Execution time = 1.0652e+00 secs

QMCPACK execution completed successfully
"""

VMC_DMC_STDOUT = """\
================================================================
                        QMCPACK 4.1.0
================================================================
====================================================
  End of a VMC section
    QMC counter        = 0
    time step          = 0.1
    reference energy   = -2.84000
    reference variance = 0.160000
====================================================
====================================================
  End of a DMC section
    QMC counter        = 1
    time step          = 0.01
    reference energy   = -2.87000
    reference variance = 0.050000
====================================================
  Total Execution time = 4.8500e+00 secs

QMCPACK execution completed successfully
"""

ERROR_STDOUT = """\
================================================================
                        QMCPACK 4.1.0
================================================================
  ERROR: The requested number of samples is more than available.
"""

EMPTY_STDOUT = ""


# ---------------------------------------------------------------------------
# QMCPACKDigest dataclass tests
# ---------------------------------------------------------------------------

class TestQMCPACKDigest:
    def test_default_values(self):
        d = QMCPACKDigest()
        assert d.success is False
        assert d.energy_Ha is None
        assert d.method is None

    def test_to_dict(self):
        d = QMCPACKDigest(success=True, energy_Ha=-2.84, method="vmc")
        result = d.to_dict()
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["energy_Ha"] == -2.84
        assert result["method"] == "vmc"

    def test_to_dict_json_serializable(self):
        import json
        d = QMCPACKDigest(success=True, energy_Ha=-2.84)
        json_str = json.dumps(d.to_dict())
        assert "energy_Ha" in json_str


# ---------------------------------------------------------------------------
# parse_qmcpack_stdout_text tests
# ---------------------------------------------------------------------------

class TestParseStdoutText:
    def test_success_detection(self):
        d = parse_qmcpack_stdout_text(VMC_STDOUT_SUCCESS)
        assert d.success is True

    def test_error_detection(self):
        d = parse_qmcpack_stdout_text(ERROR_STDOUT)
        assert d.success is False

    def test_empty_stdout(self):
        d = parse_qmcpack_stdout_text(EMPTY_STDOUT)
        assert d.success is False

    def test_vmc_energy(self):
        d = parse_qmcpack_stdout_text(VMC_STDOUT_SUCCESS)
        assert d.energy_Ha is not None
        assert abs(d.energy_Ha - (-2.83818)) < 1e-4

    def test_vmc_variance(self):
        d = parse_qmcpack_stdout_text(VMC_STDOUT_SUCCESS)
        assert d.energy_variance is not None
        assert abs(d.energy_variance - 0.152471) < 1e-4

    def test_vmc_method(self):
        d = parse_qmcpack_stdout_text(VMC_STDOUT_SUCCESS)
        assert d.method == "vmc"

    def test_wall_time(self):
        d = parse_qmcpack_stdout_text(VMC_STDOUT_SUCCESS)
        assert d.wall_time_s is not None
        assert abs(d.wall_time_s - 1.0652) < 0.01

    def test_walker_count(self):
        d = parse_qmcpack_stdout_text(VMC_STDOUT_SUCCESS)
        assert d.n_walkers == 14

    def test_dmc_sections(self):
        d = parse_qmcpack_stdout_text(VMC_DMC_STDOUT)
        assert d.n_series == 2
        # Last section is DMC
        assert d.method == "dmc"
        assert abs(d.energy_Ha - (-2.87)) < 1e-4

    def test_dmc_wall_time(self):
        d = parse_qmcpack_stdout_text(VMC_DMC_STDOUT)
        assert abs(d.wall_time_s - 4.85) < 0.01


# ---------------------------------------------------------------------------
# QMCPACKOutputParser tests
# ---------------------------------------------------------------------------

class TestQMCPACKOutputParser:
    def test_can_parse_with_scalar(self, tmp_path):
        (tmp_path / "He.s000.scalar.dat").write_text(
            "# index LocalEnergy\n0 -2.84\n"
        )
        parser = QMCPACKOutputParser()
        assert parser.can_parse(tmp_path) is True

    def test_can_parse_empty_dir(self, tmp_path):
        parser = QMCPACKOutputParser()
        assert parser.can_parse(tmp_path) is False

    def test_parse_empty_dir(self, tmp_path):
        parser = QMCPACKOutputParser()
        d = parser.parse(tmp_path)
        assert d.error_message is not None

    def test_parse_with_scalar_dat(self, tmp_path):
        # Create a minimal scalar.dat
        scalar_content = (
            "#  index  LocalEnergy  Variance  AcceptRatio\n"
            "   0     -2.840000      0.1500     0.5200\n"
            "   1     -2.830000      0.1600     0.5100\n"
            "   2     -2.850000      0.1400     0.5300\n"
        )
        (tmp_path / "He.s000.scalar.dat").write_text(scalar_content)

        parser = QMCPACKOutputParser()
        d = parser.parse(tmp_path)
        assert d.success is True
        assert d.project_tag == "He"
        assert d.energy_Ha is not None
        assert abs(d.energy_Ha - (-2.84)) < 0.02
        assert d.n_blocks == 3

    def test_parse_with_stdout(self, tmp_path):
        scalar_content = (
            "#  index  LocalEnergy  AcceptRatio\n"
            "   0     -2.84     0.52\n"
        )
        (tmp_path / "He.s000.scalar.dat").write_text(scalar_content)
        (tmp_path / "stdout.log").write_text(VMC_STDOUT_SUCCESS)

        parser = QMCPACKOutputParser()
        d = parser.parse(tmp_path)
        assert d.success is True
        assert d.wall_time_s is not None
        assert d.n_walkers == 14

    def test_registration(self):
        from qmatsuite.parsers.registry import get_parser
        parser_cls = get_parser("qmcpack", "scf_digest")
        assert parser_cls is QMCPACKOutputParser
