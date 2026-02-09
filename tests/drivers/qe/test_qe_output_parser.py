"""Tests for QE SCF digest parser registration and parsing."""

from pathlib import Path

from quantumvitas.drivers.qe.parsers.output import QEOutputParser, QESCFDigest
from quantumvitas.parsers.registry import get_parser


REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_SCF_DIR = REPO_ROOT / "tests" / "data" / "analysis_scf"


def test_qe_scf_digest_parser_registered() -> None:
    parser_cls = get_parser("qe", "scf_digest")
    assert parser_cls is QEOutputParser


def test_qe_scf_digest_can_parse_and_parse() -> None:
    parser = QEOutputParser()
    assert parser.can_parse(TEST_SCF_DIR)

    digest = parser.parse(TEST_SCF_DIR)
    assert isinstance(digest, QESCFDigest)
    assert digest.total_energy_ry is not None
    assert digest.n_iterations > 0

