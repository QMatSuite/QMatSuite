"""
Non-GUI tests for calculation detail and structure change endpoints.

This module tests:
- get_calculation_detail returns calculations with steps
- change_calculation_structure correctly updates calculation structure

These tests ensure the GUI can display calculations with steps and change structures.
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
    """Create a temporary project with a calculation and steps."""
    project_dir = tmp_path / "test_calculation_detail"
    project_dir.mkdir()
    
    # Initialize project
    QVService.init_project(project_dir, name="test_calculation_detail")
    
    # Import structures (using test data if available)
    test_data = Path(__file__).parent.parent / "data" / "calculation_bands"
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
    
    # Create a calculation with structure
    calculation_result = QVService.init_calculation(
        project_root=project_dir,
        name="test_calculation",
        structure_selector=structures["Si"],
    )
    calculation_id = calculation_result.meta.id
    
    # Use domain accessor API for step creation
    svc = QVService(project_dir)
    
    # Add steps to the calculation
    svc.calculation.add_step(
        calc_selector=calculation_id,
        step_type="scf",
    )
    svc.calculation.add_step(
        calc_selector=calculation_id,
        step_type="nscf",
    )
    
    # Store structures dict in project_dir for use in tests
    (project_dir / ".test_structures.json").write_text(json.dumps(structures))
    
    return project_dir


@pytest.fixture
def daemon() -> QVDaemon:
    """Create a daemon instance for testing."""
    return QVDaemon()


class TestGetCalculationDetail:
    """Test get_calculation_detail returns calculations with steps."""
    
    def test_get_calculation_detail_has_steps(self, temp_project: Path, daemon: QVDaemon):
        """Test that get_calculation_detail returns a calculation with non-empty steps list."""
        # Get calculation slug from list_calculations_data
        calculations = QVService.list_calculations_data(temp_project)
        assert len(calculations) > 0, "Project should have at least one calculation"
        calculation = calculations[0]
        calculation_slug = calculation["slug"]
        
        # Call get_calculation_detail via daemon
        result = send_request(daemon, "get_calculation_detail", {
            "project_root": str(temp_project.resolve()),
            "calculation": calculation_slug,
        })
        
        # Verify response structure
        assert "id" in result
        assert "name" in result
        assert "slug" in result
        assert "steps" in result
        assert "n_steps" in result
        
        # Verify steps are present
        assert isinstance(result["steps"], list), "steps should be a list"
        assert len(result["steps"]) > 0, "Calculation should have at least one step"
        assert result["n_steps"] == len(result["steps"]), "n_steps should match steps list length"
        
        # Verify step structure
        for step in result["steps"]:
            assert "step_id" in step or "id" in step, "Step should have step_id or id"
            assert "type" in step, "Step should have type"
            # step_file is now included for convenience (relative path from calculation directory)
            # This helps GUI display step file paths without needing to resolve via registry
            if "step_file" in step:
                assert isinstance(step["step_file"], str), "step_file should be a string if present"
        
        # Verify step IDs match calculation model
        # Get calculation detail directly to compare (resolve slug to ULID first)
        from quantumvitas.core.resolution import resolve_calculation
        from quantumvitas._api_legacy import QVService as LegacyService
        calculation_resolved = resolve_calculation(temp_project, calculation_slug)
        direct_result = LegacyService.get_calculation_detail(
            project_root=temp_project,
            calculation_ulid=calculation_resolved.meta.id,
        )
        assert len(direct_result["steps"]) == len(result["steps"]), \
            "Daemon result should match direct QVService result"
        
        # Verify step IDs are consistent
        daemon_step_ids = {s.get("step_id") or s.get("id") for s in result["steps"]}
        direct_step_ids = {s.get("step_id") or s.get("id") for s in direct_result["steps"]}
        assert daemon_step_ids == direct_step_ids, \
            "Step IDs from daemon should match direct QVService call"
    
    def test_multi_step_calculation_ulid_only_selectors(self, temp_project: Path, daemon: QVDaemon):
        """
        Test that multi-step calculations use ULID-only selectors and preserve order from calculation.yaml.
        
        This test ensures:
        - Steps are returned in calculation.yaml order (not filesystem order)
        - Each step.id is a 26-character ULID
        - get_step_detail works for ALL steps (not just the first)
        - The entire chain (calculation.yaml → API → GUI → daemon → API) is ULID-based
        """
        # Get calculation slug
        calculations = QVService.list_calculations_data(temp_project)
        assert len(calculations) > 0, "Project should have at least one calculation"
        calculation = calculations[0]
        calculation_slug = calculation["slug"]
        
        # Add more steps to create a multi-step calculation (scf, nscf, bands_pw, bands)
        # The temp_project fixture already has scf and nscf, so add bands_pw and bands
        svc = QVService(temp_project)
        svc.calculation.add_step(
            calc_selector=calculation_slug,
            step_type="bands_pw",
        )
        svc.calculation.add_step(
            calc_selector=calculation_slug,
            step_type="bands",
        )
        
        # Get calculation detail via daemon
        result = send_request(daemon, "get_calculation_detail", {
            "project_root": str(temp_project.resolve()),
            "calculation": calculation_slug,
        })
        
        # Verify we have at least 3-4 steps
        assert len(result["steps"]) >= 3, f"Calculation should have at least 3 steps, got {len(result['steps'])}"
        assert result["n_steps"] == len(result["steps"]), "n_steps should match steps list length"
        
        # Verify each step has a ULID (26 characters)
        step_ids = []
        for step in result["steps"]:
            step_id = step.get("id") or step.get("step_id")
            assert step_id is not None, "Step must have id field"
            assert isinstance(step_id, str), "Step id must be a string"
            assert len(step_id) == 26, f"Step id must be a ULID (26 chars), got '{step_id}' (length {len(step_id)})"
            step_ids.append(step_id)
        
        # Verify steps are in expected order (scf, nscf, bands_pw, bands)
        # We can't verify exact types without loading the step files, but we can verify
        # that the order is consistent (same order as calculation.yaml)
        expected_types = ["scf", "nscf", "bands_pw", "bands"]
        actual_types = [step.get("type") for step in result["steps"]]

        # Verify we have the expected step types (order may vary slightly, but all should be present)
        for expected_type in expected_types[:len(actual_types)]:
            assert expected_type in actual_types, f"Expected step type '{expected_type}' not found in {actual_types}"
        
        # CRITICAL: Test that get_step_detail works for ALL steps (not just the first)
        # This ensures the ULID-based resolution works for every step in the calculation
        for idx, step in enumerate(result["steps"]):
            step_id = step.get("id") or step.get("step_id")
            step_type = step.get("type")
            
            # Call get_step_detail via daemon with the ULID
            step_detail = send_request(daemon, "get_step_detail", {
                "project_root": str(temp_project.resolve()),
                "calculation": calculation_slug,
                "step": step_id,  # Use ULID as selector
            })
            
            # Verify response structure
            assert "id" in step_detail, f"Step {idx} detail should have id field"
            assert step_detail["id"] == step_id, \
                f"Step {idx} detail id should match calculation step id. Expected {step_id}, got {step_detail['id']}"
            assert "step_type" in step_detail, f"Step {idx} detail should have step_type field"
            
            # Verify step_type is related (calculation.yaml may store public type, step.yaml stores machine type)
            # e.g., calculation.yaml: "scf", step.yaml: "qe_scf" - both are valid representations
            if step_type:
                detail_step_type = step_detail["step_type"]
                # Allow either exact match or public/machine type equivalence
                matches = (
                    detail_step_type == step_type or
                    detail_step_type == f"qe_{step_type}" or
                    step_type == f"qe_{detail_step_type}" or
                    detail_step_type.replace("qe_", "") == step_type.replace("qe_", "")
                )
                assert matches, \
                    f"Step {idx} detail step_type should be related. Expected {step_type} or qe_{step_type}, got {detail_step_type}"
            
            # Verify other expected fields
            assert "parameters" in step_detail, f"Step {idx} detail should have parameters field"
            assert "name" in step_detail or "slug" in step_detail, \
                f"Step {idx} detail should have name or slug field"
        
        # Verify step order is preserved from calculation.yaml
        # Load calculation model directly to compare order
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.project_utils import load_project_config
        from quantumvitas.core.resolution import make_structure_selector_resolver
        
        config = load_project_config(temp_project)
        resolver = make_structure_selector_resolver(temp_project, config=config)
        calculation_yaml_path = temp_project / "calculations" / calculation_slug / "calculation.yaml"
        wf_model = load_calculation(calculation_yaml_path, project_root=temp_project, resolve_structure_selector=resolver)
        
        # Verify step IDs match calculation.yaml order
        calculation_yaml_step_ids = [entry.step_id for entry in wf_model.steps]
        api_step_ids = [step.get("id") or step.get("step_id") for step in result["steps"]]
        
        assert len(calculation_yaml_step_ids) == len(api_step_ids), \
            f"Step count mismatch: calculation.yaml has {len(calculation_yaml_step_ids)}, API returned {len(api_step_ids)}"
        
        assert calculation_yaml_step_ids == api_step_ids, \
            f"Step order mismatch. calculation.yaml: {calculation_yaml_step_ids}, API: {api_step_ids}"


class TestChangeCalculationStructure:
    """Test change_calculation_structure endpoint."""
    
    def test_change_calculation_structure_via_daemon(self, temp_project: Path, daemon: QVDaemon):
        """Test that change_calculation_structure correctly updates calculation structure."""
        # Load structure IDs
        structures = json.loads((temp_project / ".test_structures.json").read_text())
        
        # Get calculation slug
        calculations = QVService.list_calculations_data(temp_project)
        assert len(calculations) > 0, "Project should have at least one calculation"
        calculation = calculations[0]
        calculation_slug = calculation["slug"]
        original_structure = calculation.get("structure")
        
        # Verify we have a different structure to change to
        assert "Si2" in structures, "Should have Si2 structure for testing"
        new_structure_slug = "Si2"  # Use slug as selector
        
        # Call change_calculation_structure via daemon
        result = send_request(daemon, "change_calculation_structure", {
            "project_root": str(temp_project.resolve()),
            "calculation": calculation_slug,
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
        
        # Verify calculation detail after change
        calculation_detail = send_request(daemon, "get_calculation_detail", {
            "project_root": str(temp_project.resolve()),
            "calculation": calculation_slug,
        })
        assert calculation_detail["structure"] == "Si2", \
            "Calculation detail should show updated structure"
        
        # Verify steps are still present after structure change
        assert len(calculation_detail["steps"]) > 0, \
            "Calculation should still have steps after structure change"
    
    def test_change_calculation_structure_rejects_project_root_as_selector(
        self, temp_project: Path, daemon: QVDaemon
    ):
        """Test that change_calculation_structure rejects project_root as structure selector."""
        calculations = QVService.list_calculations_data(temp_project)
        assert len(calculations) > 0
        calculation_slug = calculations[0]["slug"]
        
        # Try to pass project_root as new_structure (should fail)
        project_root_str = str(temp_project.resolve())
        response = daemon.handle_request(RPCRequest(
            id="test",
            type="change_calculation_structure",
            payload={
                "project_root": project_root_str,
                "calculation": calculation_slug,
                "new_structure": project_root_str,  # Wrong: passing project_root as selector
                "update_steps": True,
            },
        ))
        
        # Should fail with a clear error message
        assert not response.ok, "Should reject project_root as structure selector"
        assert "project root path" in response.error.get("message", "").lower() or \
               "invalid structure selector" in response.error.get("message", "").lower(), \
            f"Error message should mention invalid selector. Got: {response.error}"
