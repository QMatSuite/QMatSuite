"""Tests for Gaussian output digest (GaussianDigest + GaussianOutputParser).

Validates the output parser against inline test logs and validation run
outputs from .tmp/engine_research/gaussian/runs/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.drivers.gaussian.parsers.output import (
    GaussianDigest,
    GaussianOutputParser,
    parse_gaussian_output_text,
)


# ──────────────────────────────────────────────────────────────────────────
# Inline log parsing tests
# ──────────────────────────────────────────────────────────────────────────


SCF_LOG = """\
 Entering Gaussian System, Link 0=/path/to/g09
 Charge =  0 Multiplicity = 1
 SCF Done:  E(RHF) =  -74.9631155184     A.U. after    7 cycles
 Dipole moment (field-independent basis, Debye):
    X=              0.0000    Y=              0.0000    Z=             -1.7255  Tot=              1.7255

                          Standard orientation:
 ---------------------------------------------------------------------
 Center     Atomic      Atomic             Coordinates (Angstroms)
  Number     Number       Type             X           Y           Z
 ---------------------------------------------------------------------
      1          8           0        0.000000    0.000000    0.117499
      2          1           0        0.000000    0.756950   -0.469996
      3          1           0        0.000000   -0.756950   -0.469996
 ---------------------------------------------------------------------
 Normal termination of Gaussian 09, Link  9999.
"""

MP2_LOG = """\
 Entering Gaussian System, Link 0=/path/to/g09
 Charge =  0 Multiplicity = 1
 SCF Done:  E(RHF) =  -77.0728565498     A.U. after    8 cycles
 E2 =    -0.1218324231D+00 EUMP2 =    -0.77194688921108D+02
 Normal termination of Gaussian 09, Link  9999.
"""

OPT_LOG = """\
 Entering Gaussian System, Link 0=/path/to/g09
 Charge =  0 Multiplicity = 1
 SCF Done:  E(RB3LYP) =  -76.4091784221     A.U. after    9 cycles
 SCF Done:  E(RB3LYP) =  -76.4094112541     A.U. after    8 cycles
 SCF Done:  E(RB3LYP) =  -76.4094121433     A.U. after    6 cycles
          Item               Value     Threshold  Converged?
 Optimization completed.
 Normal termination of Gaussian 09, Link  9999.
"""

TDDFT_LOG = """\
 Entering Gaussian System, Link 0=/path/to/g09
 Charge =  0 Multiplicity = 1
 SCF Done:  E(RB3LYP) =  -113.221568823     A.U. after   10 cycles
 Excited State   1:      Singlet-A2     4.0615 eV  305.26 nm  f=0.0000  <S**2>=0.000
 Excited State   2:      Singlet-A1     9.4829 eV  130.78 nm  f=0.0148  <S**2>=0.000
 Excited State   3:      Singlet-B2    12.0041 eV  103.30 nm  f=0.0018  <S**2>=0.000
 Normal termination of Gaussian 09, Link  9999.
"""

FREQ_LOG = """\
 Entering Gaussian System, Link 0=/path/to/g09
 Charge =  0 Multiplicity = 1
 SCF Done:  E(RHF) =  -74.9631155184     A.U. after    7 cycles
 Frequencies --   2169.8207              4141.9658              4393.0665
 Zero-point correction=                           0.024387 (Hartree/Particle)
 Thermal correction to Energy=                    0.027220
 Thermal correction to Enthalpy=                  0.028164
 Thermal correction to Gibbs Free Energy=         0.006650
 Normal termination of Gaussian 09, Link  9999.
"""

ERROR_LOG = """\
 Entering Gaussian System, Link 0=/path/to/g09
 Charge =  0 Multiplicity = 1
 SCF Done:  E(RHF) =  -74.9631155184     A.U. after   128 cycles
 Error termination via Lnk1e in /path/to/l502.exe
"""

LINK1_LOG = """\
 Entering Gaussian System, Link 0=/path/to/g09
 Charge =  0 Multiplicity = 1
 SCF Done:  E(RHF) =  -74.9631155184     A.U. after    7 cycles
 Normal termination of Gaussian 09, Link  9999.
 Entering Gaussian System, Link 0=/path/to/g09
 SCF Done:  E(RHF) =  -74.9631155184     A.U. after    7 cycles
 E2 =    -0.0123456789D+00 EUMP2 =    -0.74975462107293D+02
 Normal termination of Gaussian 09, Link  9999.
"""


class TestLogParsing:
    """Unit tests for parse_gaussian_output_text."""

    def test_scf_success(self):
        d = parse_gaussian_output_text(SCF_LOG)
        assert d.success is True
        assert d.scf_method == "RHF"
        assert abs(d.final_energy_Ha - (-74.9631155184)) < 1e-10
        assert d.n_scf_cycles == 7
        assert d.converged_scf is True
        assert d.error_message is None

    def test_scf_energy_ev(self):
        d = parse_gaussian_output_text(SCF_LOG)
        assert d.final_energy_eV is not None
        assert abs(d.final_energy_eV - d.final_energy_Ha * 27.211386245988) < 1e-6

    def test_scf_geometry(self):
        d = parse_gaussian_output_text(SCF_LOG)
        assert d.n_atoms == 3
        assert d.final_species == ["O", "H", "H"]
        assert len(d.final_cart_coords) == 3
        assert abs(d.final_cart_coords[0][2] - 0.117499) < 1e-5

    def test_scf_dipole(self):
        d = parse_gaussian_output_text(SCF_LOG)
        assert d.dipole_debye is not None
        assert abs(d.dipole_debye - 1.7255) < 1e-4

    def test_scf_charge_mult(self):
        d = parse_gaussian_output_text(SCF_LOG)
        assert d.charge == 0
        assert d.multiplicity == 1

    def test_mp2_energy(self):
        d = parse_gaussian_output_text(MP2_LOG)
        assert d.success is True
        assert d.mp2_energy_Ha is not None
        assert abs(d.mp2_energy_Ha - (-77.194688921108)) < 1e-6
        assert d.e2_correlation_Ha is not None
        assert abs(d.e2_correlation_Ha - (-0.1218324231)) < 1e-8
        # Final energy should be MP2 (not SCF)
        assert abs(d.final_energy_Ha - d.mp2_energy_Ha) < 1e-10

    def test_optimization(self):
        d = parse_gaussian_output_text(OPT_LOG)
        assert d.success is True
        assert d.converged_geometry is True
        assert d.n_opt_steps == 3

    def test_tddft_states(self):
        d = parse_gaussian_output_text(TDDFT_LOG)
        assert d.success is True
        assert d.tddft_states is not None
        assert len(d.tddft_states) == 3
        assert d.tddft_states[0]["state"] == 1
        assert abs(d.tddft_states[0]["energy_eV"] - 4.0615) < 1e-4
        assert abs(d.tddft_states[1]["energy_eV"] - 9.4829) < 1e-4

    def test_frequencies(self):
        d = parse_gaussian_output_text(FREQ_LOG)
        assert d.success is True
        assert d.frequencies_cm is not None
        assert len(d.frequencies_cm) == 3
        assert abs(d.frequencies_cm[0] - 2169.8207) < 1e-3
        assert d.imaginary_freq_count == 0
        assert d.zpe_Ha is not None
        assert abs(d.zpe_Ha - 0.024387) < 1e-6

    def test_error_termination(self):
        d = parse_gaussian_output_text(ERROR_LOG)
        assert d.success is False
        assert d.error_message is not None
        assert "Error termination" in d.error_message

    def test_link1_chain(self):
        d = parse_gaussian_output_text(LINK1_LOG)
        assert d.success is True
        assert d.n_link1_jobs == 2
        # Final energy should be from the last job (MP2)
        assert d.mp2_energy_Ha is not None

    def test_empty_text(self):
        d = parse_gaussian_output_text("")
        assert d.success is False
        assert d.final_energy_Ha is None

    def test_digest_to_dict(self):
        d = parse_gaussian_output_text(SCF_LOG)
        d_dict = d.to_dict()
        assert isinstance(d_dict, dict)
        assert d_dict["success"] is True
        assert "final_energy_Ha" in d_dict


# ──────────────────────────────────────────────────────────────────────────
# Parser class tests
# ──────────────────────────────────────────────────────────────────────────


class TestGaussianOutputParser:
    """Tests for the GaussianOutputParser class."""

    def test_can_parse_with_log(self, tmp_path):
        (tmp_path / "output.log").write_text(
            "Entering Gaussian System\nNormal termination of Gaussian 09"
        )
        parser = GaussianOutputParser()
        assert parser.can_parse(tmp_path) is True

    def test_can_parse_no_files(self, tmp_path):
        parser = GaussianOutputParser()
        assert parser.can_parse(tmp_path) is False

    def test_can_parse_non_gaussian(self, tmp_path):
        (tmp_path / "output.log").write_text("This is not a Gaussian file")
        parser = GaussianOutputParser()
        assert parser.can_parse(tmp_path) is False

    def test_parse_from_dir(self, tmp_path):
        (tmp_path / "output.log").write_text(SCF_LOG)
        parser = GaussianOutputParser()
        d = parser.parse(tmp_path)
        assert d.success is True
        assert d.final_energy_Ha is not None

    def test_parse_no_output(self, tmp_path):
        parser = GaussianOutputParser()
        d = parser.parse(tmp_path)
        assert d.error_message is not None

    def test_engine_object_type(self):
        parser = GaussianOutputParser()
        assert parser.engine == "gaussian"
        assert parser.object_type == "scf_digest"


# ──────────────────────────────────────────────────────────────────────────
# Registry integration test
# ──────────────────────────────────────────────────────────────────────────


class TestParserRegistry:
    """Verify the parser is properly registered."""

    def test_registry_lookup(self):
        from quantumvitas.parsers.registry import get_parser
        cls = get_parser("gaussian", "scf_digest")
        assert cls is GaussianOutputParser

    def test_registry_find_for_raw(self, tmp_path):
        from quantumvitas.parsers.registry import find_parser_for_raw
        (tmp_path / "output.log").write_text(
            "Entering Gaussian System\nSCF Done: E(RHF) = -74.963\n"
            "Normal termination of Gaussian 09"
        )
        cls = find_parser_for_raw(tmp_path, "scf_digest")
        assert cls is not None


# ──────────────────────────────────────────────────────────────────────────
# Validation runs (if available)
# ──────────────────────────────────────────────────────────────────────────


_RUNS_DIR = Path(__file__).resolve().parents[2] / ".tmp" / "engine_research" / "gaussian" / "runs"


@pytest.mark.skipif(not _RUNS_DIR.is_dir(), reason="No Gaussian validation runs")
class TestValidationRuns:
    """Parse real Gaussian output logs from validation runs."""

    def _parse_run(self, case_id: str) -> GaussianDigest:
        run_dir = _RUNS_DIR / case_id
        parser = GaussianOutputParser()
        return parser.parse(run_dir)

    @pytest.mark.skipif(
        not (_RUNS_DIR / "water_hf_sp" / "output.log").is_file(),
        reason="water_hf_sp run not available",
    )
    def test_water_hf_sp(self):
        d = self._parse_run("water_hf_sp")
        assert d.success is True
        assert d.scf_method == "RHF"
        assert d.final_energy_Ha is not None
        assert -76 < d.final_energy_Ha < -73
        assert d.n_scf_cycles is not None
        assert d.n_atoms == 3

    @pytest.mark.skipif(
        not (_RUNS_DIR / "ethylene_mp2" / "output.log").is_file(),
        reason="ethylene_mp2 run not available",
    )
    def test_ethylene_mp2(self):
        d = self._parse_run("ethylene_mp2")
        assert d.success is True
        assert d.mp2_energy_Ha is not None
        assert d.e2_correlation_Ha is not None
        assert d.e2_correlation_Ha < 0  # correlation is negative

    @pytest.mark.skipif(
        not (_RUNS_DIR / "water_b3lyp_opt" / "output.log").is_file(),
        reason="water_b3lyp_opt run not available",
    )
    def test_water_b3lyp_opt(self):
        d = self._parse_run("water_b3lyp_opt")
        assert d.success is True
        assert d.converged_geometry is True

    @pytest.mark.skipif(
        not (_RUNS_DIR / "formaldehyde_tddft" / "output.log").is_file(),
        reason="formaldehyde_tddft run not available",
    )
    def test_formaldehyde_tddft(self):
        d = self._parse_run("formaldehyde_tddft")
        assert d.success is True
        assert d.tddft_states is not None
        assert len(d.tddft_states) == 3
        assert d.tddft_states[0]["energy_eV"] > 0

    @pytest.mark.skipif(
        not (_RUNS_DIR / "o2_triplet_uhf" / "output.log").is_file(),
        reason="o2_triplet_uhf run not available",
    )
    def test_o2_triplet_uhf(self):
        d = self._parse_run("o2_triplet_uhf")
        assert d.success is True
        assert d.final_energy_Ha is not None

    @pytest.mark.skipif(
        not (_RUNS_DIR / "multi_step_link1" / "output.log").is_file(),
        reason="multi_step_link1 run not available",
    )
    def test_multi_step_link1(self):
        d = self._parse_run("multi_step_link1")
        assert d.success is True
        assert d.n_link1_jobs >= 2

    @pytest.mark.skipif(
        not (_RUNS_DIR / "methanol_solvation" / "output.log").is_file(),
        reason="methanol_solvation run not available",
    )
    def test_methanol_solvation(self):
        d = self._parse_run("methanol_solvation")
        assert d.success is True
        assert d.final_energy_Ha is not None

    @pytest.mark.skipif(
        not (_RUNS_DIR / "hcn_scan" / "output.log").is_file(),
        reason="hcn_scan run not available",
    )
    def test_hcn_scan(self):
        d = self._parse_run("hcn_scan")
        assert d.success is True
        assert d.final_energy_Ha is not None
