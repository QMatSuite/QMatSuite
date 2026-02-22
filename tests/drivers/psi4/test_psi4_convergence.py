"""Tests for Psi4 convergence analysis provider."""
from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.psi4.parsers.convergence import (
    Psi4ConvergenceProvider,
    parse_psi4_convergence,
)
from qmatsuite.parsers.registry import get_parser


PSI4_SCF_OUTPUT = """\

    -----------------------------------------------------------------------
          Psi4: An Open-Source Ab Initio Electronic Structure Package
    -----------------------------------------------------------------------

   @DF-RHF iter   1:   -75.97012345678901   -7.59701e+01   5.43210e-02 DIIS
   @DF-RHF iter   2:   -76.02345678901234   -5.33333e-02   1.23456e-02 DIIS
   @DF-RHF iter   3:   -76.02675678901234   -3.30000e-03   2.34567e-03 DIIS
   @DF-RHF iter   4:   -76.02678901234567   -3.22233e-05   4.56789e-04 DIIS

  Energy and wave function converged.

   @DF-RHF Final Energy:   -76.02678901234567
"""


class TestParsePsi4Convergence:
    def test_scf_steps_extracted(self):
        result = parse_psi4_convergence(PSI4_SCF_OUTPUT)
        assert len(result["scf_steps"]) == 4
        assert result["scf_steps"] == [1, 2, 3, 4]

    def test_scf_energies_in_ev(self):
        result = parse_psi4_convergence(PSI4_SCF_OUTPUT)
        assert len(result["scf_energies"]) == 4
        assert all(e < 0 for e in result["scf_energies"])

    def test_converged(self):
        result = parse_psi4_convergence(PSI4_SCF_OUTPUT)
        assert result["converged"] is True

    def test_algorithm(self):
        result = parse_psi4_convergence(PSI4_SCF_OUTPUT)
        assert "DF-RHF" in result["algorithm"]

    def test_ionic_energy(self):
        result = parse_psi4_convergence(PSI4_SCF_OUTPUT)
        assert len(result["ionic_energies"]) == 1

    def test_empty_output(self):
        result = parse_psi4_convergence("")
        assert result["scf_steps"] == []
        assert result["converged"] is False


class TestPsi4ConvergenceProvider:
    def test_registered(self):
        assert get_parser("psi4", "convergence") is Psi4ConvergenceProvider

    def test_can_parse(self, tmp_path):
        (tmp_path / "output.dat").write_text(PSI4_SCF_OUTPUT)
        assert Psi4ConvergenceProvider().can_parse(tmp_path) is True

    def test_can_parse_empty(self, tmp_path):
        assert Psi4ConvergenceProvider().can_parse(tmp_path) is False

    def test_parse(self, tmp_path):
        (tmp_path / "output.dat").write_text(PSI4_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["scf"], engine_name="psi4", evidence_steps=[],
        )
        conv = Psi4ConvergenceProvider().parse(evidence)
        assert conv.converged is True
        assert len(conv.scf_step) == 4
        assert conv.meta.parser_name == "psi4_convergence"

    def test_to_primitives(self, tmp_path):
        (tmp_path / "output.dat").write_text(PSI4_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["scf"], engine_name="psi4", evidence_steps=[],
        )
        bundle = Psi4ConvergenceProvider().parse(evidence).to_primitives()
        assert bundle.object_type == "convergence"

    def test_raises_on_missing(self, tmp_path):
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["scf"], engine_name="psi4", evidence_steps=[],
        )
        with pytest.raises(FileNotFoundError):
            Psi4ConvergenceProvider().parse(evidence)
