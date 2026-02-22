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

from qmatsuite.core.resources import generate_resource_id
from qmatsuite.core.resolution import build_resource_index
from qmatsuite.api import QMSService


@pytest.mark.unit
class TestGetCommonCards:
    """Test get_common_cards RPC handler."""
    
    def test_get_common_cards_resolves_selector_to_ulid(self, tmp_path):
        """get_common_cards resolves calculation selector to ULID at boundary."""
        from qmatsuite.daemon.server import QMSDaemon
        
        daemon = QMSDaemon()
        
        # Create minimal project with calculation
        project_root = tmp_path / "project"
        project_root.mkdir()
        calc_ulid = generate_resource_id()
        (project_root / "project.qms.yml").write_text(
            yaml.safe_dump({
                "project": {"name": "Test", "ulid": generate_resource_id()},
                "calculations": [{
                    "meta": {
                        "ulid": calc_ulid,
                        "name": "test-calc",
                        "slug": "test-calc",
                        "path": "calculations/test_calc",
                        "kind": "calculation",
                    }
                }]
            }, sort_keys=False)
        )

        calc_dir = project_root / "calculations" / "test_calc"
        calc_dir.mkdir(parents=True)
        (calc_dir / "calculation.yaml").write_text(
            yaml.safe_dump({
                "meta": {"ulid": calc_ulid, "name": "test-calc", "slug": "test-calc"},
                "ulid": "test-calc",
            }, sort_keys=False)
        )
        
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir()
        step_ulid = generate_resource_id()
        (steps_dir / "scf.step.yaml").write_text(
            yaml.safe_dump({
                "meta": {"ulid": step_ulid, "name": "scf", "slug": "scf"},
                "step_type_gen": "scf",
                "parameters": {},
                "cards": {"K_POINTS": {"mode": "automatic", "nk1": 2, "nk2": 2, "nk3": 2}},
            }, sort_keys=False)
        )
        
        # Update calculation.yaml with step
        calc_data = yaml.safe_load((calc_dir / "calculation.yaml").read_text())
        calc_data["steps"] = [{"step_ulid": step_ulid, "step_type_gen": "scf"}]
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
        """QMSService.get_common_cards uses calculation_ulid parameter."""
        # Create minimal project with calculation
        project_root = tmp_path / "project"
        project_root.mkdir()
        calc_ulid = generate_resource_id()
        (project_root / "project.qms.yml").write_text(
            yaml.safe_dump({
                "project": {"name": "Test", "ulid": generate_resource_id()},
                "calculations": [{
                    "meta": {
                        "ulid": calc_ulid,
                        "name": "test-calc",
                        "slug": "test-calc",
                        "path": "calculations/test_calc",
                        "kind": "calculation",
                    }
                }]
            }, sort_keys=False)
        )

        calc_dir = project_root / "calculations" / "test_calc"
        calc_dir.mkdir(parents=True)
        (calc_dir / "calculation.yaml").write_text(
            yaml.safe_dump({
                "meta": {"ulid": calc_ulid, "name": "test-calc", "slug": "test-calc"},
                "ulid": "test-calc",
            }, sort_keys=False)
        )
        
        steps_dir = calc_dir / "steps"
        steps_dir.mkdir()
        step_ulid = generate_resource_id()
        (steps_dir / "scf.step.yaml").write_text(
            yaml.safe_dump({
                "meta": {"ulid": step_ulid, "name": "scf", "slug": "scf"},
                "step_type_gen": "scf",
                "parameters": {},
                "cards": {"K_POINTS": {"mode": "automatic", "nk1": 2, "nk2": 2, "nk3": 2}},
            }, sort_keys=False)
        )
        
        # Update calculation.yaml with step
        calc_data = yaml.safe_load((calc_dir / "calculation.yaml").read_text())
        calc_data["steps"] = [{"step_ulid": step_ulid, "step_type_gen": "scf"}]
        (calc_dir / "calculation.yaml").write_text(yaml.safe_dump(calc_data, sort_keys=False))
        
        # Build index
        index = build_resource_index(project_root)

        # Call service method via domain accessor (QMSService)
        from qmatsuite.api import QMSService
        svc = QMSService(project_root)
        result = svc.calculation.get_common_cards(
            calc_selector=calc_ulid,  # ULID as selector
            step_selector=step_ulid,
        )

        # Should return result (may be empty if no common cards, but no error)
        assert isinstance(result, dict)

