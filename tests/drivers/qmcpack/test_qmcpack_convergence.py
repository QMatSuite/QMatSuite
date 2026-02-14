"""Tests for QMCPACK convergence analysis provider."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.qmcpack.parsers.convergence import (
    QMCPACKConvergenceProvider,
    parse_qmcpack_convergence,
)
from quantumvitas.parsers.registry import get_parser


QMCPACK_SCALAR_DAT = """\
#  index  LocalEnergy  Variance  Kinetic  LocalPotential
   0     -2.87654321   0.0123   1.5432   -4.4198
   1     -2.87654400   0.0121   1.5430   -4.4195
   2     -2.87654500   0.0119   1.5428   -4.4193
   3     -2.87654600   0.0118   1.5427   -4.4192
   4     -2.87654550   0.0120   1.5429   -4.4194
"""


class TestParseQmcpackConvergence:
    def test_scf_steps_extracted(self):
        result = parse_qmcpack_convergence(QMCPACK_SCALAR_DAT)
        assert len(result["scf_steps"]) == 5
        assert result["scf_steps"] == [0, 1, 2, 3, 4]

    def test_scf_energies_in_ev(self):
        result = parse_qmcpack_convergence(QMCPACK_SCALAR_DAT)
        assert len(result["scf_energies"]) == 5
        # All should be negative (Hartree -> eV)
        assert all(e < 0 for e in result["scf_energies"])

    def test_converged(self):
        result = parse_qmcpack_convergence(QMCPACK_SCALAR_DAT)
        assert result["converged"] is True  # QMC with data = converged

    def test_ionic_energy_is_mean(self):
        result = parse_qmcpack_convergence(QMCPACK_SCALAR_DAT)
        assert len(result["ionic_energies"]) == 1
        # Mean of converted energies
        expected_mean = np.mean([e * 27.211386245988 for e in [-2.87654321, -2.87654400, -2.87654500, -2.87654600, -2.87654550]])
        assert result["ionic_energies"][0] == pytest.approx(expected_mean, rel=1e-6)

    def test_algorithm(self):
        result = parse_qmcpack_convergence(QMCPACK_SCALAR_DAT)
        assert result["algorithm"] == "QMC"

    def test_empty_output(self):
        result = parse_qmcpack_convergence("")
        assert result["scf_steps"] == []
        assert result["converged"] is False


class TestQMCPACKConvergenceProvider:
    def test_registered(self):
        assert get_parser("qmcpack", "convergence") is QMCPACKConvergenceProvider

    def test_can_parse(self, tmp_path):
        (tmp_path / "vmc.scalar.dat").write_text(QMCPACK_SCALAR_DAT)
        assert QMCPACKConvergenceProvider().can_parse(tmp_path) is True

    def test_can_parse_empty(self, tmp_path):
        assert QMCPACKConvergenceProvider().can_parse(tmp_path) is False

    def test_parse(self, tmp_path):
        (tmp_path / "vmc.scalar.dat").write_text(QMCPACK_SCALAR_DAT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["vmc"], engine_name="qmcpack", evidence_steps=[],
        )
        conv = QMCPACKConvergenceProvider().parse(evidence)
        assert conv.converged is True
        assert len(conv.scf_step) == 5
        assert conv.meta.parser_name == "qmcpack_convergence"

    def test_to_primitives(self, tmp_path):
        (tmp_path / "vmc.scalar.dat").write_text(QMCPACK_SCALAR_DAT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["vmc"], engine_name="qmcpack", evidence_steps=[],
        )
        bundle = QMCPACKConvergenceProvider().parse(evidence).to_primitives()
        assert bundle.object_type == "convergence"

    def test_raises_on_missing(self, tmp_path):
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["vmc"], engine_name="qmcpack", evidence_steps=[],
        )
        with pytest.raises(FileNotFoundError):
            QMCPACKConvergenceProvider().parse(evidence)
