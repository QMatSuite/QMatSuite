"""Tests for Siesta FDF parser/writer and semantic roundtrip."""

from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Any

import pytest

from qmatsuite.drivers.siesta.inputspec import get_siesta_input_spec
from qmatsuite.drivers.siesta.io.fdf import parse_fdf_text
from qmatsuite.inputformat import parse_engine_inputs, write_engine_inputs


SAMPLES_DIR = Path(__file__).parent / "samples" / "siesta"
NORMALIZED_DIR = (
    Path(__file__).resolve().parents[2]
    / ".tmp"
    / "engine_research"
    / "siesta"
    / "normalized"
)

CASES = [
    "h2o_scf",
    "si_scf",
    "si_relax",
    "si_bands",
    "si_dos",
    "si_spin",
    "si_md",
    "si_vcrelax",
]


def _discover_case_fdf(case_dir: Path) -> Path:
    fdfs = sorted(case_dir.glob("*.fdf"))
    assert fdfs, f"No .fdf in {case_dir}"
    return fdfs[0]


def _canon_params(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    # Lowercase aliases are convenience duplicates inserted by parser.
    out.pop("system_name", None)
    out.pop("system_label", None)
    lc = out.get("LatticeConstant")
    if isinstance(lc, str):
        parts = lc.split()
        if parts:
            try:
                val = float(parts[0].replace("D", "e").replace("d", "e"))
                unit = parts[1].lower() if len(parts) > 1 else ""
                out["LatticeConstant"] = [val, unit]
            except ValueError:
                pass
    return out


def _assert_close(a: Any, b: Any, atol: float = 1e-8) -> None:
    if isinstance(a, bool) or isinstance(b, bool):
        assert a is b
        return

    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        assert math.isclose(float(a), float(b), abs_tol=atol, rel_tol=0.0), f"{a} != {b}"
        return

    if isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), f"List length mismatch: {len(a)} != {len(b)}"
        for x, y in zip(a, b):
            _assert_close(x, y, atol=atol)
        return

    if isinstance(a, dict) and isinstance(b, dict):
        assert set(a.keys()) == set(b.keys()), f"Dict keys mismatch: {set(a)} != {set(b)}"
        for k in a:
            _assert_close(a[k], b[k], atol=atol)
        return

    assert a == b


class TestSiestaParserOnCurated:
    @pytest.mark.parametrize("case_id", CASES)
    def test_curated_case_parses(self, case_id: str):
        case_dir = SAMPLES_DIR / case_id
        fdf = _discover_case_fdf(case_dir)

        parsed = parse_fdf_text(fdf.read_text(encoding="utf-8"))
        params = parsed["params"]
        structure = parsed["structure"]

        assert "SystemLabel" in params
        assert "SystemName" in params
        assert structure.get("species")

        # Every curated case should carry either frac or cart coordinates.
        assert ("frac_coords" in structure) or ("cart_coords" in structure)


class TestSiestaWriterAgainstCurated:
    @pytest.mark.parametrize("case_id", CASES)
    def test_yaml_to_inputs_matches_curated_semantics(self, tmp_path: Path, case_id: str):
        case_dir = SAMPLES_DIR / case_id
        fdf = _discover_case_fdf(case_dir)
        baseline = parse_fdf_text(fdf.read_text(encoding="utf-8"))

        label = baseline["params"].get("SystemLabel")
        assert isinstance(label, str) and label

        spec = get_siesta_input_spec(system_label=label)
        written = write_engine_inputs(
            spec,
            tmp_path,
            params=baseline["params"],
            structure=baseline["structure"],
        )

        assert len(written) == 1
        assert written[0].name == f"{label}.fdf"

        reparsed = parse_engine_inputs(spec, tmp_path)

        _assert_close(_canon_params(reparsed.params), _canon_params(baseline["params"]))
        assert reparsed.structure is not None
        _assert_close(reparsed.structure, baseline["structure"])


class TestSiestaRoundtrip:
    @pytest.mark.parametrize("case_id", CASES)
    def test_parse_write_parse_roundtrip(self, tmp_path: Path, case_id: str):
        case_dir = SAMPLES_DIR / case_id
        src_fdf = _discover_case_fdf(case_dir)

        parsed1 = parse_fdf_text(src_fdf.read_text(encoding="utf-8"))
        label = parsed1["params"].get("SystemLabel")
        spec = get_siesta_input_spec(system_label=label)

        # First materialization
        write_engine_inputs(spec, tmp_path, params=parsed1["params"], structure=parsed1["structure"])

        # Parse from orchestrator
        parsed2 = parse_engine_inputs(spec, tmp_path)

        # Rewrite to fresh dir then parse again
        out_dir = tmp_path / "rewrite"
        write_engine_inputs(spec, out_dir, params=parsed2.params, structure=parsed2.structure)
        parsed3 = parse_engine_inputs(spec, out_dir)

        _assert_close(_canon_params(parsed3.params), _canon_params(parsed2.params))
        assert parsed3.structure is not None
        assert parsed2.structure is not None
        _assert_close(parsed3.structure, parsed2.structure)


@pytest.mark.skipif(not NORMALIZED_DIR.is_dir(), reason="No normalized siesta corpus in .tmp")
class TestSiestaNormalizedCorpus:
    def test_parse_normalized_cases(self):
        case_dirs = sorted([p for p in NORMALIZED_DIR.iterdir() if p.is_dir()])
        assert case_dirs, "Expected at least one normalized siesta case"

        for case_dir in case_dirs:
            fdfs = sorted(case_dir.glob("*.fdf"))
            if not fdfs:
                continue
            fdf = fdfs[0]
            parsed = parse_fdf_text(fdf.read_text(encoding="utf-8"))
            assert isinstance(parsed.get("params"), dict)
            assert isinstance(parsed.get("structure"), dict)

    def test_orchestrator_parse_normalized_cases(self, tmp_path: Path):
        case_dirs = sorted([p for p in NORMALIZED_DIR.iterdir() if p.is_dir()])
        for case_dir in case_dirs:
            fdfs = sorted(case_dir.glob("*.fdf"))
            if not fdfs:
                continue
            src = fdfs[0]
            parsed = parse_fdf_text(src.read_text(encoding="utf-8"))
            label = parsed["params"].get("SystemLabel", "siesta")

            spec = get_siesta_input_spec(system_label=label)
            workdir = tmp_path / case_dir.name
            workdir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, workdir / f"{label}.fdf")

            result = parse_engine_inputs(spec, workdir)
            assert isinstance(result.params, dict)
            assert result.structure is None or isinstance(result.structure, dict)
