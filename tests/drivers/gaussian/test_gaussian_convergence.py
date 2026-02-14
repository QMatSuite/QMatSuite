"""Tests for Gaussian convergence analysis provider."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.gaussian.parsers.convergence import (
    GaussianConvergenceProvider,
    parse_gaussian_convergence,
)
from quantumvitas.parsers.registry import get_parser


# Minimal Gaussian SCF output snippet
GAUSSIAN_SCF_OUTPUT = """\
 Entering Gaussian System, Link 0=g09

 Charge =  0 Multiplicity = 1
 E= -76.0102345678     Delta-E=       -0.076023456780 Acc= 1.00D-06
 E= -76.3812345678     Delta-E=       -0.371000000000 Acc= 1.00D-06
 E= -76.4200805028     Delta-E=       -0.038846035000 Acc= 1.00D-06
 E= -76.4203805028     Delta-E=       -0.000300000000 Acc= 1.00D-06
 SCF Done:  E(RB3LYP) =  -76.4203805028     A.U. after   4 cycles

 Normal termination of Gaussian 09
"""

GAUSSIAN_OPT_OUTPUT = """\
 Entering Gaussian System, Link 0=g09

 Charge =  0 Multiplicity = 1
 E= -76.0102345678     Delta-E=       -0.076023456780 Acc= 1.00D-06
 E= -76.3812345678     Delta-E=       -0.371000000000 Acc= 1.00D-06
 SCF Done:  E(RB3LYP) =  -76.3812345678     A.U. after   2 cycles

 E= -76.4000000000     Delta-E=       -0.018765432200 Acc= 1.00D-06
 E= -76.4203805028     Delta-E=       -0.020380502800 Acc= 1.00D-06
 SCF Done:  E(RB3LYP) =  -76.4203805028     A.U. after   2 cycles

         Item               Value     Threshold  Converged?
 Optimization completed.
 -- Stationary point found.

 Normal termination of Gaussian 09
"""


class TestParseGaussianConvergence:
    """Tests for the raw parse function."""

    def test_scf_steps_extracted(self):
        result = parse_gaussian_convergence(GAUSSIAN_SCF_OUTPUT)
        assert len(result["scf_steps"]) == 4
        assert result["scf_steps"] == [1, 2, 3, 4]

    def test_scf_energies_in_ev(self):
        result = parse_gaussian_convergence(GAUSSIAN_SCF_OUTPUT)
        assert len(result["scf_energies"]) == 4
        assert all(e < 0 for e in result["scf_energies"])

    def test_scf_converged(self):
        result = parse_gaussian_convergence(GAUSSIAN_SCF_OUTPUT)
        assert result["converged"] is True

    def test_algorithm_extracted(self):
        result = parse_gaussian_convergence(GAUSSIAN_SCF_OUTPUT)
        assert result["algorithm"] == "RB3LYP"

    def test_opt_ionic_steps(self):
        result = parse_gaussian_convergence(GAUSSIAN_OPT_OUTPUT)
        assert len(result["ionic_steps"]) == 2
        assert result["ionic_steps"] == [1, 2]

    def test_opt_converged(self):
        result = parse_gaussian_convergence(GAUSSIAN_OPT_OUTPUT)
        assert result["converged"] is True

    def test_empty_output(self):
        result = parse_gaussian_convergence("")
        assert result["scf_steps"] == []
        assert result["scf_energies"] == []
        assert result["converged"] is False


class TestGaussianConvergenceProvider:
    """Tests for the provider class."""

    def test_registered_in_registry(self):
        cls = get_parser("gaussian", "convergence")
        assert cls is GaussianConvergenceProvider

    def test_can_parse_with_gaussian_output(self, tmp_path):
        log_file = tmp_path / "calc.log"
        log_file.write_text(GAUSSIAN_SCF_OUTPUT)
        provider = GaussianConvergenceProvider()
        assert provider.can_parse(tmp_path) is True

    def test_can_parse_returns_false_without_gaussian_output(self, tmp_path):
        provider = GaussianConvergenceProvider()
        assert provider.can_parse(tmp_path) is False

    def test_parse_scf_output(self, tmp_path):
        log_file = tmp_path / "calc.log"
        log_file.write_text(GAUSSIAN_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path,
            calc_dir=tmp_path,
            run_ulid="R1",
            calc_ulid="C1",
            step_ulids=["S1"],
            gen_steps=["scf"],
            engine_name="gaussian",
            evidence_steps=[],
        )
        provider = GaussianConvergenceProvider()
        conv = provider.parse(evidence)
        assert conv.converged is True
        assert len(conv.scf_step) == 4
        assert conv.meta.parser_name == "gaussian_convergence"
        assert conv.meta.engine_name == "gaussian"

    def test_parse_returns_convergence_with_to_primitives(self, tmp_path):
        log_file = tmp_path / "calc.log"
        log_file.write_text(GAUSSIAN_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path,
            calc_dir=tmp_path,
            run_ulid="R1",
            calc_ulid="C1",
            step_ulids=["S1"],
            gen_steps=["scf"],
            engine_name="gaussian",
            evidence_steps=[],
        )
        provider = GaussianConvergenceProvider()
        conv = provider.parse(evidence)
        bundle = conv.to_primitives()
        assert bundle.object_type == "convergence"
        assert len(bundle.series) > 0

    def test_parse_raises_on_missing_file(self, tmp_path):
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path,
            calc_dir=tmp_path,
            run_ulid="R1",
            calc_ulid="C1",
            step_ulids=["S1"],
            gen_steps=["scf"],
            engine_name="gaussian",
            evidence_steps=[],
        )
        provider = GaussianConvergenceProvider()
        with pytest.raises(FileNotFoundError):
            provider.parse(evidence)
