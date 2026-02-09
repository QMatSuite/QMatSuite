"""Tests for explicit provenance replay analysis snapshot endpoint."""

from __future__ import annotations

from pathlib import Path

from ._analysis_pipeline_test_utils import setup_qe_bands_run


def test_get_analysis_snapshot_reads_sqlite_and_cas(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    run_ulid = ctx["run_ulid"]

    snapshot = svc.analysis.get_analysis_snapshot(run_ulid=run_ulid, object_type="bands")
    assert snapshot["run_ulid"] == run_ulid
    assert snapshot["object_type"] == "bands"
    assert len(snapshot["canonical_sha"]) == 64
    bundle = snapshot["bundle"]
    assert bundle["bundle_kind"] == "canonical"
    assert bundle["object_type"] == "bands"
