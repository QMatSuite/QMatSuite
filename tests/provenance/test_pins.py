"""Tests for provenance pin metadata behavior."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from quantumvitas.provenance import (
    PinError,
    open_provenance_db,
    pin_analysis_to_history,
)
from quantumvitas.provenance.cas import CAS


def _seed_run_step(project_root: Path, run_ulid: str, step_ulid: str) -> None:
    """Insert a minimal run + step row pair required by can_pin_to_run()."""
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    conn = open_provenance_db(project_root)
    try:
        conn.execute(
            """
            INSERT INTO runs (run_ulid, calc_ulid, started_at, status, engine)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_ulid, "01JCALCSEED", now, "success", "qe"),
        )
        conn.execute(
            """
            INSERT INTO run_steps (run_ulid, step_ulid, step_index, status)
            VALUES (?, ?, ?, ?)
            """,
            (run_ulid, step_ulid, 0, "success"),
        )
        conn.commit()
    finally:
        conn.close()


def test_pin_analysis_stores_run_ulid_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin metadata and operation payload include run_ulid_source."""
    run_ulid = "01JPINRUN000000000000000001"
    step_ulid = "01JPINSTEP00000000000000001"
    _seed_run_step(tmp_path, run_ulid, step_ulid)

    stored_json_payloads: list[dict] = []
    original_store_json = CAS.store_json

    def _spy_store_json(self: CAS, payload: dict, tier: int) -> str:
        stored_json_payloads.append(payload)
        return original_store_json(self, payload, tier)

    monkeypatch.setattr(CAS, "store_json", _spy_store_json)

    result = pin_analysis_to_history(
        project_root=tmp_path,
        run_ulid=run_ulid,
        step_ulid=step_ulid,
        analysis_kind="bands",
        json_payload={"hello": "world"},
        run_ulid_source="inferred",
    )

    assert result.success is True
    assert result.run_ulid_source == "inferred"
    assert result.to_dict()["run_ulid_source"] == "inferred"
    assert any(
        payload.get("run_ulid_source") == "inferred"
        and payload.get("pin_ulid")
        for payload in stored_json_payloads
    )


def test_pin_analysis_rejects_invalid_run_ulid_source(tmp_path: Path) -> None:
    """Invalid run_ulid_source values fail validation."""
    run_ulid = "01JPINRUN000000000000000002"
    step_ulid = "01JPINSTEP00000000000000002"
    _seed_run_step(tmp_path, run_ulid, step_ulid)

    with pytest.raises(PinError, match="Invalid run_ulid_source"):
        pin_analysis_to_history(
            project_root=tmp_path,
            run_ulid=run_ulid,
            step_ulid=step_ulid,
            analysis_kind="dos",
            json_payload={"ok": True},
            run_ulid_source="bad",  # type: ignore[arg-type]
        )
