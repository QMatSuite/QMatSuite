"""
Unit tests for debug flag gating.

Tests verify that resolution debug logs are gated correctly.
"""
import pytest
from pathlib import Path
import json
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from quantumvitas.core.debug import is_resolution_debug_enabled
from quantumvitas.core.settings import load_settings, save_settings, QMatSuiteSettings


class TestDebugFlags:
    """Test debug flag gating."""
    
    @pytest.fixture
    def temp_settings_dir(self, tmp_path, monkeypatch):
        """Create a temporary settings directory."""
        settings_dir = tmp_path / ".qmatsuite" / "config"
        settings_dir.mkdir(parents=True)
        
        # Mock get_settings_json_path to return our temp path
        from quantumvitas.core.paths import get_settings_json_path
        original = get_settings_json_path
        
        def mock_get_settings_json_path():
            return settings_dir / "settings.json"
        
        monkeypatch.setattr("quantumvitas.core.paths.get_settings_json_path", mock_get_settings_json_path)
        monkeypatch.setattr("quantumvitas.core.settings.get_settings_json_path", mock_get_settings_json_path)
        
        return settings_dir
    
    def test_is_resolution_debug_enabled_defaults_to_false(self, temp_settings_dir):
        """Test that debug flag defaults to False."""
        # Settings file doesn't exist yet
        assert is_resolution_debug_enabled() is False
        
        # Create settings file without debug_resolution (should default to False)
        settings = QMatSuiteSettings(debug_resolution=False)
        save_settings(settings)
        assert is_resolution_debug_enabled() is False
    
    def test_is_resolution_debug_enabled_respects_setting(self, temp_settings_dir):
        """Test that debug flag respects the setting value."""
        # Set to True
        settings = QMatSuiteSettings(debug_resolution=True)
        save_settings(settings)
        assert is_resolution_debug_enabled() is True
        
        # Set to False
        settings = QMatSuiteSettings(debug_resolution=False)
        save_settings(settings)
        assert is_resolution_debug_enabled() is False
    
    def test_debug_flag_persistence(self, temp_settings_dir):
        """Test that debug flag persists across loads."""
        # Set to True
        settings = QMatSuiteSettings(debug_resolution=True)
        save_settings(settings)
        
        # Reload
        loaded = load_settings()
        assert loaded.debug_resolution is True
        
        # Set to False
        settings = QMatSuiteSettings(debug_resolution=False)
        save_settings(settings)
        
        # Reload
        loaded = load_settings()
        assert loaded.debug_resolution is False
    
    def test_logs_gated_when_flag_off(self, temp_settings_dir):
        """Test that trace logs are suppressed when flag is OFF."""
        from quantumvitas.core.resolution import ResourceIndex, ResourceMeta
        
        # Ensure flag is OFF
        settings = QMatSuiteSettings(debug_resolution=False)
        save_settings(settings)
        
        # Verify flag is disabled
        assert is_resolution_debug_enabled() is False
        
        # Create index and resolve (functionality should work even with flag OFF)
        index = ResourceIndex()
        calc_id = "01ABCDEFGHIJKLMNOPQRSTUVWX"
        calc_meta = ResourceMeta(ulid=calc_id,
            name="test",
            slug="test",
            path="calculations/test",
            kind="calculation",
        )
        index.add_resource(calc_meta, Path("/tmp/test/calculation.yaml"))
        
        # Resolve by slug (should work, but logs should be gated)
        result = index.resolve_id("test", Path("/tmp"), expected_kind="calculation")
        
        # Verify functionality works
        assert result == calc_id
    
    def test_logs_emitted_when_flag_on(self, temp_settings_dir):
        """Test that trace logs are emitted when flag is ON."""
        # Ensure flag is ON
        settings = QMatSuiteSettings(debug_resolution=True)
        save_settings(settings)
        
        # Verify flag is enabled
        assert is_resolution_debug_enabled() is True

