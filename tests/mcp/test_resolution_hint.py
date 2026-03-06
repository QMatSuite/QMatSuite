"""Success-hint tests — verify run_calculation always nudges recording
on success, with hard tone after failure recovery and soft tone otherwise.

Uses real QE execution via qe_project_with_si fixture.

Failure mechanism: ecutwfc=-1.0 causes QE to crash immediately
(negative cutoff energy).  This failure happens during QE execution
so the runner records it in provenance, unlike pseudo-resolution
failures which happen before the runner starts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.api import QMSService


GOOD_PSEUDO = "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
HARD_MARKER = "recovered from a failed run"
SOFT_MARKER = "Run succeeded"


def _create_si_scf(project_root: Path, ecutwfc: float = 20.0) -> str:
    """Create a QE SCF calc with real pseudo and given ecutwfc. Returns calc_ulid."""
    from qmatsuite.mcp.tools.create_calculation import create_calculation
    from qmatsuite.mcp.tools.set_parameters import set_parameters

    svc = QMSService(project_root)

    result = create_calculation.fn(
        engine="qe", workflow="scf", structure_selector="si",
    )
    assert result["status"] == "success", f"create_calculation failed: {result}"
    calc_ulid = result["data"]["calc_ulid"]

    svc.calculation.update_species_map(
        calc_ulid,
        {"Si": {"pseudopot": GOOD_PSEUDO}},
    )

    set_result = set_parameters.fn(
        calc_ulid=calc_ulid,
        params={"SYSTEM": {"ecutwfc": ecutwfc}},
        step=0,
    )
    assert set_result["status"] == "success", f"set_parameters failed: {set_result}"

    return calc_ulid


def _fix_ecutwfc(project_root: Path, calc_ulid: str) -> None:
    """Set ecutwfc to a valid value for Si SCF."""
    from qmatsuite.mcp.tools.set_parameters import set_parameters

    set_result = set_parameters.fn(
        calc_ulid=calc_ulid,
        params={"SYSTEM": {"ecutwfc": 20.0}},
        step=0,
    )
    assert set_result["status"] == "success"


class TestSuccessHint:
    """Verify run_calculation always nudges on success:
    hard tone after failure recovery, soft tone otherwise."""

    def test_first_success_has_soft_hint(self, qe_project_with_si):
        """First successful run gets soft recording nudge."""
        from qmatsuite.mcp.tools.run_calculation import run_calculation

        calc_ulid = _create_si_scf(qe_project_with_si, ecutwfc=20.0)
        result = run_calculation.fn(calc_ulid=calc_ulid)

        assert result["status"] == "success", f"run failed: {result}"
        assert result["data"]["status"] == "completed"
        hint = result.get("context_hint", "")
        assert SOFT_MARKER in hint
        assert HARD_MARKER not in hint

    def test_success_after_failure_has_hard_hint(self, qe_project_with_si):
        """Run with bad ecutwfc -> QE crash -> fix -> re-run -> hard hint fires."""
        from qmatsuite.mcp.tools.run_calculation import run_calculation

        calc_ulid = _create_si_scf(qe_project_with_si, ecutwfc=-1.0)

        # First run: should fail (QE crash on negative ecutwfc)
        r1 = run_calculation.fn(calc_ulid=calc_ulid)
        r1_status = r1.get("data", {}).get("status", r1.get("status"))
        assert r1_status in ("failed", "error"), f"Expected failure, got: {r1}"

        # Fix ecutwfc
        _fix_ecutwfc(qe_project_with_si, calc_ulid)

        # Second run: should succeed with hard hint
        r2 = run_calculation.fn(calc_ulid=calc_ulid, run_mode="full")
        assert r2["status"] == "success", f"re-run failed: {r2}"
        assert r2["data"]["status"] == "completed"
        hint = r2.get("context_hint", "")
        assert HARD_MARKER in hint, f"Expected hard hint but got: {hint!r}"
        assert "MUST record" in hint

    def test_soft_hint_when_previous_success(self, qe_project_with_si):
        """Fail -> fix -> succeed (hard) -> succeed again (soft, not hard)."""
        from qmatsuite.mcp.tools.run_calculation import run_calculation

        calc_ulid = _create_si_scf(qe_project_with_si, ecutwfc=-1.0)

        # Run 1: fail
        run_calculation.fn(calc_ulid=calc_ulid)

        # Fix
        _fix_ecutwfc(qe_project_with_si, calc_ulid)

        # Run 2: succeed (hard hint)
        r2 = run_calculation.fn(calc_ulid=calc_ulid, run_mode="full")
        assert r2["data"]["status"] == "completed"
        assert HARD_MARKER in r2.get("context_hint", "")

        # Run 3: succeed again (soft hint, not hard)
        r3 = run_calculation.fn(calc_ulid=calc_ulid)
        assert r3["status"] == "success"
        assert r3["data"]["status"] == "completed"
        hint3 = r3.get("context_hint", "")
        assert SOFT_MARKER in hint3
        assert HARD_MARKER not in hint3

    def test_consecutive_successes_soft_hint(self, qe_project_with_si):
        """Two consecutive successful runs -> soft hint on second."""
        from qmatsuite.mcp.tools.run_calculation import run_calculation

        calc_ulid = _create_si_scf(qe_project_with_si, ecutwfc=20.0)

        r1 = run_calculation.fn(calc_ulid=calc_ulid)
        assert r1["data"]["status"] == "completed"

        r2 = run_calculation.fn(calc_ulid=calc_ulid)
        assert r2["status"] == "success"
        assert r2["data"]["status"] == "completed"
        hint = r2.get("context_hint", "")
        assert SOFT_MARKER in hint
        assert HARD_MARKER not in hint

    def test_no_provenance_no_crash(self, qe_project_with_si):
        """If .provenance/ is missing, run still succeeds without hint."""
        from qmatsuite.mcp.tools.run_calculation import run_calculation

        calc_ulid = _create_si_scf(qe_project_with_si, ecutwfc=20.0)

        # First run -- creates provenance DB
        r1 = run_calculation.fn(calc_ulid=calc_ulid)
        assert r1["data"]["status"] == "completed"

        # Remove provenance directory
        prov_dir = qe_project_with_si / ".provenance"
        backup = qe_project_with_si / ".provenance_backup"
        if prov_dir.exists():
            prov_dir.rename(backup)

        try:
            # Run again -- should succeed without crashing
            r2 = run_calculation.fn(calc_ulid=calc_ulid)
            assert r2["status"] == "success"
            assert r2["data"]["status"] == "completed"
            hint = r2.get("context_hint", "")
            # No provenance → query_runs returns [] → soft hint (no prior info)
            assert HARD_MARKER not in hint
        finally:
            # Restore provenance
            if backup.exists():
                if prov_dir.exists():
                    import shutil
                    shutil.rmtree(prov_dir)
                backup.rename(prov_dir)
