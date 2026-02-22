"""Tests for Yambo output digest parsing and registry integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.drivers.yambo.parsers.output import (
    YamboDigest,
    YamboOutputParser,
    parse_qp_file,
    parse_report_file,
    parse_spectrum_file,
)


QP_TEXT = """\
# QP corrections
1 4 0.000000 0.406459 0.100000
8 5 1.142710 1.090228 0.200000
"""

SPECTRUM_TEXT = """\
# eps spectrum
0.00000 0.00000 14.45286
0.10000 0.01000 14.42000
"""

REPORT_TEXT = """\
Version 5.3.0 Revision 23927
Bands : 50
K-points : 10
Filled Bands : 4
Direct Gap : 2.806544
Indirect Gap : 1.142707
Timing [Min/Max/Average] : 12s/12s/12s
[WARNING] Example warning
"""


class TestYamboDigestDataclass:
    def test_defaults(self):
        d = YamboDigest()
        assert d.success is False
        assert d.n_qp_corrections == 0
        assert d.n_spectrum_points == 0

    def test_to_dict_json_safe(self):
        d = YamboDigest(success=True, run_type="gw", n_qp_corrections=2)
        dd = d.to_dict()
        assert dd["success"] is True
        assert dd["run_type"] == "gw"


class TestYamboParsers:
    def test_parse_qp_file(self, tmp_path: Path):
        qp_path = tmp_path / "o-test.qp"
        qp_path.write_text(QP_TEXT, encoding="utf-8")
        qp = parse_qp_file(qp_path)
        assert len(qp.corrections) == 2
        assert qp.qp_gap is not None
        assert qp.dft_gap is not None
        assert qp.qp_gap > qp.dft_gap

    def test_parse_spectrum_file(self, tmp_path: Path):
        eps_path = tmp_path / "o-test.eps_q1_ip"
        eps_path.write_text(SPECTRUM_TEXT, encoding="utf-8")
        spec = parse_spectrum_file(eps_path)
        assert len(spec.points) == 2
        assert spec.spectrum_type == "ip"
        assert spec.static_dielectric == pytest.approx(14.45286)

    def test_parse_report_file(self, tmp_path: Path):
        rep_path = tmp_path / "r-test"
        rep_path.write_text(REPORT_TEXT, encoding="utf-8")
        rep = parse_report_file(rep_path)
        assert rep.version == "5.3.0"
        assert rep.n_bands == 50
        assert rep.n_kpoints == 10
        assert rep.filled_bands == 4
        assert rep.direct_gap == pytest.approx(2.806544)
        assert rep.indirect_gap == pytest.approx(1.142707)
        assert rep.wall_time_s == pytest.approx(12.0)
        assert len(rep.warnings) == 1


class TestYamboOutputParser:
    def test_can_parse_false_on_empty(self, tmp_path: Path):
        parser = YamboOutputParser()
        assert parser.can_parse(tmp_path) is False

    def test_can_parse_true_on_qp_file(self, tmp_path: Path):
        parser = YamboOutputParser()
        (tmp_path / "o-any.qp").write_text(QP_TEXT, encoding="utf-8")
        assert parser.can_parse(tmp_path) is True

    def test_parse_prefers_q1_spectrum(self, tmp_path: Path):
        parser = YamboOutputParser()
        (tmp_path / "o-spec.eps_q10_ip").write_text("0.0 0.0 9.0\n", encoding="utf-8")
        (tmp_path / "o-spec.eps_q1_ip").write_text("0.0 0.0 14.0\n", encoding="utf-8")
        digest = parser.parse(tmp_path)
        assert digest.success is True
        assert digest.static_dielectric == pytest.approx(14.0)

    def test_parse_qp_and_report(self, tmp_path: Path):
        parser = YamboOutputParser()
        (tmp_path / "o-test.qp").write_text(QP_TEXT, encoding="utf-8")
        (tmp_path / "r-test").write_text(REPORT_TEXT, encoding="utf-8")
        digest = parser.parse(tmp_path)
        assert digest.success is True
        assert digest.run_type == "gw"
        assert digest.n_qp_corrections == 2
        assert digest.n_bands == 50
        assert digest.n_kpoints == 10

    def test_parse_empty_directory(self, tmp_path: Path):
        parser = YamboOutputParser()
        digest = parser.parse(tmp_path)
        assert digest.success is False
        assert digest.error_message is not None


class TestParserRegistry:
    def test_registered_in_registry(self):
        from qmatsuite.parsers.registry import get_parser

        parser = get_parser("yambo", "scf_digest")
        assert parser is not None
        assert parser.engine == "yambo"
        assert parser.object_type == "scf_digest"
