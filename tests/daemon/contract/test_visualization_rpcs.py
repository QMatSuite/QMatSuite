"""RPC contract tests for visualization endpoints."""

from pathlib import Path
import pytest
from quantumvitas.daemon.server import QVDaemon
from .conftest import send_request


class TestGetStructureVis:
    """Contract tests for get_structure_vis RPC."""

    def test_get_structure_vis_happy_path(self, demo_project_with_structure, daemon: QVDaemon):
        """get_structure_vis returns 3D viewer data."""
        project_root, structure_ulid = demo_project_with_structure

        response = send_request(daemon, "get_structure_vis", {
            "project_root": str(project_root),
            "selector": structure_ulid
        })

        # Validate schema matches actual response
        assert "structure_ulid" in response or "structure_id" in response
        assert "formula" in response
        assert "atoms" in response
        assert isinstance(response["atoms"], list)
        assert "bonds" in response
        assert "lattice" in response

    def test_get_structure_vis_with_supercell(self, demo_project_with_structure, daemon: QVDaemon):
        """get_structure_vis with supercell parameter."""
        project_root, structure_ulid = demo_project_with_structure

        response = send_request(daemon, "get_structure_vis", {
            "project_root": str(project_root),
            "selector": structure_ulid,
            "supercell": [2, 2, 1]
        })

        # Verify supercell is applied
        assert response["supercell"] == [2, 2, 1]
        # Should have more atoms than primitive cell (if crystal)

    def test_get_structure_vis_not_found(self, temp_project: Path, daemon: QVDaemon):
        """get_structure_vis errors on non-existent structure."""
        fake_ulid = "01HZZZZZZZZZZZZZZZZZZZZZZ"

        with pytest.raises(RuntimeError) as exc_info:
            send_request(daemon, "get_structure_vis", {
                "project_root": str(temp_project),
                "selector": fake_ulid
            })

        assert "not_found" in str(exc_info.value).lower()

    def test_get_structure_vis_workflow(self, demo_project_with_structure, daemon: QVDaemon):
        """get_structure_vis after list_structures."""
        project_root, structure_ulid = demo_project_with_structure

        # First list structures
        list_response = send_request(daemon, "list_structures", {
            "project_root": str(project_root)
        })
        assert list_response["count"] >= 1

        # Then get visualization
        vis_response = send_request(daemon, "get_structure_vis", {
            "project_root": str(project_root),
            "selector": structure_ulid
        })
        assert vis_response is not None
