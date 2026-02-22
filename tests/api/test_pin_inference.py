"""Tests for pin-time run ULID inference in history API."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from qmatsuite.provenance.db import get_db_path

from ._analysis_pipeline_test_utils import setup_qe_bands_run


def test_pin_infers_exact_run_ulid_from_evidence_fingerprint(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    run_ulid = ctx["run_ulid"]
    step_ulid = ctx["step_ulid"]

    analysis_payload = svc.analysis.get_analysis(run_ulid=run_ulid, object_type="bands")
    result = svc.history.pin_analysis(
        run_ulid=None,
        step_ulid=step_ulid,
        analysis_kind="bands",
        json_payload=analysis_payload,
    )

    assert result["success"] is True
    assert result["run_ulid"] == run_ulid
    assert result["run_ulid_source"] == "exact"
    details = result["run_ulid_source_details"]
    assert details["strategy"] == "evidence_fingerprint"
    assert details["matched_run_ulid"] == run_ulid
    assert details["fingerprint_match_count"] >= 1


def test_pin_infers_latest_success_when_fingerprint_not_available(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    run_ulid = ctx["run_ulid"]
    step_ulid = ctx["step_ulid"]

    result = svc.history.pin_analysis(
        run_ulid=None,
        step_ulid=step_ulid,
        analysis_kind="bands",
        json_payload={"kind": "no_provenance_payload"},
    )

    assert result["success"] is True
    assert result["run_ulid"] == run_ulid
    assert result["run_ulid_source"] == "inferred"
    details = result["run_ulid_source_details"]
    assert details["strategy"] == "latest_success_fallback"
    assert details["matched_run_ulid"] == run_ulid


def test_pin_run_ulid_unknown_when_no_run_match_exists(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    run_ulid = ctx["run_ulid"]
    step_ulid = ctx["step_ulid"]
    project_root = ctx["project_root"]

    db_path = get_db_path(project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DELETE FROM analysis_snapshots WHERE run_ulid = ?", (run_ulid,))
        conn.execute("DELETE FROM run_steps WHERE run_ulid = ?", (run_ulid,))
        conn.execute("DELETE FROM runs WHERE run_ulid = ?", (run_ulid,))
        conn.commit()
    finally:
        conn.close()

    result = svc.history.pin_analysis(
        run_ulid=None,
        step_ulid=step_ulid,
        analysis_kind="bands",
        json_payload={"kind": "no_provenance_payload"},
    )

    assert result["success"] is True
    assert result["run_ulid"] is None
    assert result["run_ulid_source"] == "unknown"
    details = result["run_ulid_source_details"]
    assert details["strategy"] == "unknown"
