"""Tests for LAMMPS output digest (LAMMPSDigest + LAMMPSOutputParser).

Validates the log.lammps parser against inline test logs and all 7 existing
validation runs under .tmp/engine_research/lammps/runs/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.drivers.lammps.parsers.output import (
    LAMMPSDigest,
    LAMMPSOutputParser,
    parse_lammps_log_text,
)


# ──────────────────────────────────────────────────────────────────────────
# Inline log parsing tests
# ──────────────────────────────────────────────────────────────────────────


MD_LOG = """\
LAMMPS (22 Jul 2025 - Update 3)
units lj
Step Temp E_pair E_mol TotEng Press
       0   3.0000000 -6.7733681   0.0000000 -2.2744931   -3.196758
      50   1.6893117 -4.6266612   0.0000000 -2.0927455   5.3788728
     250   1.6645597 -4.7779771   0.0000000 -2.2812174   5.7526089
Loop time of 0.404052 on 1 procs for 250 steps with 4000 atoms
Total wall time: 0:00:00
"""

MINIMIZE_LOG = """\
LAMMPS (22 Jul 2025 - Update 3)
units lj
Step Temp E_pair E_mol TotEng Press
       0   5.0000000 -2.4610225   0.0000000  2.5389775  23.823506
    1000   3.3035117 -2.9121093   0.0000000  0.38850143  1.8620908
Loop time of 0.0394001 on 1 procs for 1000 steps with 800 atoms
Step Temp E_pair E_mol TotEng Press
    1000   3.3035117 -2.9121093   0.0000000  0.38850143  1.8620908
    1388   3.2939531 -2.9154117   0.0000000  0.38947006  1.8531667
Loop time of 0.0157609 on 1 procs for 388 steps with 800 atoms
Minimization stats:
  Stopping criterion = linesearch alpha is zero
  Energy initial, next-to-last, final =
     0.388501425949975   0.389470063917073   0.389470063917073
  Force two-norm initial, final = 1.4345782 0.0012879116
  Force max component initial, final = 0.25988362 0.00013155399
  Final line search alpha, currentEnergy = 9.7656e-06 0.38947006
  Iterations, force evaluations = 388 1113
Total wall time: 0:00:00
"""

ERROR_LOG = """\
LAMMPS (22 Jul 2025 - Update 3)
ERROR: Unknown pair style lj/cutt (src/force.cpp:256)
"""

LOST_ATOMS_LOG = """\
LAMMPS (22 Jul 2025 - Update 3)
Step Temp TotEng
       0   1.0  -2.0
     100   1.1  -1.9
WARNING: Lost atoms: original 1000 current 998
Loop time of 0.1 on 1 procs for 100 steps with 998 atoms
Total wall time: 0:00:01
"""


class TestLogParsing:
    """Unit tests for parse_lammps_log_text."""

    def test_md_log_success(self):
        d = parse_lammps_log_text(MD_LOG)
        assert d.success is True
        assert d.error_message is None

    def test_md_log_energy(self):
        d = parse_lammps_log_text(MD_LOG)
        assert d.final_energy is not None
        assert abs(d.final_energy - (-2.2812174)) < 1e-6

    def test_md_log_temp(self):
        d = parse_lammps_log_text(MD_LOG)
        assert abs(d.final_temp - 1.6645597) < 1e-6

    def test_md_log_pressure(self):
        d = parse_lammps_log_text(MD_LOG)
        assert abs(d.final_pressure - 5.7526089) < 1e-6

    def test_md_log_atoms_steps(self):
        d = parse_lammps_log_text(MD_LOG)
        assert d.n_atoms == 4000
        assert d.n_steps == 250

    def test_md_log_units(self):
        d = parse_lammps_log_text(MD_LOG)
        assert d.units == "lj"

    def test_minimize_converged(self):
        d = parse_lammps_log_text(MINIMIZE_LOG)
        assert d.success is True
        assert d.converged_minimize is True
        assert d.minimize_iterations == 388
        assert d.minimize_force_evaluations == 1113

    def test_minimize_criterion(self):
        d = parse_lammps_log_text(MINIMIZE_LOG)
        assert d.minimize_criterion == "linesearch alpha is zero"

    def test_minimize_energy_values(self):
        d = parse_lammps_log_text(MINIMIZE_LOG)
        assert abs(d.minimize_energy_initial - 0.388501425949975) < 1e-10
        assert abs(d.minimize_energy_final - 0.389470063917073) < 1e-10

    def test_minimize_last_thermo(self):
        """Multi-phase log: should extract from last thermo block."""
        d = parse_lammps_log_text(MINIMIZE_LOG)
        assert abs(d.final_energy - 0.38947006) < 1e-6
        assert d.n_atoms == 800
        assert d.n_steps == 388  # last Loop time

    def test_error_log(self):
        d = parse_lammps_log_text(ERROR_LOG)
        assert d.success is False
        assert d.error_message is not None
        assert "Unknown pair style" in d.error_message

    def test_lost_atoms_log(self):
        d = parse_lammps_log_text(LOST_ATOMS_LOG)
        assert d.error_message is not None
        assert "ost atoms" in d.error_message.lower() or "lost" in d.error_message.lower()

    def test_empty_log(self):
        d = parse_lammps_log_text("")
        assert d.success is False

    def test_wall_time_hms(self):
        d = parse_lammps_log_text(MD_LOG)
        assert d.wall_time_s == 0  # 0:00:00

    def test_wall_time_nonzero(self):
        d = parse_lammps_log_text(LOST_ATOMS_LOG)
        assert d.wall_time_s == 1  # 0:00:01

    def test_to_dict(self):
        d = parse_lammps_log_text(MD_LOG)
        dd = d.to_dict()
        assert isinstance(dd, dict)
        assert dd["success"] is True
        assert dd["n_atoms"] == 4000


# ──────────────────────────────────────────────────────────────────────────
# LAMMPSOutputParser class tests
# ──────────────────────────────────────────────────────────────────────────


class TestOutputParserClass:
    """Tests for LAMMPSOutputParser can_parse and parse methods."""

    def test_can_parse_true(self, tmp_path):
        (tmp_path / "log.lammps").write_text(MD_LOG)
        parser = LAMMPSOutputParser()
        assert parser.can_parse(tmp_path) is True

    def test_can_parse_false(self, tmp_path):
        parser = LAMMPSOutputParser()
        assert parser.can_parse(tmp_path) is False

    def test_parse_directory(self, tmp_path):
        (tmp_path / "log.lammps").write_text(MD_LOG)
        parser = LAMMPSOutputParser()
        d = parser.parse(tmp_path)
        assert d.success is True
        assert d.n_atoms == 4000

    def test_parse_missing_log(self, tmp_path):
        parser = LAMMPSOutputParser()
        d = parser.parse(tmp_path)
        assert d.success is False
        assert "No log.lammps" in d.error_message

    def test_parser_registration(self):
        from qmatsuite.parsers.registry import get_parser
        parser_cls = get_parser("lammps", "scf_digest")
        assert parser_cls is not None
        assert parser_cls is LAMMPSOutputParser


# ──────────────────────────────────────────────────────────────────────────
# Validation against 7 existing runs
# ──────────────────────────────────────────────────────────────────────────


# Resolve relative to the project root (two levels up from tests/inputformat/)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = _PROJECT_ROOT / ".tmp" / "engine_research" / "lammps" / "runs"


@pytest.mark.skipif(
    not RUNS_DIR.is_dir(),
    reason="Validation run logs not available",
)
class TestValidationRuns:
    """Validate digest against 7 existing LAMMPS validation runs."""

    def test_melt_lj_nve(self):
        d = self._parse("melt_lj_nve")
        assert d.success is True
        assert d.n_atoms == 4000
        assert d.n_steps == 250
        assert d.units == "lj"
        assert abs(d.final_energy - (-2.2812174)) < 0.01

    def test_minimize_2d_lj(self):
        d = self._parse("minimize_2d_lj")
        assert d.success is True
        assert d.n_atoms == 800
        assert d.converged_minimize is True
        assert d.minimize_iterations == 388
        assert d.units == "lj"

    def test_crack_2d_lj(self):
        d = self._parse("crack_2d_lj")
        assert d.success is True
        assert d.n_atoms == 8141
        assert d.n_steps == 5000

    def test_flow_couette_2d(self):
        d = self._parse("flow_couette_2d")
        assert d.success is True
        assert d.n_atoms == 420
        assert d.n_steps == 10000

    def test_indent_2d_lj(self):
        d = self._parse("indent_2d_lj")
        assert d.success is True
        assert d.n_atoms == 420
        assert d.n_steps == 30000

    def test_tersoff_sic(self):
        d = self._parse("tersoff_sic")
        assert d.success is True
        assert d.n_atoms == 512
        assert d.units == "metal"

    def test_shear_metal_eam(self):
        d = self._parse("shear_metal_eam")
        assert d.success is True
        assert d.n_atoms == 1912
        assert d.units == "metal"
        assert d.n_steps == 3000

    def _parse(self, case_id: str) -> LAMMPSDigest:
        log_path = RUNS_DIR / case_id / "log.lammps"
        text = log_path.read_text(errors="replace")
        return parse_lammps_log_text(text)
