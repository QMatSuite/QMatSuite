"""Tests for Surface B step digest endpoint."""

from __future__ import annotations

from pathlib import Path

from ._analysis_pipeline_test_utils import setup_qe_bands_run


def test_get_step_digest_returns_persisted_digest_payload(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    run_ulid = ctx["run_ulid"]
    step_ulid = ctx["step_ulid"]

    payload = svc.analysis.get_step_digest(run_ulid=run_ulid, step_ulid=step_ulid)

    assert payload["available"] is True
    assert isinstance(payload["digest_sha"], str) and len(payload["digest_sha"]) == 64
    assert payload["engine"] == "qe"
    digest = payload["digest"]
    assert isinstance(digest, dict)
    assert "converged" in digest
    assert "n_iterations" in digest
