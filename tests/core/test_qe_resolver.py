"""
Unit tests for QE resolver (two-state model).
"""

import pytest
import tempfile
import shutil
import time
from pathlib import Path
import json

from quantumvitas.core.engines.qe_resolver import (
    resolve_qe_bin_dir,
    find_internal_qe_bin_dir,
    validate_qe_bin_dir,
)
from quantumvitas.core.settings import QMatSuiteSettings, QEConfig, save_settings, load_settings
from quantumvitas.core.paths import get_repo_root, home_qe_engines_dir


def test_validate_qe_bin_dir_valid(tmp_path):
    """Test validation of valid QE bin directory."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "pw.x").touch()
    (bin_dir / "pw.x").chmod(0o755)
    
    # Should not raise
    validate_qe_bin_dir(bin_dir)


def test_validate_qe_bin_dir_missing(tmp_path):
    """Test validation fails for missing directory."""
    bin_dir = tmp_path / "nonexistent" / "bin"
    
    with pytest.raises(RuntimeError, match="does not exist"):
        validate_qe_bin_dir(bin_dir)


def test_validate_qe_bin_dir_no_pw(tmp_path):
    """Test validation fails when pw.x is missing."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    
    with pytest.raises(RuntimeError, match="missing pw executable"):
        validate_qe_bin_dir(bin_dir)


def test_find_internal_qe_bin_dir_empty():
    """Test finding internal QE when none exists."""
    # Use a temporary repo root for this test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Mock the engines directory to be empty
        engines_dir = Path(tmpdir) / ".qmatsuite" / "engines" / "qe"
        engines_dir.mkdir(parents=True, exist_ok=True)
        
        # Temporarily patch home_qe_engines_dir
        from quantumvitas.core.engines import qe_resolver
        from quantumvitas.core.paths import home_qe_engines_dir
        original_func = qe_resolver.home_qe_engines_dir
        qe_resolver.home_qe_engines_dir = lambda: engines_dir
        
        try:
            result = find_internal_qe_bin_dir()
            assert result is None
        finally:
            qe_resolver.home_qe_engines_dir = original_func


def test_find_internal_qe_bin_dir_selection():
    """Test internal QE selection rule (mtime + lexicographic tie-break)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engines_base = Path(tmpdir) / ".qmatsuite" / "engines" / "qe"
        engines_base.mkdir(parents=True, exist_ok=True)
        
        # Create two engine directories
        engine1_dir = engines_base / "engine-old"
        engine1_bin = engine1_dir / "bin"
        engine1_bin.mkdir(parents=True)
        (engine1_bin / "pw.x").touch()
        
        # Wait a bit to ensure different mtime
        time.sleep(0.1)
        
        engine2_dir = engines_base / "engine-new"
        engine2_bin = engine2_dir / "bin"
        engine2_bin.mkdir(parents=True)
        (engine2_bin / "pw.x").touch()
        
        # Temporarily patch home_qe_engines_dir
        from quantumvitas.core.engines import qe_resolver
        original_func = qe_resolver.home_qe_engines_dir
        qe_resolver.home_qe_engines_dir = lambda: engines_base
        
        try:
            result = find_internal_qe_bin_dir()
            # Should select the newer one (engine-new)
            assert result is not None
            assert result == engine2_bin
        finally:
            qe_resolver.home_qe_engines_dir = original_func


def test_find_internal_qe_bin_dir_with_meta_json():
    """Test internal QE selection uses META.json created_at if available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        engines_base = Path(tmpdir) / ".qmatsuite" / "engines" / "qe"
        engines_base.mkdir(parents=True, exist_ok=True)
        
        # Create two engines
        engine1_dir = engines_base / "engine-a"
        engine1_bin = engine1_dir / "bin"
        engine1_bin.mkdir(parents=True)
        (engine1_bin / "pw.x").touch()
        
        engine2_dir = engines_base / "engine-b"
        engine2_bin = engine2_dir / "bin"
        engine2_bin.mkdir(parents=True)
        (engine2_bin / "pw.x").touch()
        
        # Create META.json for engine-a with recent created_at
        from datetime import datetime, timedelta
        meta_a = {
            "created_at": (datetime.now() + timedelta(days=1)).isoformat(),
        }
        with open(engine1_dir / "META.json", "w") as f:
            json.dump(meta_a, f)
        
        # Temporarily patch home_qe_engines_dir
        from quantumvitas.core.engines import qe_resolver
        original_func = qe_resolver.home_qe_engines_dir
        qe_resolver.home_qe_engines_dir = lambda: engines_base
        
        try:
            result = find_internal_qe_bin_dir()
            # Should select engine-a because META.json has future timestamp
            assert result is not None
            assert result == engine1_bin
        finally:
            qe_resolver.home_qe_engines_dir = original_func


def test_resolve_qe_bin_dir_external(tmp_path):
    """Test resolution with external QE (settings.qe.bin_dir set)."""
    bin_dir = tmp_path / "external" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "pw.x").touch()
    
    settings = QMatSuiteSettings(
        qe=QEConfig(bin_dir=str(bin_dir.resolve()))
    )
    
    result = resolve_qe_bin_dir(settings)
    assert result == bin_dir.resolve()


def test_resolve_qe_bin_dir_external_invalid(tmp_path):
    """Test resolution fails when external QE bin_dir is invalid."""
    bin_dir = tmp_path / "invalid" / "bin"
    bin_dir.mkdir(parents=True)
    # No pw.x
    
    settings = QMatSuiteSettings(
        qe=QEConfig(bin_dir=str(bin_dir.resolve()))
    )
    
    with pytest.raises(RuntimeError, match="invalid or missing pw executable"):
        resolve_qe_bin_dir(settings)


def test_resolve_qe_bin_dir_internal(tmp_path):
    """Test resolution with internal QE (settings.qe.bin_dir is null)."""
    engines_base = tmp_path / ".qmatsuite" / "engines" / "qe"
    engines_base.mkdir(parents=True, exist_ok=True)
    
    engine_dir = engines_base / "test-engine"
    bin_dir = engine_dir / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "pw.x").touch()
    
    settings = QMatSuiteSettings(qe=QEConfig(bin_dir=None))
    
    # Temporarily patch home_qe_engines_dir
    from quantumvitas.core.engines import qe_resolver
    original_func = qe_resolver.home_qe_engines_dir
    qe_resolver.home_qe_engines_dir = lambda: engines_base
    
    try:
        result = resolve_qe_bin_dir(settings)
        assert result == bin_dir.resolve()
    finally:
        qe_resolver.home_qe_engines_dir = original_func


def test_resolve_qe_bin_dir_no_qe():
    """Test resolution fails when no QE is available."""
    settings = QMatSuiteSettings(qe=QEConfig(bin_dir=None))
    
    # Temporarily patch to return empty engines dir
    from quantumvitas.core.engines import qe_resolver
    original_func = qe_resolver.home_qe_engines_dir
    
    with tempfile.TemporaryDirectory() as tmpdir:
        empty_engines = Path(tmpdir) / "engines" / "qe"
        empty_engines.mkdir(parents=True, exist_ok=True)
        qe_resolver.home_qe_engines_dir = lambda: empty_engines
        
        try:
            with pytest.raises(RuntimeError, match="No internal QE found"):
                resolve_qe_bin_dir(settings)
        finally:
            qe_resolver.home_qe_engines_dir = original_func


def test_bin_dir_contract_no_double_bin(tmp_path):
    """
    Test that bin_dir contract is respected: bin_dir is always the bin directory.
    
    This test ensures that when bin_dir is already a bin directory (as per two-state
    resolver contract), we never create "bin/bin" paths in search locations or error messages.
    """
    from quantumvitas.core.engines.qe import QuantumEspressoEngine
    from quantumvitas.core.engines.base import EngineConfig
    
    # Create a QE installation structure: qe_root/bin/
    qe_root = tmp_path / "qe-7.5"
    bin_dir = qe_root / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "pw.x").touch()
    (bin_dir / "pw.x").chmod(0o755)
    (bin_dir / "bands.x").touch()
    (bin_dir / "bands.x").chmod(0o755)
    
    # Create engine with qe_home pointing to QE root (normal case)
    # The engine will set qe_bin_dir = qe_root/bin (which is already a bin directory)
    config = EngineConfig(name="qe", qe_home=qe_root)
    engine = QuantumEspressoEngine(config)
    
    # Verify qe_bin_dir is set to the bin directory (not QE root)
    assert engine.qe_bin_dir == bin_dir or engine.qe_bin_dir == bin_dir.resolve()
    
    # Test that find_executable works and doesn't create bin/bin paths
    exe_path = engine.find_executable("pw.x")
    assert exe_path is not None
    assert exe_path == bin_dir / "pw.x" or exe_path == (bin_dir / "pw.x").resolve()
    
    # Test that get_executable_path error message doesn't contain "bin/bin"
    # Try to find a non-existent executable to trigger error message
    try:
        engine.get_executable_path("nonexistent.x")
        pytest.fail("Should have raised FileNotFoundError")
    except FileNotFoundError as e:
        error_msg = str(e)
        # Verify error message doesn't contain "bin/bin"
        assert "/bin/bin" not in error_msg, f"Error message contains '/bin/bin': {error_msg}"
        # Verify it does contain the correct bin directory (or at least doesn't have double bin)
        assert str(bin_dir) in error_msg or str(bin_dir.resolve()) in error_msg, \
            f"Error message should contain bin_dir: {error_msg}"
    
    # Test that find_executable with bands.x works (common executable that was missing)
    bands_path = engine.find_executable("bands.x")
    assert bands_path is not None
    assert bands_path == bin_dir / "bands.x" or bands_path == (bin_dir / "bands.x").resolve()

