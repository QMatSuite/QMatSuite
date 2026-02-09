"""VASP bands end-to-end analysis pipeline tests (SQLite + CAS + API surfaces)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from quantumvitas.provenance.db import get_db_path

from ._analysis_pipeline_test_utils import setup_vasp_bands_run


def test_vasp_bands_pipeline_eager_write_and_replay(tmp_path: Path) -> None:
    ctx = setup_vasp_bands_run(tmp_path)
    project_root = ctx["project_root"]
    svc = ctx["service"]
    run_ulid = ctx["run_ulid"]

    db_path = get_db_path(project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        snapshot_row = conn.execute(
            """
            SELECT canonical_sha, object_type, step_ulids, gen_steps
            FROM analysis_snapshots
            WHERE run_ulid = ? AND object_type = ?
            """,
            (run_ulid, "bands"),
        ).fetchone()
    finally:
        conn.close()

    assert snapshot_row is not None
    canonical_sha = str(snapshot_row[0])
    assert len(canonical_sha) == 64
    assert snapshot_row[1] == "bands"
    assert "bandspw" in str(snapshot_row[3])

    cas_blob = project_root / ".provenance" / ".cas" / "analysis" / f"{canonical_sha}.json.gz"
    assert cas_blob.exists()

    analysis = svc.analysis.get_analysis(run_ulid=run_ulid, object_type="bands")
    assert analysis["run_ulid"] == run_ulid
    assert analysis["object_type"] == "bands"
    assert analysis["canonical_sha"] == canonical_sha

    bundle = analysis["bundle"]
    assert bundle["bundle_kind"] == "canonical"
    assert bundle["object_type"] == "bands"
    assert len(bundle["series"]) == 16
    assert len(bundle["arrays"]["k_distances"]) == 200
    assert len(bundle["arrays"]["eigenvalues"]) == 200
    assert [marker["label"] for marker in bundle["render_meta"]["markers"]] == [
        "G",
        "X",
        "W",
        "K",
        "G",
        "L",
    ]

    snapshot = svc.analysis.get_analysis_snapshot(run_ulid=run_ulid, object_type="bands")
    assert snapshot["run_ulid"] == run_ulid
    assert snapshot["object_type"] == "bands"
    assert snapshot["canonical_sha"] == canonical_sha
