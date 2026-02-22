"""Yambo parser/writer tests using curated inputs and normalized corpus."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from qmatsuite.drivers.yambo.inputspec import get_yambo_input_spec
from qmatsuite.drivers.yambo.io.yambo_input import parse_yambo_input_text
from qmatsuite.inputformat import parse_engine_inputs, write_engine_inputs

SAMPLES_DIR = Path(__file__).parent / "samples" / "yambo"
NORMALIZED_DIR = Path(__file__).resolve().parents[2] / ".tmp" / "engine_research" / "yambo" / "normalized"

CASES = [
    ("si_gw_ppa", "gw", "gw.in"),
    ("si_bse_haydock", "bse", "bse.in"),
    ("si_ip_optics", "optics", "optics.in"),
    ("si_tddft_lrc", "optics", "optics.in"),
]


def _load_expected(case_dir: str, filename: str) -> dict:
    text = (SAMPLES_DIR / case_dir / filename).read_text(encoding="utf-8")
    return parse_yambo_input_text(text)


class TestYamboWriterAgainstCurated:
    @pytest.mark.parametrize("case_dir,gen_type,filename", CASES)
    def test_dict_to_input_semantics(self, tmp_path: Path, case_dir: str, gen_type: str, filename: str):
        expected = _load_expected(case_dir, filename)
        spec = get_yambo_input_spec(gen_type=gen_type)

        written = write_engine_inputs(spec, tmp_path, params=expected)
        assert (tmp_path / filename) in written

        observed = parse_yambo_input_text((tmp_path / filename).read_text(encoding="utf-8"))
        assert observed == expected


class TestYamboParserFromCurated:
    @pytest.mark.parametrize("case_dir,gen_type,filename", CASES)
    def test_input_to_dict(self, tmp_path: Path, case_dir: str, gen_type: str, filename: str):
        spec = get_yambo_input_spec(gen_type=gen_type)
        src = SAMPLES_DIR / case_dir / filename
        dst = tmp_path / filename
        shutil.copy2(src, dst)

        parsed = parse_engine_inputs(spec, tmp_path)
        expected = _load_expected(case_dir, filename)
        assert parsed.params == expected


class TestYamboSemanticRoundtrip:
    @pytest.mark.parametrize("case_dir,gen_type,filename", CASES)
    def test_parse_write_parse_roundtrip(self, tmp_path: Path, case_dir: str, gen_type: str, filename: str):
        spec = get_yambo_input_spec(gen_type=gen_type)
        shutil.copy2(SAMPLES_DIR / case_dir / filename, tmp_path / filename)

        parsed1 = parse_engine_inputs(spec, tmp_path)
        outdir = tmp_path / "rewrite"
        write_engine_inputs(spec, outdir, params=parsed1.params)
        parsed2 = parse_engine_inputs(spec, outdir)

        assert parsed2.params == parsed1.params


@pytest.mark.skipif(not NORMALIZED_DIR.is_dir(), reason="No normalized Yambo corpus in .tmp")
class TestYamboNormalizedCorpus:
    def test_parse_normalized_yambo_inputs(self):
        in_files = sorted(
            p for p in NORMALIZED_DIR.glob("**/*.in")
            if p.name in {"gw.in", "bse.in", "ip.in", "gw_generated.in", "bse_generated.in", "ip_generated.in"}
        )
        assert in_files, "Expected at least one normalized Yambo .in file"

        for path in in_files:
            parsed = parse_yambo_input_text(path.read_text(encoding="utf-8"))
            assert isinstance(parsed, dict)
            assert parsed, f"Parsed empty dict for {path}"
            assert "runlevels" in parsed
