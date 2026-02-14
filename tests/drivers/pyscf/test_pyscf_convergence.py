"""Tests for PySCF convergence analysis provider."""
from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.core.analysis.evidence import EvidenceBundle
from quantumvitas.drivers.pyscf.parsers.convergence import (
    PySCFConvergenceProvider,
    parse_pyscf_convergence,
)
from quantumvitas.parsers.registry import get_parser


PYSCF_SCF_OUTPUT = """\
#INFO: PySCF 2.4.0
cycle= 1 E= -75.9701234568  delta_E= -75.97  |g|= 0.543  |ddm|= 1.23
cycle= 2 E= -76.0234567890  delta_E= -0.0533  |g|= 0.123  |ddm|= 0.45
cycle= 3 E= -76.0267567890  delta_E= -0.0033  |g|= 0.023  |ddm|= 0.12
cycle= 4 E= -76.0267890123  delta_E= -3.22e-05  |g|= 0.001  |ddm|= 0.01
converged SCF energy = -76.0267890123
"""


class TestParsePyscfConvergence:
    def test_scf_steps_extracted(self):
        result = parse_pyscf_convergence(PYSCF_SCF_OUTPUT)
        assert len(result["scf_steps"]) == 4
        assert result["scf_steps"] == [1, 2, 3, 4]

    def test_scf_energies_in_ev(self):
        result = parse_pyscf_convergence(PYSCF_SCF_OUTPUT)
        assert len(result["scf_energies"]) == 4
        assert all(e < 0 for e in result["scf_energies"])

    def test_converged(self):
        result = parse_pyscf_convergence(PYSCF_SCF_OUTPUT)
        assert result["converged"] is True

    def test_ionic_energy(self):
        result = parse_pyscf_convergence(PYSCF_SCF_OUTPUT)
        assert len(result["ionic_energies"]) == 1

    def test_empty_output(self):
        result = parse_pyscf_convergence("")
        assert result["scf_steps"] == []
        assert result["converged"] is False


class TestPySCFConvergenceProvider:
    def test_registered(self):
        assert get_parser("pyscf", "convergence") is PySCFConvergenceProvider

    def test_can_parse(self, tmp_path):
        (tmp_path / "pyscf.out").write_text(PYSCF_SCF_OUTPUT)
        assert PySCFConvergenceProvider().can_parse(tmp_path) is True

    def test_can_parse_empty(self, tmp_path):
        assert PySCFConvergenceProvider().can_parse(tmp_path) is False

    def test_parse(self, tmp_path):
        (tmp_path / "pyscf.out").write_text(PYSCF_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["scf"], engine_name="pyscf", evidence_steps=[],
        )
        conv = PySCFConvergenceProvider().parse(evidence)
        assert conv.converged is True
        assert len(conv.scf_step) == 4
        assert conv.meta.parser_name == "pyscf_convergence"

    def test_to_primitives(self, tmp_path):
        (tmp_path / "pyscf.out").write_text(PYSCF_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["scf"], engine_name="pyscf", evidence_steps=[],
        )
        bundle = PySCFConvergenceProvider().parse(evidence).to_primitives()
        assert bundle.object_type == "convergence"

    def test_raises_on_missing(self, tmp_path):
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["scf"], engine_name="pyscf", evidence_steps=[],
        )
        with pytest.raises(FileNotFoundError):
            PySCFConvergenceProvider().parse(evidence)
