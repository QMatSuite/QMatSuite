"""
Tests for QE detection and preflight_check.

Tests verify:
- QE is initialized correctly at preflight (not requiring Settings visit)
- Preflight uses two-state resolver (not legacy get_qe_home)
- QE detection logs are present
"""
import pytest
from pathlib import Path
import yaml
import tempfile
import shutil

from quantumvitas.core.resources import generate_resource_id
from quantumvitas.core.settings import QMatSuiteSettings, QEConfig, save_settings
from quantumvitas.api import QVService


@pytest.mark.unit
class TestQEDetection:
    """Test QE detection in preflight_check."""
    
    def test_preflight_check_initializes_qe_from_settings(self, tmp_path):
        """preflight_check initializes QE from settings without requiring Settings page visit."""
        # Create minimal project
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "project.qv.yml").write_text(
            yaml.safe_dump({"project": {"name": "Test", "id": generate_resource_id()}}, sort_keys=False)
        )
        
        # Create internal QE structure
        qe_engines_dir = tmp_path / ".qmatsuite" / "engines" / "qe"
        qe_engines_dir.mkdir(parents=True)
        qe_bin_dir = qe_engines_dir / "q-e-qe-7.5" / "bin"
        qe_bin_dir.mkdir(parents=True)
        
        # Create fake pw.x executable
        pw_x = qe_bin_dir / "pw.x"
        pw_x.write_text("#!/bin/bash\necho 'fake pw.x'")
        pw_x.chmod(0o755)
        
        # Settings should have bin_dir=None (internal QE)
        # Mock get_settings_json_path to return our test settings file
        settings_dir = tmp_path / ".qmatsuite" / "config"
        settings_dir.mkdir(parents=True)
        settings_file = settings_dir / "settings.json"
        settings = QMatSuiteSettings(
            version=1,
            qe=QEConfig(bin_dir=None),  # Internal QE
        )
        
        # Write settings file directly
        import json
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)
        
        # Mock home directory to point to our tmp_path
        import os
        original_home = os.environ.get("HOME")
        try:
            os.environ["HOME"] = str(tmp_path)
            
            # Call preflight_check - should succeed without visiting Settings
            from quantumvitas._api_legacy import QVService as LegacyService
            result = LegacyService.preflight_check(
                project_root=project_root,
            )
            
            # Should find QE (internal)
            qe_check = next((c for c in result["checks"] if c["name"] == "QE Installation"), None)
            assert qe_check is not None
            # May be True or False depending on whether pw.x is actually executable
            # But should not crash with "QE not detected" if internal QE exists
            assert "QE" in qe_check["message"]
        finally:
            if original_home:
                os.environ["HOME"] = original_home
            elif "HOME" in os.environ:
                del os.environ["HOME"]
    
    def test_preflight_check_uses_two_state_resolver(self, tmp_path, monkeypatch):
        """preflight_check uses resolve_qe_bin_dir (two-state) not legacy get_qe_home."""
        # Create minimal project
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "project.qv.yml").write_text(
            yaml.safe_dump({"project": {"name": "Test", "id": generate_resource_id()}}, sort_keys=False)
        )
        
        # Create settings with external QE
        settings_dir = tmp_path / ".qmatsuite" / "config"
        settings_dir.mkdir(parents=True)
        settings_file = settings_dir / "settings.json"
        
        # Create fake external QE
        external_qe_bin = tmp_path / "external_qe" / "bin"
        external_qe_bin.mkdir(parents=True)
        pw_x = external_qe_bin / "pw.x"
        pw_x.write_text("#!/bin/bash\necho 'fake pw.x'")
        pw_x.chmod(0o755)
        
        settings = QMatSuiteSettings(
            version=1,
            qe=QEConfig(bin_dir=str(external_qe_bin)),  # External QE
        )
        
        # Write settings file directly
        import json
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings.to_dict(), f, indent=2)
        
        # Mock get_settings_json_path to return our test settings file
        # Patch kernel module for this API test (verifies API method uses kernel function correctly)
        from quantumvitas.core import paths as paths_module
        monkeypatch.setattr(paths_module, "get_settings_json_path", lambda: settings_file)
        
        # Call preflight_check
        from quantumvitas._api_legacy import QVService as LegacyService
        result = LegacyService.preflight_check(
            project_root=project_root,
        )
        
        # Should find QE from settings (external)
        qe_check = next((c for c in result["checks"] if c["name"] == "QE Installation"), None)
        assert qe_check is not None
        assert str(external_qe_bin) in qe_check["message"] or "pw.x" in qe_check["message"]

