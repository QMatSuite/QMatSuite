"""Tests for operational analysis derivation endpoint."""

from __future__ import annotations

from pathlib import Path

from ._analysis_pipeline_test_utils import setup_qe_bands_run


def test_get_analysis_returns_primitive_bundle_json(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    run_ulid = ctx["run_ulid"]

    response = svc.analysis.get_analysis(run_ulid=run_ulid, object_type="bands")
    assert response["run_ulid"] == run_ulid
    assert response["object_type"] == "bands"
    assert len(response["canonical_sha"]) == 64
    bundle = response["bundle"]
    assert bundle["bundle_kind"] == "canonical"
    assert bundle["object_type"] == "bands"
    assert "series" in bundle


def test_get_analysis_applies_transforms_on_the_fly(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    run_ulid = ctx["run_ulid"]

    transformed = svc.analysis.get_analysis(
        run_ulid=run_ulid,
        object_type="bands",
        transforms=["FermiShift"],
    )
    bundle = transformed["bundle"]
    assert bundle["bundle_kind"] == "derived"
    assert len(bundle["transform_chain"]) == 1
    assert bundle["transform_chain"][0]["transform_name"] == "fermi_shift"
