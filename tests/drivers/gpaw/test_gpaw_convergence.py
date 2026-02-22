"""Tests for GPAW convergence analysis provider."""
from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.gpaw.parsers.convergence import (
    GPAWConvergenceProvider,
    parse_gpaw_convergence,
)
from qmatsuite.parsers.registry import get_parser


GPAW_SCF_OUTPUT = """\
  ___ ___ ___ _ _ _
 |   |   |_  | | | |
 | | | | | . | | | |
 |__ |  _|___|_____|  GPAW 22.8.0
 |___|_|

iter:   1  12:34:56  -15.12345  0.1230  log10-change= -1.23
iter:   2  12:34:57  -15.34567  0.0456  log10-change= -2.00
iter:   3  12:34:58  -15.34570  0.0001  log10-change= -4.50
iter:   4  12:34:59  -15.34570  0.0000  log10-change= -6.12

Converged after 4 iterations.

Free energy:   -15.34570
"""


class TestParseGpawConvergence:
    def test_scf_steps_extracted(self):
        result = parse_gpaw_convergence(GPAW_SCF_OUTPUT)
        assert len(result["scf_steps"]) == 4
        assert result["scf_steps"] == [1, 2, 3, 4]

    def test_scf_energies(self):
        result = parse_gpaw_convergence(GPAW_SCF_OUTPUT)
        assert len(result["scf_energies"]) == 4
        assert all(e < 0 for e in result["scf_energies"])

    def test_converged(self):
        result = parse_gpaw_convergence(GPAW_SCF_OUTPUT)
        assert result["converged"] is True

    def test_ionic_energy_from_free_energy(self):
        result = parse_gpaw_convergence(GPAW_SCF_OUTPUT)
        assert len(result["ionic_energies"]) == 1
        assert result["ionic_energies"][0] == pytest.approx(-15.34570, abs=0.001)

    def test_empty_output(self):
        result = parse_gpaw_convergence("")
        assert result["scf_steps"] == []
        assert result["converged"] is False


class TestGPAWConvergenceProvider:
    def test_registered_in_registry(self):
        cls = get_parser("gpaw", "convergence")
        assert cls is GPAWConvergenceProvider

    def test_can_parse(self, tmp_path):
        (tmp_path / "gpaw.txt").write_text(GPAW_SCF_OUTPUT)
        assert GPAWConvergenceProvider().can_parse(tmp_path) is True

    def test_can_parse_empty(self, tmp_path):
        assert GPAWConvergenceProvider().can_parse(tmp_path) is False

    def test_parse(self, tmp_path):
        (tmp_path / "gpaw.txt").write_text(GPAW_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["scf"], engine_name="gpaw", evidence_steps=[],
        )
        conv = GPAWConvergenceProvider().parse(evidence)
        assert conv.converged is True
        assert len(conv.scf_step) == 4
        assert conv.meta.parser_name == "gpaw_convergence"

    def test_to_primitives(self, tmp_path):
        (tmp_path / "gpaw.txt").write_text(GPAW_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["scf"], engine_name="gpaw", evidence_steps=[],
        )
        conv = GPAWConvergenceProvider().parse(evidence)
        bundle = conv.to_primitives()
        assert bundle.object_type == "convergence"

    def test_raises_on_missing(self, tmp_path):
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path, calc_dir=tmp_path,
            run_ulid="R1", calc_ulid="C1", step_ulids=["S1"],
            gen_steps=["scf"], engine_name="gpaw", evidence_steps=[],
        )
        with pytest.raises(FileNotFoundError):
            GPAWConvergenceProvider().parse(evidence)
