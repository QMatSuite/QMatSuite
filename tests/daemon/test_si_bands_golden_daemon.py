"""Golden daemon E2E for QE bands using the new analysis pipeline surfaces."""

from __future__ import annotations

import gzip
import json
import sqlite3
import time
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from quantumvitas.daemon.server import QVDaemon, RPCRequest
from quantumvitas.provenance.db import get_db_path


pytestmark = pytest.mark.qe_core


def _send_request(daemon: QVDaemon, request_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = daemon.handle_request(
        RPCRequest(
            id="test",
            type=request_type,
            payload=payload,
        )
    )
    if not response.ok:
        raise RuntimeError(f"Daemon request failed for {request_type}: {response.error}")
    return response.data


def _wait_for_job(daemon: QVDaemon, job_id: str, timeout: float = 600.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _send_request(daemon, "get_job_status", {"job_id": job_id})
        if status["status"] in {"completed", "failed", "cancelled"}:
            return status
        time.sleep(1.0)
    raise TimeoutError(f"Job {job_id} did not complete in {timeout}s")


@pytest.fixture()
def daemon() -> QVDaemon:
    d = QVDaemon(stdin=StringIO(), stdout=StringIO(), stderr=StringIO())
    try:
        yield d
    finally:
        d.job_manager.shutdown(wait=True)


def test_qe_bands_demo_runs_new_analysis_pipeline_end_to_end(
    daemon: QVDaemon,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "demo_workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    created = _send_request(
        daemon,
        "create_demo_project",
        {
            "target_dir": str(workspace),
            "name": "qe-bands-golden",
            "demo_id": "si_bands_demo",
        },
    )
    project_root = Path(created["project_root"])
    assert (project_root / "project.qv.yml").exists()

    calc_listing = _send_request(daemon, "list_calculations", {"project_root": str(project_root)})
    calculations = calc_listing.get("calculations", [])
    target_calc = next((row for row in calculations if row.get("slug") == "si-bands"), None)
    assert target_calc is not None, calculations
    calc_selector = str(target_calc.get("slug") or target_calc.get("ulid") or target_calc.get("name"))
    assert calc_selector

    submission = _send_request(
        daemon,
        "run_calculation",
        {
            "project_root": str(project_root),
            "calculation": calc_selector,
            "run_mode": "full",
        },
    )
    job_id = submission["job_id"]
    assert submission["status"] == "pending"
    assert job_id

    final_status = _wait_for_job(daemon, job_id)
    assert final_status["status"] == "completed", final_status

    run_result = final_status.get("result") or {}
    run_ulid = str(run_result.get("run_ulid") or "")
    assert run_ulid
    steps = run_result.get("steps") or []
    assert len(steps) == 4

    step_ulids = [str(row["step_ulid"]) for row in steps if row.get("step_ulid")]
    assert len(step_ulids) == 4

    for step_ulid in step_ulids:
        digest = _send_request(
            daemon,
            "get_step_digest",
            {
                "project_root": str(project_root),
                "run_ulid": run_ulid,
                "step_ulid": step_ulid,
            },
        )
        assert digest["available"] is True
        assert isinstance(digest.get("digest"), dict)
        digest_sha = str(digest.get("digest_sha") or "")
        assert len(digest_sha) == 64

    bandspw_step = next((row for row in steps if row.get("step_type_spec") == "qe_bandspw"), None)
    assert bandspw_step is not None, steps

    raw_listing = _send_request(
        daemon,
        "list_raw_files",
        {
            "project_root": str(project_root),
            "calculation": calc_selector,
            "step": str(bandspw_step["step_ulid"]),
        },
    )
    files = raw_listing.get("files", [])
    assert any(str(path).endswith(".bands.dat.gnu") for path in files), files

    analysis = _send_request(
        daemon,
        "get_analysis",
        {
            "project_root": str(project_root),
            "run_ulid": run_ulid,
            "object_type": "bands",
        },
    )
    assert analysis["run_ulid"] == run_ulid
    assert analysis["object_type"] == "bands"
    canonical_sha = str(analysis["canonical_sha"])
    assert len(canonical_sha) == 64

    bundle = analysis["bundle"]
    assert bundle["bundle_kind"] == "canonical"
    assert bundle["object_type"] == "bands"
    assert isinstance(bundle.get("series"), list) and bundle["series"]

    provenance_meta = bundle["provenance_meta"]
    assert provenance_meta["run_ulid"] == run_ulid
    assert "step_ulids" in provenance_meta and provenance_meta["step_ulids"]

    snapshot = _send_request(
        daemon,
        "get_analysis_snapshot",
        {
            "project_root": str(project_root),
            "run_ulid": run_ulid,
            "object_type": "bands",
        },
    )
    assert snapshot["canonical_sha"] == canonical_sha

    db_path = get_db_path(project_root)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            """
            SELECT canonical_sha, object_type
            FROM analysis_snapshots
            WHERE run_ulid = ?
            """,
            (run_ulid,),
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) >= 1
    bands_rows = [r for r in rows if r[1] == "bands"]
    assert len(bands_rows) == 1
    assert bands_rows[0][0] == canonical_sha

    cas_blob = project_root / ".provenance" / ".cas" / "analysis" / f"{canonical_sha}.json.gz"
    assert cas_blob.exists()
    with gzip.open(cas_blob, "rb") as handle:
        cas_payload = json.loads(handle.read().decode("utf-8"))
    assert cas_payload["object_type"] == "bands"
