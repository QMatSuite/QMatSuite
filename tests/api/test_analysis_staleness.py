"""API-level staleness invalidation tests for analysis memoization."""

from __future__ import annotations

from pathlib import Path

from ._analysis_pipeline_test_utils import setup_qe_bands_run


def test_get_analysis_rederives_when_source_files_change(tmp_path: Path) -> None:
    ctx = setup_qe_bands_run(tmp_path)
    svc = ctx["service"]
    run_ulid = ctx["run_ulid"]
    calc_dir = Path(ctx["calc_dir"])

    first = svc.analysis.get_analysis(run_ulid=run_ulid, object_type="bands")
    first_entry = dict(svc._analysis_index[(run_ulid, "bands")])
    assert first["bundle"]["bundle_kind"] == "canonical"

    bands_file = calc_dir / "raw" / "si.bands.dat.gnu"
    bands_file.write_text(
        bands_file.read_text(encoding="utf-8") + "\n# staleness-mutation\n",
        encoding="utf-8",
    )

    second = svc.analysis.get_analysis(run_ulid=run_ulid, object_type="bands")
    second_entry = dict(svc._analysis_index[(run_ulid, "bands")])

    assert second["bundle"]["bundle_kind"] == "canonical"
    assert second["object_type"] == "bands"
    assert second_entry["evidence_fingerprint"] != first_entry["evidence_fingerprint"]
