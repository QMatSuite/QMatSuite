"""Tests for analysis source-file staleness detection."""

from __future__ import annotations

from pathlib import Path

from qmatsuite.core.analysis.base import AnalysisObjectMeta, SourceFileStat, check_staleness


def test_check_staleness_detects_source_change(tmp_path: Path) -> None:
    calc_dir = tmp_path / "calc"
    raw_dir = calc_dir / "raw"
    raw_dir.mkdir(parents=True)
    source_path = raw_dir / "bands.out"
    source_path.write_text("initial", encoding="utf-8")

    source_stat = SourceFileStat.from_path(source_path, calc_dir)
    meta = AnalysisObjectMeta.create(
        object_type="bands",
        source_files=[source_stat],
        run_ulid="01RUN",
        calc_ulid="01CALC",
        step_ulids=["01STEP1"],
        gen_steps=["bandspw"],
        engine_name="qe",
        parser_name="qe_bands",
        parser_version="1.0",
    )

    assert check_staleness(meta, calc_dir=calc_dir) is False

    source_path.write_text("initial + changed", encoding="utf-8")
    assert check_staleness(meta, calc_dir=calc_dir) is True
