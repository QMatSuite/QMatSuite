"""
Unit tests for QE executable detection and path resolution.
"""

import pytest
import platform
import tempfile
from pathlib import Path
import os
import stat

from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig


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
        
        config = EngineConfig(name="qe", executable_path=bin_dir)
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
        
        config = EngineConfig(name="qe", executable_path=qe_root)
        engine = QuantumEspressoEngine(config)
        
        exe_path = engine.find_executable("pw.x")
        assert exe_path is not None
        assert exe_path.exists()
        assert exe_path.parent == bin_dir
    
    def test_executable_not_found(self, tmp_path):
        """Test error when executable is not found."""
        config = EngineConfig(name="qe", executable_path=tmp_path)
        engine = QuantumEspressoEngine(config)
        
        exe_path = engine.find_executable("pw.x")
        assert exe_path is None
    
    def test_get_executable_path_raises_error(self, tmp_path):
        """Test that get_executable_path raises FileNotFoundError when not found."""
        config = EngineConfig(name="qe", executable_path=tmp_path)
        engine = QuantumEspressoEngine(config)
        
        with pytest.raises(FileNotFoundError) as exc_info:
            engine.get_executable_path("pw.x")
        
        assert "not found" in str(exc_info.value).lower()
        assert "pw" in str(exc_info.value)
    
    def test_detect_executable(self, temp_qe_dir):
        """Test detect_executable method."""
        qe_root, bin_dir = temp_qe_dir
        
        config = EngineConfig(name="qe", executable_path=bin_dir)
        engine = QuantumEspressoEngine(config)
        
        assert engine.detect_executable("pw.x") is True
        assert engine.detect_executable("ph.x") is True
        assert engine.detect_executable("nonexistent.x") is False
    
    def test_platform_specific_executable_names(self, temp_qe_dir):
        """Test that correct executable name is used for each platform."""
        qe_root, bin_dir = temp_qe_dir
        
        config = EngineConfig(name="qe", executable_path=bin_dir)
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
        
        config = EngineConfig(name="qe", executable_path=bin_dir)
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
        config = EngineConfig(name="qe", executable_path=tmp_path)
        engine = QuantumEspressoEngine(config)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.in', delete=False) as f:
            input_file = Path(f.name)
            input_file.write_text("&control\n/\n")
        
        try:
            with pytest.raises(FileNotFoundError):
                engine.build_command("scf", input_file, Path("."))
        finally:
            input_file.unlink()
    
    def test_executable_caching(self, temp_qe_dir):
        """Test that found executables are cached."""
        qe_root, bin_dir = temp_qe_dir
        
        config = EngineConfig(name="qe", executable_path=bin_dir)
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
        # Create two directories with executables
        dir1 = tmp_path / "qe1" / "bin"
        dir2 = tmp_path / "qe2" / "bin"
        dir1.mkdir(parents=True)
        dir2.mkdir(parents=True)
        
        system = platform.system()
        exe_name = "pw.exe" if system == "Windows" else "pw.x"
        
        # Put executable in dir2
        exe_path = dir2 / exe_name
        exe_path.write_text("mock")
        if system != "Windows":
            exe_path.chmod(stat.S_IRWXU)
        
        config = EngineConfig(name="qe", executable_path=dir1)
        engine = QuantumEspressoEngine(config)
        
        # Search in both directories
        found = engine.find_executable("pw.x", search_paths=[dir1, dir2])
        
        assert found is not None
        assert found == exe_path

