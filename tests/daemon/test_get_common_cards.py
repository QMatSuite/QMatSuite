"""
Tests for get_common_cards RPC handler.

Tests verify:
- Handler resolves calculation selector to ULID at boundary
- Service method uses calculation_ulid (not calculation_selector)
- No TypeError from old keyword argument
"""
import pytest
from pathlib import Path
import yaml

from quantumvitas.core.resources import generate_resource_id
from quantumvitas.core.resolution import build_resource_index
from quantumvitas.api import QVService


@pytest.mark.unit
class TestGetCommonCards:
    """Test get_common_cards RPC handler."""
    
    def test_get_common_cards_resolves_selector_to_ulid(self, tmp_path):
        """get_common_cards resolves calculation selector to ULID at boundary."""
        from quantumvitas.daemon.server import QVDaemon
        
        daemon = QVDaemon()
        
        # Create minimal project with calculation
        project_root = tmp_path / "project"
        project_root.mkdir()
        calc_ulid = generate_resource_id()
        (project_root / "project.qv.yml").write_text(
            yaml.safe_dump({
                "project": {"name": "Test", "id": generate_resource_id()},
                "calculations": [{"calculation_id": calc_ulid}]
            }, sort_keys=False)
        )
        
        calc_dir = project_root / "calculations" / "test_calc"
        calc_dir.mkdir(parents=True)
        (calc_dir / "calculation.yaml").write_text(
            yaml.safe_dump({
                "meta": {"id": calc_ulid, "name": "test-calc", "slug": "test-calc"},
                "id": "test-calc",
            }, sort_keys=False)
        )
        
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir()
        step_ulid = generate_resource_id()
        (steps_dir / "scf.step.yaml").write_text(
            yaml.safe_dump({
                "meta": {"id": step_ulid, "name": "scf", "slug": "scf"},
                "step_type": "scf",
                "parameters": {},
                "cards": {"K_POINTS": {"mode": "automatic", "nk1": 2, "nk2": 2, "nk3": 2}},
            }, sort_keys=False)
        )
        
        # Update calculation.yaml with step
        calc_data = yaml.safe_load((calc_dir / "calculation.yaml").read_text())
        calc_data["steps"] = [{"step_id": step_ulid, "type": "scf"}]
        (calc_dir / "calculation.yaml").write_text(yaml.safe_dump(calc_data, sort_keys=False))
        
        # Build index
        build_resource_index(project_root)
        
        # Call with slug selector (should resolve to ULID)
        response = daemon._handle_get_common_cards({
            "project_root": str(project_root),
            "calculation": "test-calc",  # slug, not ULID
            "step": step_ulid,  # ULID
        })
        
        # Should succeed (no TypeError from calculation_selector keyword)
        assert "k_points" in response or "error" not in response
    
    def test_get_common_cards_service_uses_ulid(self, tmp_path):
        """QVService.get_common_cards uses calculation_ulid parameter."""
        # Create minimal project with calculation
        project_root = tmp_path / "project"
        project_root.mkdir()
        calc_ulid = generate_resource_id()
        (project_root / "project.qv.yml").write_text(
            yaml.safe_dump({
                "project": {"name": "Test", "id": generate_resource_id()},
                "calculations": [{"calculation_id": calc_ulid}]
            }, sort_keys=False)
        )
        
        calc_dir = project_root / "calculations" / "test_calc"
        calc_dir.mkdir(parents=True)
        (calc_dir / "calculation.yaml").write_text(
            yaml.safe_dump({
                "meta": {"id": calc_ulid, "name": "test-calc", "slug": "test-calc"},
                "id": "test-calc",
            }, sort_keys=False)
        )
        
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir()
        step_ulid = generate_resource_id()
        (steps_dir / "scf.step.yaml").write_text(
            yaml.safe_dump({
                "meta": {"id": step_ulid, "name": "scf", "slug": "scf"},
                "step_type": "scf",
                "parameters": {},
                "cards": {"K_POINTS": {"mode": "automatic", "nk1": 2, "nk2": 2, "nk3": 2}},
            }, sort_keys=False)
        )
        
        # Update calculation.yaml with step
        calc_data = yaml.safe_load((calc_dir / "calculation.yaml").read_text())
        calc_data["steps"] = [{"step_id": step_ulid, "type": "scf"}]
        (calc_dir / "calculation.yaml").write_text(yaml.safe_dump(calc_data, sort_keys=False))
        
        # Build index
        index = build_resource_index(project_root)
        
        # Call service method directly with ULID (should not raise TypeError)
        result = QVService.get_common_cards(
            project_root=project_root,
            calculation_ulid=calc_ulid,  # ULID, not selector
            step_selector=step_ulid,
            index=index,
        )
        
        # Should return result (may be empty if no common cards, but no error)
        assert isinstance(result, dict)

