"""
Non-GUI tests for GUI backend paths (daemon endpoints).

This module tests the exact same daemon endpoints that the GUI uses:
- Job submission (run_calculation)
- Job listing (list_jobs with project_root filter)
- Step detail retrieval (get_step_detail)

These tests simulate what the GUI does but in pure Python, ensuring:
- DAG + ID-only model is respected (calculation.structure_id ULID, step.step_id ULID)
- Selectors work correctly (calculation slug, step ULID)
- Path normalization is consistent (project_root matching)

Key invariants:
- Calculation YAML: structure_id (ULID), steps with step_id (ULID)
- Step YAML: NO structure_id, NO parent_calculation_id
- Job filtering: project_root must match exactly (normalized paths)
"""

import json
import shutil
import time
from pathlib import Path
from typing import Any, Dict

import pytest

from quantumvitas.api import QVService
from quantumvitas.daemon.server import QVDaemon, RPCRequest
from quantumvitas.daemon.jobs import JobManager, JobStatus
from quantumvitas.core.resolution import build_resource_index, require_calculation, require_step


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
    """Create a temporary project with a simple calculation."""
    project_dir = tmp_path / "test_gui_flows"
    project_dir.mkdir()
    
    # Initialize project
    QVService.init_project(project_dir, name="test_gui_flows")
    
    # Import a structure (using test data if available)
    test_data = Path(__file__).parent.parent / "data" / "calculation_bands"
    if test_data.exists():
        scf_in = test_data / "si.0_scf.in"
        if scf_in.exists():
            structure_resolved = QVService.import_structure(
                project_root=project_dir,
                source=scf_in,
                name="Si",
            )
            structure_id = structure_resolved.meta.id
        else:
            # Skip if no test data
            pytest.skip("Test data not available")
    else:
        # Skip if no test data
        pytest.skip("Test data not available")
    
    # Create a calculation with one SCF step
    calculation_result = QVService.init_calculation(
        project_root=project_dir,
        name="test_calculation",
        structure_selector=structure_id,
    )
    calculation_id = calculation_result.meta.id
    
    # Add a simple SCF step
    step_result = QVService.add_step_to_calculation(
        project_root=project_dir,
        calculation_selector=calculation_id,
        step_type="scf",
    )
    
    return project_dir


@pytest.fixture
def daemon() -> QVDaemon:
    """Create a daemon instance for testing."""
    return QVDaemon()


class TestJobSubmissionAndListing:
    """Test job submission and listing (GUI path)."""
    
    def test_submit_job_and_list_jobs(self, temp_project: Path, daemon: QVDaemon):
        """
        Test that submitting a calculation job and listing jobs works.
        
        This simulates:
        1. GUI calls run_calculation with calculation.slug
        2. GUI calls list_jobs with project_root filter
        3. Job should appear in the list
        """
        # Get calculation slug (GUI uses slug, not ULID)
        index = build_resource_index(temp_project)
        # Filter calculations by checking meta.kind
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0, "No calculations found"
        calculation = calculations[0]
        calculation_slug = calculation.slug
        
        # Normalize project_root (GUI sends string, daemon normalizes to Path)
        project_root_str = str(temp_project.resolve())
        
        # Submit job (GUI path: uses calculation.slug)
        submit_response = send_request(daemon, "run_calculation", {
            "project_root": project_root_str,
            "calculation": calculation_slug,
            "strict": False,
            "verbose": False,
        })
        
        assert "job_id" in submit_response
        job_id = submit_response["job_id"]
        assert submit_response["status"] == "pending"
        
        # List jobs with project_root filter (GUI path)
        # Note: GUI sends project_root as string, need to ensure it matches
        list_response = send_request(daemon, "list_jobs", {
            "project_root": project_root_str,
            "limit": 50,
        })
        
        assert "jobs" in list_response
        jobs = list_response["jobs"]
        
        # Job should appear in the list
        job_ids = [j["id"] for j in jobs]
        assert job_id in job_ids, f"Job {job_id} not found in list. Found: {job_ids}"
        
        # Verify job has correct project_root
        job = next(j for j in jobs if j["id"] == job_id)
        assert job["project_root"] == project_root_str, \
            f"Job project_root mismatch: {job['project_root']} != {project_root_str}"
        assert job["job_type"] == "run_calculation"
        assert job["target_name"] == calculation_slug
    
    def test_job_list_path_normalization(self, temp_project: Path, daemon: QVDaemon):
        """
        Test that job listing works with different path formats.
        
        GUI might send:
        - Absolute path: "/path/to/project"
        - Relative path: "./project" (if cwd is parent)
        - Path with trailing slash: "/path/to/project/"
        
        All should match the same job.
        """
        # Get calculation
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0
        calculation_slug = calculations[0].slug
        
        project_root_abs = str(temp_project.resolve())
        
        # Submit job
        submit_response = send_request(daemon, "run_calculation", {
            "project_root": project_root_abs,
            "calculation": calculation_slug,
        })
        job_id = submit_response["job_id"]
        
        # Test different path formats
        formats = [
            project_root_abs,  # Absolute, no trailing slash
            project_root_abs + "/",  # Absolute, trailing slash
            str(temp_project),  # Might be relative or absolute
        ]
        
        for path_format in formats:
            list_response = send_request(daemon, "list_jobs", {
                "project_root": path_format,
            })
            job_ids = [j["id"] for j in list_response["jobs"]]
            assert job_id in job_ids, \
                f"Job not found with path format: {path_format}"


class TestStepDetailRetrieval:
    """Test step detail retrieval (GUI path)."""
    
    def test_get_step_detail_with_ulid(self, temp_project: Path, daemon: QVDaemon):
        """
        Test that step detail can be retrieved using step ULID.
        
        GUI path:
        1. Calculation list shows steps with step.id (ULID)
        2. Clicking step calls get_step_detail with calculation.slug and step.id
        3. Should return step details
        """
        # Get calculation and step info
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0
        calculation = calculations[0]
        calculation_slug = calculation.slug
        
        # Get step ULID from calculation
        calculation_resolved = require_calculation(temp_project, calculation_slug, index=index)
        from quantumvitas.core.models import load_calculation
        wf_model = load_calculation(calculation_resolved.absolute_path, temp_project)
        assert len(wf_model.steps) > 0
        step_entry = wf_model.steps[0]
        step_id_ulid = step_entry.step_id
        assert step_id_ulid, "Step should have step_id (ULID)"
        assert len(step_id_ulid) == 26, f"step_id should be ULID (26 chars), got: {step_id_ulid}"
        
        project_root_str = str(temp_project.resolve())
        
        # Get step detail (GUI path: calculation.slug + step.id ULID)
        detail_response = send_request(daemon, "get_step_detail", {
            "project_root": project_root_str,
            "calculation": calculation_slug,
            "step": step_id_ulid,
        })
        
        assert "id" in detail_response
        assert detail_response["id"] == step_id_ulid
        assert "step_type" in detail_response
        assert "parameters" in detail_response
        assert "cards" in detail_response
    
    def test_get_step_detail_requires_ulid_from_calculation_yaml(self, temp_project: Path, daemon: QVDaemon):
        """
        Test that get_step_detail requires step_selector to be a ULID that exists in calculation.yaml.
        
        GUI path is now ULID-only: step_selector MUST be a ULID from calculation.yaml's steps array.
        Slug/name fallback is no longer supported for GUI path (legacy selector support dropped).
        """
        # Get calculation
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0
        calculation_slug = calculations[0].slug
        
        # Get step via registry to find its slug
        calculation_resolved = require_calculation(temp_project, calculation_slug, index=index)
        from quantumvitas.core.models import load_calculation
        wf_model = load_calculation(calculation_resolved.absolute_path, temp_project)
        step_entry = wf_model.steps[0]
        step_id_ulid = step_entry.step_id
        
        # Resolve step to get its slug
        step_resolved = require_step(temp_project, calculation_slug, step_id_ulid)
        step_slug = step_resolved.meta.slug
        
        project_root_str = str(temp_project.resolve())
        
        # Try to get step detail using slug instead of ULID - should FAIL
        # GUI path now requires ULID from calculation.yaml
        response = daemon.handle_request(RPCRequest(
            id="test",
            type="get_step_detail",
            payload={
                "project_root": project_root_str,
                "calculation": calculation_slug,
                "step": step_slug,  # Using slug, not ULID
            },
        ))
        
        # Should fail with resource_not_found error
        assert not response.ok, "get_step_detail with slug should fail (ULID-only for GUI path)"
        assert response.error is not None
        assert response.error.get("code") == "resource_not_found"
        assert response.error.get("kind") == "step"


class TestDAGInvariants:
    """Test that DAG + ID-only invariants are maintained."""
    
    def test_calculation_has_structure_id_ulid(self, temp_project: Path):
        """Verify calculation.yaml has structure_id (ULID), not structure selector."""
        from quantumvitas.core.models import load_calculation
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        calculation = calculations[0]
        calculation_resolved = require_calculation(temp_project, calculation.slug, index=index)
        
        wf_model = load_calculation(calculation_resolved.absolute_path, temp_project)
        
        # Should have structure_id (ULID)
        assert wf_model.structure_id, "Calculation should have structure_id"
        assert len(wf_model.structure_id) == 26, \
            f"structure_id should be ULID (26 chars), got: {wf_model.structure_id}"
        
        # Should NOT have structure selector in YAML (but may be present in-memory for compat)
        # The to_dict() should not write it
    
    def test_step_yaml_no_structure_id(self, temp_project: Path):
        """Verify step YAML does NOT contain structure_id or parent_calculation_id."""
        from quantumvitas.calculation.structure_steps import StructureStepSpec
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0
        calculation = calculations[0]
        calculation_resolved = require_calculation(temp_project, calculation.slug, index=index)
        
        from quantumvitas.core.models import load_calculation
        wf_model = load_calculation(calculation_resolved.absolute_path, temp_project)
        step_entry = wf_model.steps[0]
        step_id_ulid = step_entry.step_id
        
        # Resolve step file
        step_resolved = require_step(temp_project, calculation.slug, step_id_ulid)
        
        # Load step spec
        spec = StructureStepSpec.from_yaml(step_resolved.absolute_path)
        
        # Verify step YAML does NOT contain these fields
        step_dict = spec.to_dict()
        assert "structure_id" not in step_dict, \
            "Step YAML should NOT contain structure_id (DAG invariant)"
        assert "parent_calculation_id" not in step_dict, \
            "Step YAML should NOT contain parent_calculation_id (DAG invariant)"
        assert "structure" not in step_dict or step_dict["structure"] == "", \
            "Step YAML should NOT contain structure selector (DAG invariant)"


class TestStepCreationRaceCondition:
    """Test race condition handling when step is created and immediately accessed."""
    
    def test_immediate_get_step_detail_after_add_step(self, temp_project: Path, daemon: QVDaemon):
        """
        Test that get_step_detail succeeds immediately after add_step_to_calculation.
        
        This test verifies that the ResourceIndex is properly refreshed after step creation,
        preventing "Step not found" errors when the GUI immediately tries to fetch step detail.
        
        RACE CONDITION SCENARIO:
        1. GUI calls add_step_to_calculation RPC
        2. Daemon creates step file and updates calculation.yaml
        3. GUI immediately calls get_step_detail with the returned step_id
        4. ResourceIndex should be refreshed by daemon, so get_step_detail should succeed
        """
        project_root = str(temp_project.resolve())
        
        # Get the calculation slug from the project
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0, "Project should have at least one calculation"
        calculation_slug = calculations[0].slug
        
        # Add a new step via daemon RPC (simulating GUI action)
        add_result = send_request(daemon, "add_step_to_calculation", {
            "project_root": project_root,
            "calculation": calculation_slug,
            "step_type": "nscf",
            "step_name": "nscf",
        })
        
        # Verify the step was added
        assert "steps" in add_result, "add_step_to_calculation should return steps list"
        steps = add_result["steps"]
        assert len(steps) > 0, "Step should be added to calculation"
        
        # Find the newly added step (should be the last one with type 'nscf')
        new_step = None
        for step in steps:
            if step.get("type") == "nscf":
                new_step = step
                break
        
        assert new_step is not None, "New nscf step should be in the returned steps"
        new_step_id = new_step.get("step_id")
        assert new_step_id is not None, "Step should have step_id (ULID)"
        assert len(new_step_id) == 26, f"step_id should be ULID (26 chars), got: {new_step_id}"
        
        # CRITICAL: Immediately try to get step detail using the returned step_id.
        # This simulates the GUI clicking on the step right after creation.
        # The ResourceIndex should be refreshed by the daemon handler, so this should succeed
        # without raising ResourceNotFoundError.
        step_detail = send_request(daemon, "get_step_detail", {
            "project_root": project_root,
            "calculation": calculation_slug,
            "step": new_step_id,
        })
        
        # Verify step detail was retrieved successfully
        assert step_detail is not None, "Step detail should be retrieved"
        assert step_detail.get("id") == new_step_id, "Step detail ID should match"
        assert step_detail.get("step_type") == "nscf", "Step type should be nscf"
        
        # Verify no ResourceNotFoundError was raised (would indicate stale index)
        # The step should be found even though it was just created
        
        # CRITICAL: Verify the step YAML file was actually created on disk
        # This ensures add_step_to_calculation creates the file, not just the calculation entry
        from quantumvitas.core.models import load_calculation
        calculation_resolved = require_calculation(temp_project, calculation_slug, index=build_resource_index(temp_project))
        wf_model = load_calculation(calculation_resolved.absolute_path / "calculation.yaml", temp_project)
        
        # Find the step entry we just created
        new_step_entry = None
        for step in wf_model.steps:
            if step.step_id == new_step_id:
                new_step_entry = step
                break
        
        assert new_step_entry is not None, f"Step entry with id {new_step_id} should be in calculation.yaml"
        
        # Resolve the step to get its file path
        step_resolved = require_step(temp_project, calculation_slug, new_step_id)
        step_file_path = step_resolved.absolute_path
        
        # Verify the step file exists on disk
        assert step_file_path.exists(), \
            f"Step YAML file should exist at {step_file_path}. " \
            f"The calculation entry exists but the step file is missing (ghost step bug)."
        
        # Verify the file is readable and contains valid YAML
        import yaml
        step_data = yaml.safe_load(step_file_path.read_text())
        assert step_data is not None, "Step file should contain valid YAML"
        assert "meta" in step_data, "Step file should have meta block"
        assert step_data["meta"]["id"] == new_step_id, "Step file meta.id should match calculation entry step_id"
        
        # Verify DAG invariants: step file should NOT contain structure_id or parent_calculation_id
        assert "structure_id" not in step_data, "Step YAML should NOT contain structure_id (DAG invariant)"
        assert "parent_calculation_id" not in step_data, "Step YAML should NOT contain parent_calculation_id (DAG invariant)"


class TestStepDeletion:
    """Test step deletion via daemon RPC."""
    
    def test_delete_step_via_daemon_removes_from_calculation_yaml(self, temp_project: Path, daemon: QVDaemon):
        """Test that delete_step removes the step entry from calculation.yaml."""
        # Get calculation and step info
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0
        calculation = calculations[0]
        calculation_slug = calculation.slug
        
        # Get step ULID from calculation
        calculation_resolved = require_calculation(temp_project, calculation_slug, index=index)
        from quantumvitas.core.models import load_calculation
        wf_model = load_calculation(calculation_resolved.absolute_path, temp_project)
        assert len(wf_model.steps) > 0
        step_entry = wf_model.steps[0]
        step_id_ulid = step_entry.step_id
        initial_step_count = len(wf_model.steps)
        
        project_root_str = str(temp_project.resolve())
        
        # Delete step via daemon
        result = send_request(daemon, "delete_step", {
            "project_root": project_root_str,
            "calculation": calculation_slug,
            "step": step_id_ulid,
        })
        
        assert result.get("status") == "deleted"
        
        # Reload calculation.yaml and verify step is removed
        wf_model_after = load_calculation(calculation_resolved.absolute_path, temp_project)
        assert len(wf_model_after.steps) == initial_step_count - 1
        assert not any(s.step_id == step_id_ulid for s in wf_model_after.steps), \
            f"Step {step_id_ulid} should be removed from calculation.yaml"
    
    def test_delete_step_via_daemon_moves_step_file_to_trash(self, temp_project: Path, daemon: QVDaemon):
        """Test that delete_step moves the step file to the trash directory."""
        # Get calculation and step info
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0
        calculation = calculations[0]
        calculation_slug = calculation.slug
        
        # Get step ULID and file path
        calculation_resolved = require_calculation(temp_project, calculation_slug, index=index)
        from quantumvitas.core.models import load_calculation
        wf_model = load_calculation(calculation_resolved.absolute_path, temp_project)
        assert len(wf_model.steps) > 0
        step_entry = wf_model.steps[0]
        step_id_ulid = step_entry.step_id
        
        step_resolved = require_step(temp_project, calculation_slug, step_id_ulid, index=index)
        original_step_path = step_resolved.absolute_path
        
        assert original_step_path.exists(), "Step file should exist before deletion"
        
        project_root_str = str(temp_project.resolve())
        trash_dir = temp_project / "trash"
        
        # Delete step via daemon
        result = send_request(daemon, "delete_step", {
            "project_root": project_root_str,
            "calculation": calculation_slug,
            "step": step_id_ulid,
        })
        
        assert result.get("status") == "deleted"
        
        # Verify original file no longer exists
        assert not original_step_path.exists(), \
            f"Original step file {original_step_path} should be moved to trash"
        
        # Verify file exists in trash directory
        assert trash_dir.exists(), "Trash directory should exist"
        # Find the moved file (it will have a timestamp suffix)
        trash_files = list(trash_dir.glob(f"{original_step_path.name}_*"))
        assert len(trash_files) > 0, \
            f"Step file should be in trash directory. Found: {list(trash_dir.glob('*'))}"
        
        # Verify the trash file has the same basename (before timestamp)
        trash_file = trash_files[0]
        assert trash_file.name.startswith(original_step_path.name), \
            f"Trash file {trash_file.name} should start with original name {original_step_path.name}"
    
    def test_delete_step_via_daemon_allows_missing_step_file(self, temp_project: Path, daemon: QVDaemon):
        """Test that delete_step handles ghost steps (entry in calculation.yaml but no file) gracefully."""
        # Get calculation and step info
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0
        calculation = calculations[0]
        calculation_slug = calculation.slug
        
        # Get step ULID from calculation
        calculation_resolved = require_calculation(temp_project, calculation_slug, index=index)
        from quantumvitas.core.models import load_calculation
        wf_model = load_calculation(calculation_resolved.absolute_path, temp_project)
        assert len(wf_model.steps) > 0
        step_entry = wf_model.steps[0]
        step_id_ulid = step_entry.step_id
        initial_step_count = len(wf_model.steps)
        
        # Manually delete the step file to simulate a ghost step
        step_resolved = require_step(temp_project, calculation_slug, step_id_ulid, index=index)
        step_file_path = step_resolved.absolute_path
        if step_file_path.exists():
            step_file_path.unlink()
        
        project_root_str = str(temp_project.resolve())
        
        # Delete step via daemon - should succeed even though file is missing
        result = send_request(daemon, "delete_step", {
            "project_root": project_root_str,
            "calculation": calculation_slug,
            "step": step_id_ulid,
        })
        
        assert result.get("status") == "deleted"
        
        # Verify step entry is removed from calculation.yaml
        wf_model_after = load_calculation(calculation_resolved.absolute_path, temp_project)
        assert len(wf_model_after.steps) == initial_step_count - 1
        assert not any(s.step_id == step_id_ulid for s in wf_model_after.steps), \
            f"Step {step_id_ulid} should be removed from calculation.yaml even if file was missing"
    
    def test_delete_step_via_daemon_invalid_ulid_raises_resource_not_found(self, temp_project: Path, daemon: QVDaemon):
        """Test that delete_step with invalid ULID raises resource_not_found error."""
        # Get calculation
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0
        calculation_slug = calculations[0].slug
        
        # Use a random ULID that doesn't exist
        import ulid as ulid_module
        fake_step_id = str(ulid_module.new())
        
        project_root_str = str(temp_project.resolve())
        
        # Try to delete non-existent step - should fail
        response = daemon.handle_request(RPCRequest(
            id="test",
            type="delete_step",
            payload={
                "project_root": project_root_str,
                "calculation": calculation_slug,
                "step": fake_step_id,
            },
        ))
        
        assert not response.ok, "delete_step with invalid ULID should fail"
        assert response.error is not None
        # The error code may be "resource_not_found" or "invalid_argument" depending on where validation happens
        assert response.error.get("code") in ("resource_not_found", "invalid_argument"), \
            f"Expected resource_not_found or invalid_argument, got {response.error.get('code')}"
        # If it's resource_not_found, it should have kind="step"
        if response.error.get("code") == "resource_not_found":
            assert response.error.get("kind") == "step"


class TestCalculationFailureHandling:
    """Test that multi-step calculations stop after a step failure."""
    
    def test_calculation_stops_after_step_failure(self, temp_project: Path, daemon: QVDaemon, monkeypatch):
        """
        Test that when a multi-step calculation runs and a middle step fails,
        later dependent steps are not executed and are marked as SKIPPED.
        
        Scenario:
        - Calculation chain: scf → nscf → projwfc
        - Simulate that nscf step fails
        - Expected: scf succeeds, nscf fails, projwfc is SKIPPED, calculation is FAILED
        """
        # Create a calculation with multiple steps
        project_root_str = str(temp_project.resolve())
        
        # Get calculation
        index = build_resource_index(temp_project)
        calculations = [meta for meta in index.by_id.values() if meta.kind == "calculation"]
        assert len(calculations) > 0
        calculation_slug = calculations[0].slug
        
        # Add additional steps to create a multi-step calculation
        # Add nscf step
        send_request(daemon, "add_step_to_calculation", {
            "project_root": project_root_str,
            "calculation": calculation_slug,
            "step_type": "nscf",
        })
        
        # Add projwfc step
        send_request(daemon, "add_step_to_calculation", {
            "project_root": project_root_str,
            "calculation": calculation_slug,
            "step_type": "projwfc",
        })
        
        # Verify calculation has 3 steps now
        calculation_resolved = require_calculation(temp_project, calculation_slug, index=index)
        from quantumvitas.core.models import load_calculation
        wf_model = load_calculation(calculation_resolved.absolute_path, temp_project)
        assert len(wf_model.steps) >= 3, "Calculation should have at least 3 steps"
        
        # Get step IDs
        step_ids = [s.step_id for s in wf_model.steps]
        scf_step_id = step_ids[0]
        nscf_step_id = step_ids[1]
        projwfc_step_id = step_ids[2]
        
        # Mock the calculation runner to simulate nscf failure
        from quantumvitas.calculation.runner import CalculationRunner
        from quantumvitas.calculation.types import StepStatus, StepType
        from quantumvitas.calculation.results import CalculationResult, StepResultSummary
        from datetime import datetime, timezone
        
        original_run = CalculationRunner.run
        
        def mock_run_with_failure(self, calculation):
            """Mock runner that simulates nscf step failure."""
            from quantumvitas.calculation.types import StepMode
            started = datetime.now(timezone.utc)
            step_summaries = []
            calculation_failed = False
            
            # Get step IDs from calculation model (ULIDs from calculation.yaml)
            from quantumvitas.core.models import load_calculation
            wf_model = load_calculation(calculation.dir / "calculation.yaml", calculation.project.root)
            step_ulids = [s.step_id for s in wf_model.steps]
            
            for i, step in enumerate(calculation.steps):
                # Use ULID from calculation.yaml, not step.id (which is slug)
                step_id = step_ulids[i] if i < len(step_ulids) else step.id
                step_type = step.step_type or StepType.CUSTOM
                
                # If a previous step failed, mark remaining steps as SKIPPED
                if calculation_failed:
                    summary = StepResultSummary(
                        step_id=step_id,
                        step_type=step_type,
                        status=StepStatus.SKIPPED,
                        working_dir=calculation.raw_dir,
                        input_file=step.input_file if hasattr(step, 'input_file') else Path(),
                        output_file=Path(),
                        reference_file=step.reference_output,
                        message="Step skipped because a previous step failed",
                        metrics={},
                    )
                    step_summaries.append(summary)
                    continue
                
                # Simulate step execution
                # First step (scf) succeeds
                if i == 0:
                    step_status = StepStatus.SUCCESS
                    message = "SCF converged"
                # Second step (nscf) fails
                elif i == 1:
                    step_status = StepStatus.FAILED
                    message = "NSCF calculation failed"
                    calculation_failed = True
                # Third step (projwfc) should be skipped
                else:
                    step_status = StepStatus.SKIPPED
                    message = "Step skipped because a previous step failed"
                
                summary = StepResultSummary(
                    step_id=step_id,
                    step_type=step_type,
                    status=step_status,
                    working_dir=calculation.raw_dir,
                    input_file=step.input_file if hasattr(step, 'input_file') else Path(),
                    output_file=Path() if step_status == StepStatus.SKIPPED else Path("/tmp/fake.out"),
                    reference_file=step.reference_output,
                    message=message,
                    metrics={},
                )
                step_summaries.append(summary)
                
                if step_status != StepStatus.SUCCESS:
                    calculation_failed = True
                    if calculation.mode == StepMode.STRICT:
                        break
            
            finished = datetime.now(timezone.utc)
            calculation_status = StepStatus.FAILED if calculation_failed else StepStatus.SUCCESS
            return CalculationResult(
                calculation_id=calculation.id,
                mode=calculation.mode,
                steps=step_summaries,
                status=calculation_status,
                started_at=started,
                finished_at=finished,
            )
        
        # Patch the runner
        monkeypatch.setattr(CalculationRunner, "run", mock_run_with_failure)
        
        # Mock pseudopotential resolution to avoid pseudo requirements
        def fake_ensure_qe_pseudos(*args, **kwargs):
            from quantumvitas.core.pseudo import PseudoResolutionResult
            from pathlib import Path
            # Return success without actually resolving pseudos
            return PseudoResolutionResult(
                project_pseudo_dir=Path("/tmp/pseudo"),
                system_pseudo_dir=None,
                resolved_pseudos={},
                all_available=True,
            )
        
        monkeypatch.setattr("quantumvitas.core.pseudo.ensure_qe_pseudos", fake_ensure_qe_pseudos)
        
        # Run calculation via daemon
        submit_response = send_request(daemon, "run_calculation", {
            "project_root": project_root_str,
            "calculation": calculation_slug,
            "strict": True,  # Use strict mode to ensure failure stops execution
            "verbose": False,
        })
        
        job_id = submit_response["job_id"]
        
        # Wait for job to complete (mocked runner should be fast)
        import time
        max_wait = 5
        wait_time = 0
        while wait_time < max_wait:
            job_status = daemon.job_manager.get_job_status(job_id)
            if job_status and job_status["status"] in ("completed", "failed"):
                break
            time.sleep(0.2)
            wait_time += 0.2
        
        # Get job result
        job = daemon.job_manager.get_job(job_id)
        assert job is not None, "Job should exist"
        assert job.status.value in ("completed", "failed"), \
            f"Job should be completed or failed, got {job.status.value}. Job: {job.to_dict() if job else None}"
        
        # Get calculation result from job
        result = job.result
        assert result is not None, \
            f"Job should have a result. Job status: {job.status.value}, error: {job.error}"
        
        # Verify calculation status is FAILED
        assert result["status"] == "failed", f"Calculation should be FAILED, got {result['status']}"
        
        # Verify step statuses
        steps = result["steps"]
        assert len(steps) == 3, f"Should have 3 steps, got {len(steps)}"
        
        # First step (scf) should be SUCCESS
        scf_step = next(s for s in steps if s["step_id"] == scf_step_id)
        assert scf_step["status"] == "success", f"SCF step should be SUCCESS, got {scf_step['status']}"
        
        # Second step (nscf) should be FAILED
        nscf_step = next(s for s in steps if s["step_id"] == nscf_step_id)
        assert nscf_step["status"] == "failed", f"NSCF step should be FAILED, got {nscf_step['status']}"
        
        # Third step (projwfc) should be SKIPPED
        projwfc_step = next(s for s in steps if s["step_id"] == projwfc_step_id)
        assert projwfc_step["status"] == "skipped", \
            f"PROJWFC step should be SKIPPED, got {projwfc_step['status']}"
        assert "skipped because a previous step failed" in projwfc_step.get("message", "").lower(), \
            "SKIPPED step should have appropriate message"

