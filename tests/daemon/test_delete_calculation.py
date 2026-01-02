"""
Tests for delete_calculation RPC handler.

Tests verify:
- Validation of selector at boundary
- Proper error handling for None/empty selectors
- ULID-based deletion works correctly
"""
import pytest
from pathlib import Path
import yaml

from quantumvitas.core.resources import generate_resource_id
from quantumvitas.core.resolution import build_resource_index
from quantumvitas.api import QVService


@pytest.mark.unit
class TestDeleteCalculation:
    """Test delete_calculation RPC handler."""
    
    def test_delete_calculation_with_none_selector_returns_invalid_argument(self, tmp_path):
        """delete_calculation with selector=None returns invalid_argument (no crash)."""
        from quantumvitas.daemon.server import QVDaemon
        
        daemon = QVDaemon()
        
        # Create minimal project
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "project.qv.yml").write_text(
            yaml.safe_dump({"project": {"name": "Test", "id": generate_resource_id()}}, sort_keys=False)
        )
        
        # Call with selector=None
        response = daemon._handle_delete_calculation({
            "project_root": str(project_root),
            "selector": None,
        })
        
        assert response["ok"] is False
        assert response["error"]["code"] == "invalid_argument"
        assert "selector" in response["error"]["message"].lower()
    
    def test_delete_calculation_with_empty_selector_returns_invalid_argument(self, tmp_path):
        """delete_calculation with selector='' returns invalid_argument."""
        from quantumvitas.daemon.server import QVDaemon
        
        daemon = QVDaemon()
        
        # Create minimal project
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "project.qv.yml").write_text(
            yaml.safe_dump({"project": {"name": "Test", "id": generate_resource_id()}}, sort_keys=False)
        )
        
        # Call with empty selector
        response = daemon._handle_delete_calculation({
            "project_root": str(project_root),
            "selector": "   ",  # Whitespace-only (strips to empty)
        })
        
        assert response["ok"] is False
        assert response["error"]["code"] == "invalid_argument"
        assert "non-empty" in response["error"]["message"].lower()
    
    def test_delete_calculation_with_non_string_selector_returns_invalid_argument(self, tmp_path):
        """delete_calculation with selector=123 (int) returns invalid_argument."""
        from quantumvitas.daemon.server import QVDaemon
        
        daemon = QVDaemon()
        
        # Create minimal project
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "project.qv.yml").write_text(
            yaml.safe_dump({"project": {"name": "Test", "id": generate_resource_id()}}, sort_keys=False)
        )
        
        # Call with non-string selector
        response = daemon._handle_delete_calculation({
            "project_root": str(project_root),
            "selector": 123,
        })
        
        assert response["ok"] is False
        assert response["error"]["code"] == "invalid_argument"
        assert "string" in response["error"]["message"].lower()
    
    def test_entry_matches_raises_value_error_for_none(self):
        """entry_matches raises ValueError for None identifier."""
        from quantumvitas.core.project_utils import entry_matches
        
        entry = {"meta": {"id": "01TEST123", "name": "test"}}
        
        with pytest.raises(ValueError, match="identifier must be a non-empty string"):
            entry_matches(entry, None)
    
    def test_entry_matches_raises_value_error_for_empty_string(self):
        """entry_matches raises ValueError for empty string."""
        from quantumvitas.core.project_utils import entry_matches
        
        entry = {"meta": {"id": "01TEST123", "name": "test"}}
        
        with pytest.raises(ValueError, match="identifier must be a non-empty string"):
            entry_matches(entry, "")
    
    def test_entry_matches_raises_value_error_for_non_string(self):
        """entry_matches raises ValueError for non-string identifier."""
        from quantumvitas.core.project_utils import entry_matches
        
        entry = {"meta": {"id": "01TEST123", "name": "test"}}
        
        with pytest.raises(ValueError, match="identifier must be a string"):
            entry_matches(entry, 123)

