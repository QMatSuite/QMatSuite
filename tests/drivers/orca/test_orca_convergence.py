"""Tests for ORCA convergence analysis provider."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qmatsuite.core.analysis.evidence import EvidenceBundle
from qmatsuite.drivers.orca.parsers.convergence import (
    ORCAConvergenceProvider,
    parse_orca_convergence,
)
from qmatsuite.parsers.registry import get_parser


# Minimal ORCA SCF output snippet
ORCA_SCF_OUTPUT = """\
                            *****************
                            * O   R   C   A *
                            *****************

-------------------
FINAL SINGLE POINT ENERGY      -76.359831578643
-------------------

                          ---------------------
                          SCF CONVERGENCE OUTPUT
                          ---------------------

                     ITER       Energy            Delta-E        Max-DP      RMS-DP
                       0    -75.8823715264   0.000000000000 0.08812  0.00611
                       1    -75.9843829482  -0.102011421815 0.05791  0.00451
                       2    -76.0245073189  -0.040124370651 0.02113  0.00182
                       3    -76.3598295186  -0.335322199763 0.00510  0.00051
                       4    -76.3598315786  -0.000002060000 0.00032  0.00003

*                     SCF CONVERGED AFTER   5 CYCLES                     *

****ORCA TERMINATED NORMALLY****
Total run time: 0 days 0 hours 0 min 3 sec
"""

ORCA_OPT_OUTPUT = """\
                            *****************
                            * O   R   C   A *
                            *****************

         **** GEOMETRY OPTIMIZATION ****

                    --- GEOMETRY OPTIMIZATION CYCLE   1 ---

                     ITER       Energy            Delta-E        Max-DP      RMS-DP
                       0    -75.8823715264   0.000000000000 0.08812  0.00611
                       1    -76.3498315786  -0.467460052200 0.00032  0.00003

*                     SCF CONVERGED AFTER   2 CYCLES                     *

FINAL SINGLE POINT ENERGY      -76.349831578643

                    --- GEOMETRY OPTIMIZATION CYCLE   2 ---

                     ITER       Energy            Delta-E        Max-DP      RMS-DP
                       0    -76.3498315786   0.000000000000 0.01002  0.00101
                       1    -76.3598315786  -0.010000000000 0.00020  0.00002

*                     SCF CONVERGED AFTER   2 CYCLES                     *

FINAL SINGLE POINT ENERGY      -76.359831578643

            *****    HURRAY - THE OPTIMIZATION HAS CONVERGED     *****

****ORCA TERMINATED NORMALLY****
Total run time: 0 days 0 hours 0 min 10 sec
"""


class TestParseOrcaConvergence:
    """Tests for the raw parse function."""

    def test_scf_steps_extracted(self):
        result = parse_orca_convergence(ORCA_SCF_OUTPUT)
        assert len(result["scf_steps"]) == 5
        assert result["scf_steps"] == [1, 2, 3, 4, 5]

    def test_scf_energies_in_ev(self):
        result = parse_orca_convergence(ORCA_SCF_OUTPUT)
        assert len(result["scf_energies"]) == 5
        # Energies should be negative (Hartree * 27.2...)
        assert all(e < 0 for e in result["scf_energies"])

    def test_scf_converged(self):
        result = parse_orca_convergence(ORCA_SCF_OUTPUT)
        assert result["converged"] is True

    def test_algorithm(self):
        result = parse_orca_convergence(ORCA_SCF_OUTPUT)
        assert result["algorithm"] == "ORCA-SCF"

    def test_opt_ionic_steps(self):
        result = parse_orca_convergence(ORCA_OPT_OUTPUT)
        assert len(result["ionic_steps"]) == 2
        assert result["ionic_steps"] == [1, 2]

    def test_opt_converged(self):
        result = parse_orca_convergence(ORCA_OPT_OUTPUT)
        assert result["converged"] is True

    def test_empty_output(self):
        result = parse_orca_convergence("")
        assert result["scf_steps"] == []
        assert result["scf_energies"] == []
        assert result["converged"] is False


class TestORCAConvergenceProvider:
    """Tests for the provider class."""

    def test_registered_in_registry(self):
        cls = get_parser("orca", "convergence")
        assert cls is ORCAConvergenceProvider

    def test_can_parse_with_orca_output(self, tmp_path):
        out_file = tmp_path / "orca.out"
        out_file.write_text(ORCA_SCF_OUTPUT)
        provider = ORCAConvergenceProvider()
        assert provider.can_parse(tmp_path) is True

    def test_can_parse_returns_false_without_orca_output(self, tmp_path):
        provider = ORCAConvergenceProvider()
        assert provider.can_parse(tmp_path) is False

    def test_parse_scf_output(self, tmp_path):
        out_file = tmp_path / "orca.out"
        out_file.write_text(ORCA_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path,
            calc_dir=tmp_path,
            run_ulid="R1",
            calc_ulid="C1",
            step_ulids=["S1"],
            gen_steps=["scf"],
            engine_name="orca",
            evidence_steps=[],
        )
        provider = ORCAConvergenceProvider()
        conv = provider.parse(evidence)
        assert conv.converged is True
        assert len(conv.scf_step) == 5
        assert conv.meta.parser_name == "orca_convergence"
        assert conv.meta.engine_name == "orca"

    def test_parse_returns_convergence_with_to_primitives(self, tmp_path):
        out_file = tmp_path / "orca.out"
        out_file.write_text(ORCA_SCF_OUTPUT)
        evidence = EvidenceBundle(
            primary_raw_dir=tmp_path,
            calc_dir=tmp_path,
            run_ulid="R1",
            calc_ulid="C1",
            step_ulids=["S1"],
            gen_steps=["scf"],
            engine_name="orca",
            evidence_steps=[],
        )
        provider = ORCAConvergenceProvider()
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
            engine_name="orca",
            evidence_steps=[],
        )
        provider = ORCAConvergenceProvider()
        with pytest.raises(FileNotFoundError):
            provider.parse(evidence)
