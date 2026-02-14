"""Integration tests for orchestrator using real driver registration chains."""

from __future__ import annotations

from pathlib import Path

from quantumvitas.core.analysis.bundles import CanonicalPrimitiveBundle
from quantumvitas.core.analysis.orchestrator import run_post_run_analysis
from quantumvitas.drivers.qe.driver import QEDriver


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_orchestrator_real_qe_driver_registration_chain() -> None:
    raw_dir = REPO_ROOT / "tests" / "data" / "analysis_bands"
    ordered_gen_steps = [("01ULID1", "bandspw", raw_dir)]

    results = run_post_run_analysis(
        engine="qe",
        driver=QEDriver(),
        ordered_gen_steps=ordered_gen_steps,
        run_ulid="01RUN",
        calc_ulid="01CALC",
        calc_dir=raw_dir.parent,
    )

    from quantumvitas.core.analysis.capability import ResultState

    ok_results = [r for r in results if r.state == ResultState.OK]
    assert len(ok_results) >= 1
    entry = ok_results[0]
    assert entry.object_type == "bands"
    assert isinstance(entry.canonical, CanonicalPrimitiveBundle)
    assert entry.canonical.bundle_kind == "canonical"
