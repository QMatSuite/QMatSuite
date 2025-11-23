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
        # Simulate $HOME/src/q-e-qe-7.5 structure
        home = tmp_path / "home" / "user"
        qe_home = home / "src" / "q-e-qe-7.5"
        qe_bin = qe_home / "bin"
        qe_bin.mkdir(parents=True)
        
        system = platform.system()
        exe_name = "pw.exe" if system == "Windows" else "pw.x"
        exe_path = qe_bin / exe_name
        exe_path.write_text("mock")
        if system != "Windows":
            exe_path.chmod(stat.S_IRWXU)
        
        # Test with path to QE home (should find bin/pw.x)
        config = EngineConfig(name="qe", qe_home=qe_home)
        engine = QuantumEspressoEngine(config)
        
        found = engine.find_executable("pw.x")
        assert found is not None
        assert found == exe_path
        
        # Test again with same config
        config2 = EngineConfig(name="qe", qe_home=qe_home)
        engine2 = QuantumEspressoEngine(config2)
        
        found2 = engine2.find_executable("pw.x")
        assert found2 is not None
        assert found2 == exe_path
    
    def test_multiple_qe_installations(self, tmp_path):
        """Test behavior with multiple QE installations."""
        # Create two QE installations
        qe1_home = tmp_path / "qe-7.0"
        qe2_home = tmp_path / "qe-7.5"
        qe1_bin = qe1_home / "bin"
        qe2_bin = qe2_home / "bin"
        qe1_bin.mkdir(parents=True)
        qe2_bin.mkdir(parents=True)
        
        system = platform.system()
        exe_name = "pw.exe" if system == "Windows" else "pw.x"
        
        # Put executable in both qe1 and qe2 (needed for QEInstallation validation)
        exe1 = qe1_bin / exe_name
        exe2 = qe2_bin / exe_name
        exe1.write_text("mock")
        exe2.write_text("mock")
        if system != "Windows":
            exe1.chmod(stat.S_IRWXU)
            exe2.chmod(stat.S_IRWXU)
        
        # Configure to use qe2
        config = EngineConfig(name="qe", qe_home=qe2_home)
        engine = QuantumEspressoEngine(config)
        
        found = engine.find_executable("pw.x")
        assert found == exe2
        
        # Should find in qe1 as well
        config2 = EngineConfig(name="qe", qe_home=qe1_home)
        engine2 = QuantumEspressoEngine(config2)
        
        found2 = engine2.find_executable("pw.x")
        assert found2 == exe1
    
    def test_error_message_helpfulness(self, tmp_path):
        """Test that error messages are helpful."""
        # Create a directory that looks like QE home but without bin/pw.x
        fake_qe = tmp_path / "nonexistent"
        fake_qe.mkdir()
        config = EngineConfig(name="qe", qe_home=fake_qe)
        # This should raise ValueError during initialization
        with pytest.raises(ValueError) as exc_info:
            engine = QuantumEspressoEngine(config)
        
        error_msg = str(exc_info.value)
        assert "Invalid QE home directory" in error_msg or "bin/pw.x" in error_msg

