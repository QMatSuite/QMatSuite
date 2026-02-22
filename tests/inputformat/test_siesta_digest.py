"""Tests for Siesta output digest parser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qmatsuite.drivers.siesta.parsers.output import SiestaDigest, SiestaOutputParser
from qmatsuite.parsers.registry import get_parser


ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "docs" / "engines" / "siesta" / "artifacts"


class TestSiestaDigestDataclass:
    def test_defaults(self):
        d = SiestaDigest()
        assert d.final_energy_eV is None
        assert d.n_atoms == 0
        assert d.normal_exit is False

    def test_to_dict_json_serializable(self):
        d = SiestaDigest(final_energy_eV=-1.0, n_atoms=2, converged_electronic=True)
        payload = d.to_dict()
        text = json.dumps(payload)
        assert isinstance(text, str)


class TestSiestaOutputParserClass:
    def test_registry_lookup(self):
        import qmatsuite.drivers.siesta  # noqa: F401

        cls = get_parser("siesta", "scf_digest")
        assert cls is not None
        assert cls is SiestaOutputParser

    def test_can_parse_true_on_artifact(self):
        parser = SiestaOutputParser()
        assert parser.can_parse(ARTIFACTS_DIR / "h2o_scf") is True

    def test_can_parse_false_on_empty(self, tmp_path: Path):
        parser = SiestaOutputParser()
        assert parser.can_parse(tmp_path) is False

    def test_parse_missing_out(self, tmp_path: Path):
        parser = SiestaOutputParser()
        d = parser.parse(tmp_path)
        assert d.error_message is not None


class TestSiestaOutputParserOnRealArtifacts:
    @pytest.mark.parametrize(
        "case_name, expected_atoms, expected_energy",
        [
            ("h2o_scf", 3, -474.1735),
            ("si_scf", 2, -230.0361),
            ("si_relax", 2, -230.0519),
        ],
    )
    def test_parse_artifact_cases(self, case_name: str, expected_atoms: int, expected_energy: float):
        parser = SiestaOutputParser()
        case_dir = ARTIFACTS_DIR / case_name
        digest = parser.parse(case_dir)

        assert digest.error_message is None
        assert digest.n_atoms == expected_atoms
        assert digest.normal_exit is True
        assert digest.converged_electronic is True
        assert digest.final_energy_eV is not None
        assert abs(digest.final_energy_eV - expected_energy) < 5e-3

        if case_name == "si_relax":
            assert digest.n_ionic_steps >= 1
            assert digest.converged_ionic is True

    def test_parse_h2o_has_time_and_force(self):
        parser = SiestaOutputParser()
        digest = parser.parse(ARTIFACTS_DIR / "h2o_scf")

        assert digest.elapsed_time_s is not None
        assert digest.elapsed_time_s > 0.0
        assert digest.max_force_eV_A is not None
        assert digest.max_force_eV_A > 0.0

    def test_parse_si_relax_has_structure(self):
        parser = SiestaOutputParser()
        digest = parser.parse(ARTIFACTS_DIR / "si_relax")

        assert digest.final_lattice is not None
        assert len(digest.final_lattice) == 3
        assert digest.final_frac_coords is not None
        assert len(digest.final_frac_coords) == digest.n_atoms
        assert digest.volume_A3 is not None
        assert digest.volume_A3 > 0.0
