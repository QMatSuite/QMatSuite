"""Stage 6 MCP error recovery tests.

Tests the error enrichment layer and real QE failure + recovery scenarios.

- Unit tests: mock digest → enrichment classification (no QE needed)
- Integration tests: real QE failure with bad params → enriched error → fix → success

Shared fixtures (qms_project, qe_available, qe_project_with_si) are in conftest.py.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from qmatsuite.api import QMSService
from qmatsuite.mcp.error_enrichment import enrich_run_error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_result_dto(
    status: str = "failed",
    exit_code: int | None = 1,
    step_messages: list[str] | None = None,
) -> SimpleNamespace:
    """Build a minimal mock RunResultDTO for unit tests."""
    msgs = step_messages or ["JOB DONE not found in output [return code: 1]"]
    steps = [
        SimpleNamespace(
            step_ulid="STEP001",
            step_type_gen="scf",
            step_type_spec="qe_scf",
            status="failed",
            message=msg,
        )
        for msg in msgs
    ]
    return SimpleNamespace(
        run_ulid="RUN001",
        calc_ulid="CALC001",
        status=status,
        exit_code=exit_code,
        steps=steps,
        io_dir="/tmp/fake",
    )


def _setup_si_scf_calc(project_root: Path, **param_overrides) -> str:
    """Create a QE SCF calc with species_map and optional param overrides."""
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
        {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}},
    )

    # Default: low ecutwfc for fast execution
    params = {"SYSTEM": {"ecutwfc": 20.0}}
    params.update(param_overrides)

    set_result = set_parameters.fn(
        calc_ulid=calc_ulid, params=params, step=0,
    )
    assert set_result["status"] == "success", f"set_parameters failed: {set_result}"

    return calc_ulid


# ===========================================================================
# Unit tests: error enrichment classification (no QE needed)
# ===========================================================================


class TestEnrichmentClassification:
    """Mock-based tests for error pattern detection."""

    @pytest.fixture(autouse=True)
    def _patch_knowledge(self, tmp_path, monkeypatch):
        """Patch KnowledgeStore to use a temp DB."""
        from qmatsuite.mcp.knowledge.store import KnowledgeStore
        from qmatsuite.mcp.knowledge.build_builtin import build_builtin_db

        db_path = tmp_path / "knowledge" / "test.db"
        build_builtin_db(output_path=db_path)
        # Patch the default path so error_enrichment finds it
        monkeypatch.setattr(
            "qmatsuite.mcp.knowledge.store._default_db_path",
            lambda: db_path,
        )

    def test_scf_not_converged(self):
        """Digest with converged=False, n_iterations>0 → SCF_NOT_CONVERGED."""
        dto = _make_mock_result_dto()
        digest = {"converged": False, "n_iterations": 5, "total_energy_ry": -10.5}

        result = enrich_run_error("CALC001", dto, digest, "qe", "scf")

        assert result["status"] == "error"
        assert result["error_type"] == "SCF_NOT_CONVERGED"
        assert result["severity"] == "recoverable"
        assert result["diagnostics"] is not None
        assert result["diagnostics"][0]["converged"] is False
        assert result["diagnostics"][0]["n_iterations"] == 5

    def test_engine_crash(self):
        """No digest, non-zero exit code → ENGINE_CRASH."""
        dto = _make_mock_result_dto(exit_code=139)
        digest = None

        result = enrich_run_error("CALC001", dto, digest, "qe", "scf")

        assert result["status"] == "error"
        assert result["error_type"] == "ENGINE_CRASH"
        assert result["severity"] == "fatal"

    def test_unknown_failure(self):
        """No digest, exit_code=None → UNKNOWN_FAILURE."""
        dto = _make_mock_result_dto(exit_code=None, step_messages=["something went wrong"])

        result = enrich_run_error("CALC001", dto, None, "qe", "scf")

        assert result["status"] == "error"
        assert result["error_type"] == "UNKNOWN_FAILURE"

    def test_suggested_fixes_from_knowledge(self):
        """SCF_NOT_CONVERGED fixes include knowledge-backed reasoning."""
        dto = _make_mock_result_dto()
        digest = {"converged": False, "n_iterations": 5}

        result = enrich_run_error("CALC001", dto, digest, "qe", "scf")

        fixes = result.get("suggested_fixes", [])
        assert len(fixes) >= 1
        # At least one fix should have a non-empty reason from knowledge
        reasons = [f.get("reason", "") for f in fixes]
        assert any(len(r) > 10 for r in reasons), f"Expected knowledge reason, got: {reasons}"

    def test_suggested_fix_format(self):
        """Each suggested_fix has the required fields."""
        dto = _make_mock_result_dto()
        digest = {"converged": False, "n_iterations": 5}

        result = enrich_run_error("CALC001", dto, digest, "qe", "scf")

        fixes = result.get("suggested_fixes", [])
        assert len(fixes) >= 1
        for fix in fixes:
            assert "action" in fix
            assert "parameter" in fix
            assert "confidence" in fix
            assert "reason" in fix

    def test_context_hint_includes_calc_ulid(self):
        """The context_hint includes the calc_ulid for copy-paste."""
        dto = _make_mock_result_dto()
        digest = {"converged": False, "n_iterations": 5}

        result = enrich_run_error("MY_CALC_ULID", dto, digest, "qe", "scf")

        assert "MY_CALC_ULID" in result.get("context_hint", "")

    def test_error_severity_classification(self):
        """Recoverable errors get 'recoverable', crashes get 'fatal'."""
        # Recoverable: SCF not converged
        dto = _make_mock_result_dto()
        digest_scf = {"converged": False, "n_iterations": 5}
        result_scf = enrich_run_error("C1", dto, digest_scf, "qe", "scf")
        assert result_scf["severity"] == "recoverable"

        # Fatal: engine crash
        dto_crash = _make_mock_result_dto(exit_code=139)
        result_crash = enrich_run_error("C2", dto_crash, None, "qe", "scf")
        assert result_crash["severity"] == "fatal"


# ===========================================================================
# Real QE failure + recovery tests
# ===========================================================================


class TestRealQEFailureRecovery:
    """Real QE execution with bad params → enriched error → fix → success."""

    def test_scf_failure_and_recovery(self, qe_project_with_si):
        """Full cycle: bad params → failure with diagnostics → fix → success.

        Uses conv_thr=1e-30 (impossibly tight) + electron_maxstep=3 to
        guarantee SCF non-convergence.  QE exits normally ("JOB DONE")
        but with no converged energy — the enrichment layer detects this.
        """
        from qmatsuite.mcp.tools.run_calculation import run_calculation
        from qmatsuite.mcp.tools.set_parameters import set_parameters
        from qmatsuite.mcp.tools.get_results_summary import get_results_summary

        # 1. Create with bad params: impossibly tight threshold + low iterations
        calc_ulid = _setup_si_scf_calc(
            qe_project_with_si,
            ELECTRONS={"electron_maxstep": 3, "conv_thr": 1.0e-30},
        )

        # 2. Run → should detect non-convergence via digest analysis
        result = run_calculation.fn(calc_ulid=calc_ulid)
        assert result["status"] == "error", f"Expected failure but got: {result['status']}"
        assert result["error_type"] == "SCF_NOT_CONVERGED"
        assert result["severity"] == "recoverable"

        # 3. Apply fix: relax conv_thr to a reasonable value
        fix_result = set_parameters.fn(
            calc_ulid=calc_ulid, step=0,
            params={"ELECTRONS": {"electron_maxstep": 100, "conv_thr": 1.0e-6}},
        )
        assert fix_result["status"] == "success"

        # 4. Retry → should succeed
        retry = run_calculation.fn(calc_ulid=calc_ulid)
        assert retry["status"] == "success", f"Retry failed: {retry}"
        assert retry["data"]["status"] == "completed"

        # 5. Verify results
        summary = get_results_summary.fn(calc_ulid=calc_ulid)
        assert summary["status"] == "success"
        assert summary["data"]["converged"] is True
        assert summary["data"]["total_energy_eV"] < 0

    def test_error_return_has_diagnostics(self, qe_project_with_si):
        """Verify the error return structure is complete on failure."""
        from qmatsuite.mcp.tools.run_calculation import run_calculation

        calc_ulid = _setup_si_scf_calc(
            qe_project_with_si,
            ELECTRONS={"electron_maxstep": 3, "conv_thr": 1.0e-30},
        )

        result = run_calculation.fn(calc_ulid=calc_ulid)
        assert result["status"] == "error"

        # Core error fields
        assert "error_type" in result
        assert "message" in result
        assert "severity" in result
        assert "context_hint" in result

        # calc_ulid in context hint for copy-paste
        assert calc_ulid in result.get("context_hint", "")

        # Diagnostics and suggested_fixes both present
        assert result.get("diagnostics") is not None
        assert result.get("suggested_fixes") is not None
        assert len(result["suggested_fixes"]) >= 1

        # Run payload is embedded in data
        assert "data" in result
        assert result["data"]["calc_ulid"] == calc_ulid
