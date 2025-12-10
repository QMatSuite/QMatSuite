"""
Non-GUI tests for workflow detail and structure change endpoints.

This module tests:
- get_workflow_detail returns workflows with steps
- change_workflow_structure correctly updates workflow structure

These tests ensure the GUI can display workflows with steps and change structures.
"""

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from quantumvitas.api import QVService
from quantumvitas.daemon.server import QVDaemon, RPCRequest


def send_request(daemon: QVDaemon, request_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Send a request to the daemon and return the response data."""
    response = daemon.handle_request(RPCRequest(
        id="test",
        type=request_type,
        payload=payload,
    ))
    
    if not response.ok:
        raise RuntimeError(f"Daemon request failed: {response.error}")
    
    return response.data


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project with a workflow and steps."""
    project_dir = tmp_path / "test_workflow_detail"
    project_dir.mkdir()
    
    # Initialize project
    QVService.init_project(project_dir, name="test_workflow_detail")
    
    # Import structures (using test data if available)
    test_data = Path(__file__).parent.parent / "data" / "workflow_bands"
    structures = {}
    if test_data.exists():
        scf_in = test_data / "si.0_scf.in"
        if scf_in.exists():
            structure1 = QVService.import_structure(
                project_root=project_dir,
                source=scf_in,
                name="Si",
            )
            structures["Si"] = structure1.meta.id
            
            # Create a second structure for testing structure change
            structure2 = QVService.import_structure(
                project_root=project_dir,
                source=scf_in,
                name="Si2",
            )
            structures["Si2"] = structure2.meta.id
        else:
            pytest.skip("Test data not available")
    else:
        pytest.skip("Test data not available")
    
    # Create a workflow with structure
    workflow_result = QVService.init_workflow(
        project_root=project_dir,
        name="test_workflow",
        structure_selector=structures["Si"],
    )
    workflow_id = workflow_result.meta.id
    
    # Add steps to the workflow
    QVService.add_step_to_workflow(
        project_root=project_dir,
        workflow_selector=workflow_id,
        step_type="scf",
    )
    QVService.add_step_to_workflow(
        project_root=project_dir,
        workflow_selector=workflow_id,
        step_type="nscf",
    )
    
    # Store structures dict in project_dir for use in tests
    (project_dir / ".test_structures.json").write_text(json.dumps(structures))
    
    return project_dir


@pytest.fixture
def daemon() -> QVDaemon:
    """Create a daemon instance for testing."""
    return QVDaemon()


class TestGetWorkflowDetail:
    """Test get_workflow_detail returns workflows with steps."""
    
    def test_get_workflow_detail_has_steps(self, temp_project: Path, daemon: QVDaemon):
        """Test that get_workflow_detail returns a workflow with non-empty steps list."""
        # Get workflow slug from list_workflows_data
        workflows = QVService.list_workflows_data(temp_project)
        assert len(workflows) > 0, "Project should have at least one workflow"
        workflow = workflows[0]
        workflow_slug = workflow["slug"]
        
        # Call get_workflow_detail via daemon
        result = send_request(daemon, "get_workflow_detail", {
            "project_root": str(temp_project.resolve()),
            "workflow": workflow_slug,
        })
        
        # Verify response structure
        assert "id" in result
        assert "name" in result
        assert "slug" in result
        assert "steps" in result
        assert "n_steps" in result
        
        # Verify steps are present
        assert isinstance(result["steps"], list), "steps should be a list"
        assert len(result["steps"]) > 0, "Workflow should have at least one step"
        assert result["n_steps"] == len(result["steps"]), "n_steps should match steps list length"
        
        # Verify step structure
        for step in result["steps"]:
            assert "step_id" in step or "id" in step, "Step should have step_id or id"
            assert "type" in step, "Step should have type"
            # step_file is NOT stored (resolved via registry)
            assert "step_file" not in step or step.get("step_file") is None, \
                "step_file should not be stored (resolved via registry)"
        
        # Verify step IDs match workflow model
        # Get workflow detail directly to compare
        direct_result = QVService.get_workflow_detail(
            project_root=temp_project,
            workflow_selector=workflow_slug,
        )
        assert len(direct_result["steps"]) == len(result["steps"]), \
            "Daemon result should match direct QVService result"
        
        # Verify step IDs are consistent
        daemon_step_ids = {s.get("step_id") or s.get("id") for s in result["steps"]}
        direct_step_ids = {s.get("step_id") or s.get("id") for s in direct_result["steps"]}
        assert daemon_step_ids == direct_step_ids, \
            "Step IDs from daemon should match direct QVService call"


class TestChangeWorkflowStructure:
    """Test change_workflow_structure endpoint."""
    
    def test_change_workflow_structure_via_daemon(self, temp_project: Path, daemon: QVDaemon):
        """Test that change_workflow_structure correctly updates workflow structure."""
        # Load structure IDs
        structures = json.loads((temp_project / ".test_structures.json").read_text())
        
        # Get workflow slug
        workflows = QVService.list_workflows_data(temp_project)
        assert len(workflows) > 0, "Project should have at least one workflow"
        workflow = workflows[0]
        workflow_slug = workflow["slug"]
        original_structure = workflow.get("structure")
        
        # Verify we have a different structure to change to
        assert "Si2" in structures, "Should have Si2 structure for testing"
        new_structure_slug = "Si2"  # Use slug as selector
        
        # Call change_workflow_structure via daemon
        result = send_request(daemon, "change_workflow_structure", {
            "project_root": str(temp_project.resolve()),
            "workflow": workflow_slug,
            "new_structure": new_structure_slug,
            "update_steps": True,
        })
        
        # Verify response structure
        assert "id" in result
        assert "name" in result
        assert "slug" in result
        assert "structure" in result
        assert "old_structure" in result
        assert "updated_steps" in result
        
        # Verify structure was updated
        assert result["structure"] == "Si2", "Structure should be updated to Si2"
        assert result["old_structure"] == original_structure, "old_structure should match original"
        
        # Verify workflow detail after change
        workflow_detail = send_request(daemon, "get_workflow_detail", {
            "project_root": str(temp_project.resolve()),
            "workflow": workflow_slug,
        })
        assert workflow_detail["structure"] == "Si2", \
            "Workflow detail should show updated structure"
        
        # Verify steps are still present after structure change
        assert len(workflow_detail["steps"]) > 0, \
            "Workflow should still have steps after structure change"
    
    def test_change_workflow_structure_rejects_project_root_as_selector(
        self, temp_project: Path, daemon: QVDaemon
    ):
        """Test that change_workflow_structure rejects project_root as structure selector."""
        workflows = QVService.list_workflows_data(temp_project)
        assert len(workflows) > 0
        workflow_slug = workflows[0]["slug"]
        
        # Try to pass project_root as new_structure (should fail)
        project_root_str = str(temp_project.resolve())
        response = daemon.handle_request(RPCRequest(
            id="test",
            type="change_workflow_structure",
            payload={
                "project_root": project_root_str,
                "workflow": workflow_slug,
                "new_structure": project_root_str,  # Wrong: passing project_root as selector
                "update_steps": True,
            },
        ))
        
        # Should fail with a clear error message
        assert not response.ok, "Should reject project_root as structure selector"
        assert "project root path" in response.error.get("message", "").lower() or \
               "invalid structure selector" in response.error.get("message", "").lower(), \
            f"Error message should mention invalid selector. Got: {response.error}"
