"""
RPC contract tests for project management endpoints.

Tests:
- find_project_root: Project discovery
- get_project_summary: Project metadata
- list_structures: Structure listing
- list_calculations: Calculation listing
"""

from pathlib import Path

import pytest

from quantumvitas.daemon.server import QVDaemon

from .conftest import send_request


class TestFindProjectRoot:
    """Contract tests for find_project_root RPC."""

    def test_find_project_root_from_root(self, temp_project: Path, daemon: QVDaemon):
        """find_project_root returns project root when given project root."""
        response = send_request(daemon, "find_project_root", {
            "start_dir": str(temp_project)
        })

        assert "found" in response
        assert response["found"] is True
        assert "project_root" in response
        assert response["project_root"] is not None
        assert Path(response["project_root"]).resolve() == temp_project.resolve()

    def test_find_project_root_from_subdirectory(self, temp_project: Path, daemon: QVDaemon):
        """find_project_root returns project root from subdirectory."""
        # Create a subdirectory
        subdir = temp_project / "structures"
        subdir.mkdir(exist_ok=True)

        response = send_request(daemon, "find_project_root", {
            "start_dir": str(subdir)
        })

        assert response["found"] is True
        assert response["project_root"] is not None
        assert Path(response["project_root"]).resolve() == temp_project.resolve()

    def test_find_project_root_not_found(self, tmp_path: Path, daemon: QVDaemon):
        """find_project_root returns found=False for non-project directory."""
        non_project = tmp_path / "not_a_project"
        non_project.mkdir()

        # This endpoint doesn't raise an error, it returns found=False
        response = send_request(daemon, "find_project_root", {
            "start_dir": str(non_project)
        })

        assert "found" in response
        assert response["found"] is False
        assert response["project_root"] is None


class TestGetProjectSummary:
    """Contract tests for get_project_summary RPC."""

    def test_get_project_summary_happy_path(self, temp_project: Path, daemon: QVDaemon):
        """get_project_summary returns project metadata."""
        response = send_request(daemon, "get_project_summary", {
            "project_root": str(temp_project)
        })

        # Validate schema
        assert "name" in response
        assert response["name"] == "test_project"
        assert "structure_count" in response or "n_structures" in response
        assert "calculation_count" in response or "n_calculations" in response

        # New project should have zero resources
        struct_count = response.get("structure_count") or response.get("n_structures")
        calc_count = response.get("calculation_count") or response.get("n_calculations")
        assert struct_count == 0
        assert calc_count == 0

    def test_get_project_summary_missing_param(self, daemon: QVDaemon):
        """get_project_summary errors on missing project_root."""
        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "get_project_summary", {})

        assert "invalid_argument" in str(exc_info.value) or "missing" in str(exc_info.value).lower()

    def test_get_project_summary_not_found(self, tmp_path: Path, daemon: QVDaemon):
        """get_project_summary errors on non-project directory."""
        non_project = tmp_path / "not_a_project"
        non_project.mkdir()

        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "get_project_summary", {
                "project_root": str(non_project)
            })

        assert "project_missing" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


class TestListStructures:
    """Contract tests for list_structures RPC."""

    def test_list_structures_empty_project(self, temp_project: Path, daemon: QVDaemon):
        """list_structures returns empty list for new project."""
        response = send_request(daemon, "list_structures", {
            "project_root": str(temp_project)
        })

        assert "structures" in response
        assert "count" in response
        assert response["structures"] == []
        assert response["count"] == 0

    def test_list_structures_with_data(self, demo_project_with_structure, daemon: QVDaemon):
        """list_structures returns structure metadata."""
        project_root, structure_ulid = demo_project_with_structure

        response = send_request(daemon, "list_structures", {
            "project_root": str(project_root)
        })

        assert response["count"] == 1
        assert len(response["structures"]) == 1

        struct = response["structures"][0]

        # Validate schema matches TypeScript StructureInfo
        # Check for either canonical or legacy field names
        assert "ulid" in struct or "structure_ulid" in struct or "id" in struct
        assert "formula" in struct
        assert "n_atoms" in struct or "num_atoms" in struct or "nsites" in struct

        # Verify ULID matches
        struct_id = struct.get("ulid") or struct.get("structure_ulid") or struct.get("id")
        assert struct_id == structure_ulid

    def test_list_structures_missing_param(self, daemon: QVDaemon):
        """list_structures errors on missing project_root."""
        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "list_structures", {})

        assert "invalid_argument" in str(exc_info.value) or "missing" in str(exc_info.value).lower()


class TestListCalculations:
    """Contract tests for list_calculations RPC."""

    def test_list_calculations_empty_project(self, temp_project: Path, daemon: QVDaemon):
        """list_calculations returns empty list for new project."""
        response = send_request(daemon, "list_calculations", {
            "project_root": str(temp_project)
        })

        assert "calculations" in response
        assert "count" in response
        assert response["calculations"] == []
        assert response["count"] == 0

    def test_list_calculations_with_data(self, demo_project_with_calculation, daemon: QVDaemon):
        """list_calculations returns calculation metadata with n_steps."""
        project_root, _, calc_ulid = demo_project_with_calculation

        response = send_request(daemon, "list_calculations", {
            "project_root": str(project_root)
        })

        assert response["count"] == 1
        assert len(response["calculations"]) == 1

        calc = response["calculations"][0]

        # Validate schema matches TypeScript CalculationInfo
        assert "ulid" in calc or "calc_ulid" in calc or "id" in calc

        # n_steps may be called differently
        assert "n_steps" in calc or "step_count" in calc or "steps" in calc

        # Verify ULID matches
        calc_id = calc.get("ulid") or calc.get("calc_ulid") or calc.get("id")
        assert calc_id == calc_ulid

        # Verify step count
        step_count = calc.get("n_steps") or calc.get("step_count")
        if step_count is not None:
            assert step_count == 1  # We added one SCF step

    def test_list_calculations_missing_param(self, daemon: QVDaemon):
        """list_calculations errors on missing project_root."""
        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "list_calculations", {})

        assert "invalid_argument" in str(exc_info.value) or "missing" in str(exc_info.value).lower()
