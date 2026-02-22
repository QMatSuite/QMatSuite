"""
Unit tests for QE executable detection and path resolution.
"""

import pytest
import platform
import tempfile
from pathlib import Path
import os
import stat

from qmatsuite.core.engines.qe import QuantumEspressoEngine
from qmatsuite.core.engines.base import EngineConfig


class TestQEExecutableDetection:
    """Test QE executable detection across platforms."""
    
    @pytest.fixture
    def temp_qe_dir(self, tmp_path):
        """Create a temporary QE installation directory."""
        qe_root = tmp_path / "qe-7.5"
        bin_dir = qe_root / "bin"
        bin_dir.mkdir(parents=True)
        
        # Create mock executables
        system = platform.system()
        if system == "Windows":
            (bin_dir / "pw.exe").write_text("mock")
            (bin_dir / "ph.exe").write_text("mock")
        else:
            pw_exe = bin_dir / "pw.x"
            ph_exe = bin_dir / "ph.x"
            pw_exe.write_text("mock")
            ph_exe.write_text("mock")
            # Make executable
            pw_exe.chmod(stat.S_IRWXU)
            ph_exe.chmod(stat.S_IRWXU)
        
        return qe_root, bin_dir
    
    def test_find_executable_in_bin_dir(self, temp_qe_dir):
        """Test finding executable in specified bin directory."""
        qe_root, bin_dir = temp_qe_dir
        
        config = EngineConfig(name="qe", qe_home=qe_root)
        engine = QuantumEspressoEngine(config)
        
        system = platform.system()
        exe_name = "pw.exe" if system == "Windows" else "pw.x"
        
        exe_path = engine.find_executable("pw.x")
        assert exe_path is not None
        assert exe_path.exists()
        assert exe_path.name == exe_name
    
    def test_find_executable_in_qe_root(self, temp_qe_dir):
        """Test finding executable when qe_root is provided (checks bin subdirectory)."""
        qe_root, bin_dir = temp_qe_dir
        
        config = EngineConfig(name="qe", qe_home=qe_root)
        engine = QuantumEspressoEngine(config)
        
        exe_path = engine.find_executable("pw.x")
        assert exe_path is not None
        assert exe_path.exists()
        assert exe_path.parent == bin_dir
    
    def test_executable_not_found(self, tmp_path):
        """Test error when executable is not found."""
        # Create a valid QE home structure but without the specific executable we're looking for
        qe_home = tmp_path / "qe-7.5"
        bin_dir = qe_home / "bin"
        bin_dir.mkdir(parents=True)
        
        # Create pw.x but we'll look for a different executable
        system = platform.system()
        exe_name = "pw.exe" if system == "Windows" else "pw.x"
        (bin_dir / exe_name).write_text("mock")
        if system != "Windows":
            (bin_dir / exe_name).chmod(stat.S_IRWXU)
        
        config = EngineConfig(name="qe", qe_home=qe_home)
        engine = QuantumEspressoEngine(config)
        
        # Look for an executable that doesn't exist
        exe_path = engine.find_executable("nonexistent.x")
        assert exe_path is None
    
    def test_get_executable_path_raises_error(self, tmp_path):
        """Test that get_executable_path raises FileNotFoundError when not found."""
        # Create a valid QE home structure
        qe_home = tmp_path / "qe-7.5"
        bin_dir = qe_home / "bin"
        bin_dir.mkdir(parents=True)
        
        system = platform.system()
        exe_name = "pw.exe" if system == "Windows" else "pw.x"
        (bin_dir / exe_name).write_text("mock")
        if system != "Windows":
            (bin_dir / exe_name).chmod(stat.S_IRWXU)
        
        config = EngineConfig(name="qe", qe_home=qe_home)
        engine = QuantumEspressoEngine(config)
        
        # Look for an executable that doesn't exist
        with pytest.raises(FileNotFoundError) as exc_info:
            engine.get_executable_path("nonexistent.x")
        
        assert "not found" in str(exc_info.value).lower()
        assert "nonexistent" in str(exc_info.value)
    
    def test_detect_executable(self, temp_qe_dir):
        """Test detect_executable method."""
        qe_root, bin_dir = temp_qe_dir
        
        config = EngineConfig(name="qe", qe_home=qe_root)
        engine = QuantumEspressoEngine(config)
        
        assert engine.detect_executable("pw.x") is True
        assert engine.detect_executable("ph.x") is True
        assert engine.detect_executable("nonexistent.x") is False
    
    def test_platform_specific_executable_names(self, temp_qe_dir):
        """Test that correct executable name is used for each platform."""
        qe_root, bin_dir = temp_qe_dir
        
        config = EngineConfig(name="qe", qe_home=qe_root)
        engine = QuantumEspressoEngine(config)
        
        system = platform.system()
        exe_path = engine.find_executable("pw.x")
        
        if system == "Windows":
            assert exe_path.name == "pw.exe"
        else:
            assert exe_path.name == "pw.x"
    
    def test_build_command_uses_detected_executable(self, temp_qe_dir):
        """Test that build_command uses the detected executable path."""
        qe_root, bin_dir = temp_qe_dir
        
        config = EngineConfig(name="qe", qe_home=qe_root)
        engine = QuantumEspressoEngine(config)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.in', delete=False) as f:
            input_file = Path(f.name)
            input_file.write_text("&control\n/\n")
        
        try:
            command = engine.build_command("scf", input_file, Path("."))
            
            assert len(command) > 0
            exe_path = Path(command[0])
            assert exe_path.exists()
            assert exe_path.parent == bin_dir
            
            system = platform.system()
            if system == "Windows":
                assert exe_path.name == "pw.exe"
            else:
                assert exe_path.name == "pw.x"
        finally:
            input_file.unlink()
    
    def test_build_command_raises_error_when_not_found(self, tmp_path):
        """Test that build_command raises error when executable not found."""
        # Create a valid QE home structure but we'll use a different executable
        qe_home = tmp_path / "qe-7.5"
        bin_dir = qe_home / "bin"
        bin_dir.mkdir(parents=True)
        
        # Don't create pw.x - we'll test with a different executable
        system = platform.system()
        exe_name = "ph.exe" if system == "Windows" else "ph.x"
        (bin_dir / exe_name).write_text("mock")
        if system != "Windows":
            (bin_dir / exe_name).chmod(stat.S_IRWXU)
        
        # This will fail during initialization because pw.x is required
        with pytest.raises(ValueError):
            config = EngineConfig(name="qe", qe_home=qe_home)
            engine = QuantumEspressoEngine(config)
    
    def test_executable_caching(self, temp_qe_dir):
        """Test that found executables are cached."""
        qe_root, bin_dir = temp_qe_dir
        
        config = EngineConfig(name="qe", qe_home=qe_root)
        engine = QuantumEspressoEngine(config)
        
        # First call
        exe_path1 = engine.get_executable_path("pw.x")
        
        # Second call should use cache
        exe_path2 = engine.get_executable_path("pw.x")
        
        assert exe_path1 == exe_path2
        assert "pw.x" in engine._detected_executables


class TestQEExecutableSearchPaths:
    """Test executable search path logic."""
    
    def test_search_in_multiple_locations(self, tmp_path):
        """Test searching in multiple specified locations."""
        # Create two QE installations
        qe1_home = tmp_path / "qe1"
        qe2_home = tmp_path / "qe2"
        dir1 = qe1_home / "bin"
        dir2 = qe2_home / "bin"
        dir1.mkdir(parents=True)
        dir2.mkdir(parents=True)
        
        system = platform.system()
        exe_name = "pw.exe" if system == "Windows" else "pw.x"
        
        # Put executable in both (needed for QEInstallation validation)
        exe1 = dir1 / exe_name
        exe2 = dir2 / exe_name
        exe1.write_text("mock")
        exe2.write_text("mock")
        if system != "Windows":
            exe1.chmod(stat.S_IRWXU)
            exe2.chmod(stat.S_IRWXU)
        
        # Create QE home structure
        config = EngineConfig(name="qe", qe_home=qe1_home)
        engine = QuantumEspressoEngine(config)
        
        # Search in both directories
        found = engine.find_executable("pw.x", search_paths=[dir1, dir2])
        
        assert found is not None
        # Should find in dir1 (first in search_paths)
        assert found == exe1 or found == exe2

