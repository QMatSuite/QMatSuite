"""
Integration tests for QE executable detection with real-world scenarios.
"""

import pytest
import platform
import tempfile
from pathlib import Path
import os
import stat

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig


class TestRealWorldScenarios:
    """Test real-world QE installation scenarios."""
    
    def test_qe_installation_in_home(self, tmp_path, monkeypatch):
        """Test QE installation in home directory structure."""
        # Simulate $HOME/src/q-e-qe-7.5/bin structure
        home = tmp_path / "home" / "user"
        qe_install = home / "src" / "q-e-qe-7.5" / "bin"
        qe_install.mkdir(parents=True)
        
        system = platform.system()
        exe_name = "pw.exe" if system == "Windows" else "pw.x"
        exe_path = qe_install / exe_name
        exe_path.write_text("mock")
        if system != "Windows":
            exe_path.chmod(stat.S_IRWXU)
        
        # Test with full path to bin directory
        config = EngineConfig(name="qe", executable_path=qe_install)
        engine = QuantumEspressoEngine(config)
        
        found = engine.find_executable("pw.x")
        assert found is not None
        assert found == exe_path
        
        # Test with path to QE root (should find bin subdirectory)
        config2 = EngineConfig(name="qe", executable_path=qe_install.parent)
        engine2 = QuantumEspressoEngine(config2)
        
        found2 = engine2.find_executable("pw.x")
        assert found2 is not None
        assert found2 == exe_path
    
    def test_multiple_qe_installations(self, tmp_path):
        """Test behavior with multiple QE installations."""
        # Create two QE installations
        qe1_bin = tmp_path / "qe-7.0" / "bin"
        qe2_bin = tmp_path / "qe-7.5" / "bin"
        qe1_bin.mkdir(parents=True)
        qe2_bin.mkdir(parents=True)
        
        system = platform.system()
        exe_name = "pw.exe" if system == "Windows" else "pw.x"
        
        # Put executable in qe2
        exe2 = qe2_bin / exe_name
        exe2.write_text("mock")
        if system != "Windows":
            exe2.chmod(stat.S_IRWXU)
        
        # Configure to use qe2
        config = EngineConfig(name="qe", executable_path=qe2_bin)
        engine = QuantumEspressoEngine(config)
        
        found = engine.find_executable("pw.x")
        assert found == exe2
        
        # Should not find in qe1
        config2 = EngineConfig(name="qe", executable_path=qe1_bin)
        engine2 = QuantumEspressoEngine(config2)
        
        found2 = engine2.find_executable("pw.x")
        assert found2 is None
    
    def test_error_message_helpfulness(self, tmp_path):
        """Test that error messages are helpful."""
        config = EngineConfig(name="qe", executable_path=tmp_path / "nonexistent")
        engine = QuantumEspressoEngine(config)
        
        with pytest.raises(FileNotFoundError) as exc_info:
            engine.get_executable_path("pw.x")
        
        error_msg = str(exc_info.value)
        assert "pw" in error_msg.lower()
        assert "not found" in error_msg.lower()
        # Should mention search locations
        assert "PATH" in error_msg or "path" in error_msg.lower()

