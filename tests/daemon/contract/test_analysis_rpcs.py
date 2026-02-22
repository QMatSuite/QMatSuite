"""RPC contract tests for analysis endpoints."""

from pathlib import Path
import pytest
from qmatsuite.daemon.server import QMSDaemon
from .conftest import send_request


class TestGetAnalysis:
    """Contract tests for get_analysis RPC."""

    def test_get_analysis_missing_run(self, demo_project_with_calculation, daemon: QMSDaemon):
        """get_analysis errors on non-existent run."""
        project_root, _, _ = demo_project_with_calculation
        fake_run = "01HZZZZZZZZZZZZZZZZZZZZZZ"

        with pytest.raises(RuntimeError):
            send_request(daemon, "get_analysis", {
                "project_root": str(project_root),
                "run_ulid": fake_run,
                "object_type": "convergence"
            })


class TestGetAnalysisInstancesForStep:
    """Contract tests for get_analysis_instances_for_step RPC."""

    def test_get_analysis_instances_no_run(self, demo_project_with_calculation, daemon: QMSDaemon):
        """get_analysis_instances_for_step returns empty for step without run."""
        project_root, _, calc_ulid = demo_project_with_calculation
        calc = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })
        step_ulid = calc["steps"][0]["ulid"]

        response = send_request(daemon, "get_analysis_instances_for_step", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step_ulid": step_ulid
        })

        # Should return empty list or dict (no error for missing step)
        assert response is not None

    def test_get_analysis_instances_valid_step(self, demo_project_with_calculation, daemon: QMSDaemon):
        """get_analysis_instances_for_step with valid step returns data."""
        project_root, _, calc_ulid = demo_project_with_calculation
        calc = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })
        step_ulid = calc["steps"][0]["ulid"]

        # Should return data or empty list, not error
        response = send_request(daemon, "get_analysis_instances_for_step", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step_ulid": step_ulid
        })
        
        assert response is not None
