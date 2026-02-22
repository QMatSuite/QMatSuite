"""Integration tests for end-of-run eager analysis persistence."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from qmatsuite.provenance.db import get_db_path

from ._analysis_pipeline_test_utils import setup_qe_bands_run


def test_eager_pipeline_writes_analysis_snapshot_row(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    project_root = ctx["project_root"]
    run_ulid = ctx["run_ulid"]
    step_ulid = ctx["step_ulid"]

    db_path = get_db_path(project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        run_step_row = conn.execute(
            """
            SELECT status, digest_sha
            FROM run_steps
            WHERE run_ulid = ? AND step_ulid = ?
            """,
            (run_ulid, step_ulid),
        ).fetchone()
        assert run_step_row is not None
        assert run_step_row[0] == "success"

        snapshot_row = conn.execute(
            """
            SELECT canonical_sha, step_ulids, gen_steps, match_key, evidence_fingerprint
            FROM analysis_snapshots
            WHERE run_ulid = ? AND object_type = ?
            """,
            (run_ulid, "bands"),
        ).fetchone()
        assert snapshot_row is not None
        canonical_sha = snapshot_row[0]
        assert isinstance(canonical_sha, str) and len(canonical_sha) == 64
        assert "bandspw" in snapshot_row[2]
        assert snapshot_row[3] is not None
        assert snapshot_row[4] is not None
    finally:
        conn.close()

    cas_blob = project_root / ".provenance" / ".cas" / "analysis" / f"{canonical_sha}.json.gz"
    assert cas_blob.exists()
