"""Tests for Surface A raw file API endpoints."""

from __future__ import annotations

from pathlib import Path

from ._analysis_pipeline_test_utils import setup_qe_bands_run


def test_list_raw_files_returns_step_raw_artifacts(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    calc_ulid = ctx["calc_ulid"]
    step_ulid = ctx["step_ulid"]

    payload = svc.analysis.list_raw_files(
        calculation_selector=calc_ulid,
        step_selector=step_ulid,
    )

    assert "files" in payload
    assert "artifacts" in payload
    assert "si.bands.dat.gnu" in payload["files"]
    assert "si.3_bands.pp.out" in payload["files"]


def test_read_raw_file_returns_text_payload(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    calc_ulid = ctx["calc_ulid"]
    step_ulid = ctx["step_ulid"]

    payload = svc.analysis.read_step_artifact_text(
        calculation_selector=calc_ulid,
        step_selector=step_ulid,
        artifact_path="si.bands.dat.gnu",
        head_lines=1000,
        tail_lines=100,
    )

    assert "content" in payload
    assert "total_bytes" in payload
    assert payload["total_bytes"] > 0
    assert payload["truncated"] is False
    assert "resolved_path" in payload
