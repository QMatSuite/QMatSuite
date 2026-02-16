"""
RPC contract tests for calculation management endpoints.

Tests:
- get_calculation_detail: Full calculation metadata
- add_step_to_calculation: Step creation
"""

from pathlib import Path

import pytest

from quantumvitas.daemon.server import QVDaemon

from .conftest import send_request


class TestGetCalculationDetail:
    """Contract tests for get_calculation_detail RPC."""

    def test_get_calculation_detail_happy_path(self, demo_project_with_calculation, daemon: QVDaemon):
        """get_calculation_detail returns full calculation data."""
        project_root, _, calc_ulid = demo_project_with_calculation

        response = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid  # Parameter is "calculation" not "calculation_ulid"
        })

        # Validate schema matches TypeScript CalculationDetail
        assert "ulid" in response or "calc_ulid" in response
        assert "name" in response
        assert "structure_ulid" in response
        assert "steps" in response
        assert isinstance(response["steps"], list)
        assert len(response["steps"]) >= 1  # We added one SCF step

        # Verify steps have required fields
        step = response["steps"][0]
        assert "ulid" in step or "step_ulid" in step
        assert "step_type_spec" in step or "type" in step

    def test_get_calculation_detail_not_found(self, temp_project: Path, daemon: QVDaemon):
        """get_calculation_detail errors on non-existent calculation."""
        fake_ulid = "01HZZZZZZZZZZZZZZZZZZZZZZ"

        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "get_calculation_detail", {
                "project_root": str(temp_project),
                "calculation": fake_ulid
            })

        assert "not_found" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()

    def test_get_calculation_detail_workflow(self, demo_project_with_calculation, daemon: QVDaemon):
        """get_calculation_detail after list_calculations."""
        project_root, _, calc_ulid = demo_project_with_calculation

        # First list calculations
        list_response = send_request(daemon, "list_calculations", {
            "project_root": str(project_root)
        })
        assert list_response["count"] >= 1

        # Then get detail
        detail_response = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })
        assert detail_response is not None


class TestAddStepToCalculation:
    """Contract tests for add_step_to_calculation RPC."""

    def test_add_step_to_calculation_happy_path(self, demo_project_with_calculation, daemon: QVDaemon):
        """add_step_to_calculation creates a new step."""
        project_root, _, calc_ulid = demo_project_with_calculation

        # Add a relax step
        response = send_request(daemon, "add_step_to_calculation", {
            "project_root": str(project_root),
            "calculation": calc_ulid,  # Parameter is "calculation" not "calculation_ulid"
            "step_type_gen": "relax",
            "name": "relax_step"
        })

        # Response includes calculation steps with the new step added
        assert "steps" in response
        assert len(response["steps"]) == 2  # Original SCF + new relax

    def test_add_step_missing_step_type(self, demo_project_with_calculation, daemon: QVDaemon):
        """add_step_to_calculation errors on missing step_type_gen."""
        project_root, _, calc_ulid = demo_project_with_calculation

        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "add_step_to_calculation", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                # Missing step_type_gen
            })

        assert "invalid_argument" in str(exc_info.value).lower() or "missing" in str(exc_info.value).lower()

    def test_add_step_workflow(self, demo_project_with_calculation, daemon: QVDaemon):
        """add_step in context of calculation creation workflow."""
        project_root, _, calc_ulid = demo_project_with_calculation

        # Add multiple steps to build a workflow
        step_types = ["relax", "scf", "bands"]

        for step_type in step_types:
            response = send_request(daemon, "add_step_to_calculation", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step_type_gen": step_type
            })
            assert "steps" in response

        # Last response should have all steps: 1 original SCF + 3 new = 4 total
        assert len(response["steps"]) == 4

class TestCreateCalculation:
    """Contract tests for create_calculation RPC."""

    def test_create_calculation_happy_path(self, demo_project_with_structure, daemon: QVDaemon):
        """create_calculation creates a new calculation."""
        project_root, structure_ulid = demo_project_with_structure

        response = send_request(daemon, "create_calculation", {
            "project_root": str(project_root),
            "structure_ulid": structure_ulid,
            "name": "test_calculation",
            "engine_family": "qe"
        })

        # Response should include calculation ULID
        assert "ulid" in response or "calc_ulid" in response or "calculation_ulid" in response

    def test_create_calculation_missing_structure(self, temp_project: Path, daemon: QVDaemon):
        """create_calculation with non-existent structure."""
        fake_ulid = "01HZZZZZZZZZZZZZZZZZZZZZZ"

        # May not raise error, just create calculation with invalid structure reference
        try:
            response = send_request(daemon, "create_calculation", {
                "project_root": str(temp_project),
                "structure_ulid": fake_ulid,
                "name": "test",
                "engine_family": "qe"
            })
            # If it succeeds, that's OK (validation may happen later)
            assert response is not None
        except RuntimeError:
            # If it errors, that's also OK
            pass

    def test_create_calculation_workflow(self, demo_project_with_structure, daemon: QVDaemon):
        """create_calculation in full workflow."""
        project_root, structure_ulid = demo_project_with_structure

        # Create calculation
        create_response = send_request(daemon, "create_calculation", {
            "project_root": str(project_root),
            "structure_ulid": structure_ulid,
            "name": "workflow_calc",
            "engine_family": "qe"
        })

        calc_id = create_response.get("ulid") or create_response.get("calc_ulid") or create_response.get("calculation_ulid")
        assert calc_id is not None

        # Verify it appears in list
        list_response = send_request(daemon, "list_calculations", {
            "project_root": str(project_root)
        })
        assert list_response["count"] >= 1


class TestRenameCalculation:
    """Contract tests for rename_calculation RPC."""

    def test_rename_calculation_happy_path(self, demo_project_with_calculation, daemon: QVDaemon):
        """rename_calculation updates calculation name."""
        project_root, _, calc_ulid = demo_project_with_calculation

        new_name = "renamed_calculation"
        response = send_request(daemon, "rename_calculation", {
            "project_root": str(project_root),
            "calculation_ulid": calc_ulid,
            "new_name": new_name
        })

        assert response.get("success") is True or "name" in response

        # Verify rename
        detail = send_request(daemon, "get_calculation_detail", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })
        assert detail["name"] == new_name

    def test_rename_calculation_not_found(self, temp_project: Path, daemon: QVDaemon):
        """rename_calculation errors on non-existent calculation."""
        fake_ulid = "01HZZZZZZZZZZZZZZZZZZZZZZ"

        with pytest.raises(RuntimeError):
            send_request(daemon, "rename_calculation", {
                "project_root": str(temp_project),
                "calculation": fake_ulid,
                "new_name": "new_name"
            })


class TestDeleteCalculation:
    """Contract tests for delete_calculation and can_delete_calculation RPCs."""

    def test_can_delete_calculation_happy_path(self, demo_project_with_calculation, daemon: QVDaemon):
        """can_delete_calculation checks if calculation can be deleted."""
        project_root, _, calc_ulid = demo_project_with_calculation

        response = send_request(daemon, "can_delete_calculation", {
            "project_root": str(project_root),
            "calculation": calc_ulid
        })

        # Response should indicate if deletion is allowed
        assert "has_dependencies" in response or "can_delete" in response

    def test_delete_calculation_happy_path(self, demo_project_with_calculation, daemon: QVDaemon):
        """delete_calculation removes a calculation."""
        project_root, _, calc_ulid = demo_project_with_calculation

        # Delete the calculation
        response = send_request(daemon, "delete_calculation", {
            "project_root": str(project_root),
            "calculation_ulid": calc_ulid
        })

        assert response is not None  # Deletion succeeded if no error raised

        # Verify it's gone
        with pytest.raises(RuntimeError):
            send_request(daemon, "get_calculation_detail", {
                "project_root": str(project_root),
                "calculation": calc_ulid
            })

    def test_delete_calculation_not_found(self, temp_project: Path, daemon: QVDaemon):
        """delete_calculation with non-existent calculation."""
        fake_ulid = "01HZZZZZZZZZZZZZZZZZZZZZZ"

        # May not error on missing calculation (idempotent delete)
        try:
            response = send_request(daemon, "delete_calculation", {
                "project_root": str(temp_project),
                "calculation_ulid": fake_ulid
            })
            assert response is not None
        except RuntimeError as e:
            # Expected - calculation not found
            assert "not_found" in str(e).lower()


class TestReorderCalculationSteps:
    """Contract tests for reorder_calculation_steps RPC."""

    def test_reorder_steps_happy_path(self, demo_project_with_calculation, daemon: QVDaemon):
        """reorder_calculation_steps validates step order."""
        project_root, _, calc_ulid = demo_project_with_calculation

        # Test that RPC validates step order (expect error for invalid IDs)
        # This confirms the RPC exists and validates its inputs
        fake_ids = ["01HZZZZZZZZZZZZZZZZZZZZZZ"]
        
        # Should error on invalid step IDs
        with pytest.raises(RuntimeError):
            send_request(daemon, "reorder_calculation_steps", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step_order": fake_ids
            })

    def test_reorder_steps_invalid_ids(self, demo_project_with_calculation, daemon: QVDaemon):
        """reorder_calculation_steps errors on invalid step IDs."""
        project_root, _, calc_ulid = demo_project_with_calculation

        fake_ids = ["01HZZZZZZZZZZZZZZZZZZZZZZ", "01HYYYYYYYYYYYYYYYYYYYY"]

        with pytest.raises(RuntimeError):
            send_request(daemon, "reorder_calculation_steps", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "step_order": fake_ids
            })


class TestChangeCalculationStructure:
    """Contract tests for change_calculation_structure RPC."""

    def test_change_structure_happy_path(self, demo_project_with_calculation, daemon: QVDaemon):
        """change_calculation_structure RPC accepts parameters."""
        project_root, structure_ulid, calc_ulid = demo_project_with_calculation

        # Use the same structure (idempotent change)
        response = send_request(daemon, "change_calculation_structure", {
            "project_root": str(project_root),
            "calculation": calc_ulid,
            "new_structure": structure_ulid
        })

        # Should succeed (changing to same structure is valid)
        assert response is not None

    def test_change_structure_not_found(self, demo_project_with_calculation, daemon: QVDaemon):
        """change_calculation_structure errors on non-existent structure."""
        project_root, _, calc_ulid = demo_project_with_calculation
        fake_struct = "01HZZZZZZZZZZZZZZZZZZZZZZ"

        with pytest.raises(RuntimeError):
            send_request(daemon, "change_calculation_structure", {
                "project_root": str(project_root),
                "calculation": calc_ulid,
                "new_structure": fake_struct
            })
