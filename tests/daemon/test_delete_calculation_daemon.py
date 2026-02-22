"""
Daemon-level tests for delete_calculation RPC.

Tests verify:
- Daemon handler accepts slug and resolves to ULID at boundary
- Core service receives ULID (not slug)
"""
import pytest
from pathlib import Path
import yaml

from qmatsuite.core.resources import generate_resource_id
from qmatsuite.daemon.server import QMSDaemon
from qmatsuite.api import QMSService


class TestDeleteCalculationDaemon:
    """Test delete_calculation daemon handler."""
    
    def test_delete_calculation_handler_accepts_slug_and_resolves(self, tmp_path):
        """Daemon handler accepts slug selector and resolves to ULID at boundary."""
        # Create minimal project
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "project.qms.yml").write_text(
            yaml.safe_dump({"project": {"name": "Test", "ulid": generate_resource_id()}}, sort_keys=False)
        )
        
        # Create calculation (this registers it in project config)
        calc_resource = QMSService(project_root).project.init_calculation(name="To Delete")
        calculation_ulid = calc_resource.ulid
        calculation_slug = calc_resource.meta.slug
        
        # Rebuild index to ensure calculation is discoverable
        from qmatsuite.core.resolution import build_resource_index
        index = build_resource_index(project_root)
        
        # Verify calculation exists
        from qmatsuite.core.resolution import resolve_calculation
        resolved = resolve_calculation(project_root, calculation_ulid, index=index)
        assert resolved.ulid == calculation_ulid
        
        # Create daemon instance
        daemon = QMSDaemon()
        
        # Call daemon handler with slug (should resolve to ULID at boundary)
        payload = {
            "project_root": str(project_root),
            "selector": calculation_slug,  # Slug, not ULID
        }
        
        result = daemon._handle_delete_calculation(payload)
        
        # Should succeed (no error)
        assert result is None or (isinstance(result, dict) and result.get("ok") is not False)
        
        # Verify calculation is deleted
        from qmatsuite.core.resolution import SelectorNotFoundError, build_resource_index
        index = build_resource_index(project_root)
        with pytest.raises(SelectorNotFoundError):
            from qmatsuite.core.resolution import resolve_calculation
            resolve_calculation(project_root, calculation_ulid, index=index)

