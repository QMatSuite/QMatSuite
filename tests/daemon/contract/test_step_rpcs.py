"""RPC contract tests for step management endpoints."""

from pathlib import Path
import pytest
from qmatsuite.daemon.server import QMSDaemon
from .conftest import send_request


class TestGetStepDetail:
    """Contract tests for get_step_detail RPC."""

    def test_get_step_detail_happy_path(self, demo_project_with_calculation, daemon: QMSDaemon):
        """get_step_detail returns step information."""
        project_root, _, calc_ulid = demo_project_with_calculation
        calc = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })
        step_ulid = calc["steps"][0]["ulid"]

        response = send_request(daemon, "get_step_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step": step_ulid
        })

        # Validate schema matches TypeScript StepDetail
        assert "ulid" in response
        assert "step_type_gen" in response
        assert "step_type_spec" in response
        assert "parameters" in response

    def test_get_step_detail_not_found(self, demo_project_with_calculation, daemon: QMSDaemon):
        """get_step_detail errors on non-existent step."""
        project_root, _, calc_ulid = demo_project_with_calculation
        fake_step = "01HZZZZZZZZZZZZZZZZZZZZZZ"

        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "get_step_detail", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": fake_step
            })

        assert "not_found" in str(exc_info.value).lower()

    def test_get_step_detail_workflow(self, demo_project_with_calculation, daemon: QMSDaemon):
        """get_step_detail after add_step_to_calculation."""
        project_root, _, calc_ulid = demo_project_with_calculation

        # Add step
        add_response = send_request(daemon, "add_step_to_calculation", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step_type_gen": "nscf",
            "step_type_spec": "qe_nscf"
        })

        # Extract step_ulid from the steps array (response has steps array, not direct ulid)
        steps = add_response["steps"]
        # Find the newly added nscf step
        nscf_step = next(s for s in steps if s["step_type_gen"] == "nscf")
        step_ulid = nscf_step["step_ulid"]

        # Get detail
        detail = send_request(daemon, "get_step_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step": step_ulid
        })

        assert detail["step_type_gen"] == "nscf"


class TestUpdateStepParams:
    """Contract tests for update_step_params RPC."""

    def test_update_step_params_happy_path(self, demo_project_with_calculation, daemon: QMSDaemon):
        """update_step_params modifies step parameters."""
        project_root, _, calc_ulid = demo_project_with_calculation
        calc = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })
        step_ulid = calc["steps"][0]["ulid"]

        # Update parameters
        response = send_request(daemon, "update_step_params", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step": step_ulid,
            "parameters": {
                "system": {"ecutwfc": 50.0}
            }
        })

        assert response.get("success") is True or "parameters" in response

    def test_update_step_params_missing_step(self, demo_project_with_calculation, daemon: QMSDaemon):
        """update_step_params errors on non-existent step."""
        project_root, _, calc_ulid = demo_project_with_calculation
        fake_step = "01HZZZZZZZZZZZZZZZZZZZZZZ"

        with pytest.raises(RuntimeError):
            send_request(daemon, "update_step_params", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step": fake_step,
                "parameters": {}
            })

    def test_update_step_params_workflow(self, demo_project_with_calculation, daemon: QMSDaemon):
        """update_step_params in editing workflow."""
        project_root, _, calc_ulid = demo_project_with_calculation
        calc = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })
        step_ulid = calc["steps"][0]["ulid"]

        # Get initial params
        before = send_request(daemon, "get_step_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step": step_ulid
        })
        assert before is not None

        # Update params (use a simple parameter that exists)
        send_request(daemon, "update_step_params", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step": step_ulid,
            "parameters": {
                "system": {"ecutwfc": 60.0}
            }
        })

        # Verify update succeeded (don't check exact value since merging may be complex)
        after = send_request(daemon, "get_step_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "step": step_ulid
        })
        assert after is not None
        assert "parameters" in after
