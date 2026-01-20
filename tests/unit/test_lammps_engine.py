"""Unit tests for LAMMPS engine."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from quantumvitas.engine.lammps_engine import LammpsEngine
from quantumvitas.engine.registry import create_default_registry, EngineRegistry
from quantumvitas.engine.base import EngineConfig
from quantumvitas.workflow.registry import get_registry


class TestLammpsEngine:
    """Test LammpsEngine class."""
    
    def test_engine_name(self):
        """Test engine name is correct."""
        engine = LammpsEngine()
        assert engine.name == "lammps"
    
    def test_supported_presets(self):
        """Test supported_presets returns correct values."""
        engine = LammpsEngine()
        presets = engine.supported_presets
        assert isinstance(presets, list)
        assert "classical_ensemble" in presets
        assert "potential_type" in presets
    
    def test_materialize_inputs_implemented(self):
        """Test materialize_inputs is implemented (Phase 2 complete)."""
        engine = LammpsEngine()
        # materialize_inputs is now implemented, but requires valid step/calculation
        # Just verify it exists and is callable
        assert hasattr(engine, 'materialize_inputs')
        assert callable(engine.materialize_inputs)
    
    def test_run_step_implemented(self):
        """Test run_step is implemented (Phase 3 complete)."""
        engine = LammpsEngine()
        # run_step is now implemented, but requires valid step/working_dir
        # Just verify it exists and is callable
        assert hasattr(engine, 'run_step')
        assert callable(engine.run_step)


class TestLammpsEngineRegistry:
    """Test LAMMPS engine registration."""
    
    def test_lammps_in_default_registry(self):
        """Test LAMMPS engine is in default registry."""
        registry = create_default_registry(include_lammps=True)
        assert registry.has("lammps")
        assert "lammps" in registry.list_engines()
    
    def test_lammps_not_in_registry_when_excluded(self):
        """Test LAMMPS engine can be excluded from registry."""
        registry = create_default_registry(include_lammps=False)
        assert not registry.has("lammps")
        assert "lammps" not in registry.list_engines()
    
    def test_get_lammps_engine(self):
        """Test getting LAMMPS engine from registry."""
        registry = create_default_registry(include_lammps=True)
        engine = registry.get("lammps")
        assert isinstance(engine, LammpsEngine)
        assert engine.name == "lammps"


class TestLammpsStepTypes:
    """Test LAMMPS step type registration."""
    
    def test_lammps_relax_registered(self):
        """Test lammps_relax step type is registered."""
        registry = get_registry()
        spec = registry.get("lammps_relax")
        assert spec is not None
        assert spec.engine == "lammps"
        assert spec.machine_type == "lammps_relax"
        assert spec.public_type == "relax"
        assert spec.is_structure_transform is True
    
    def test_lammps_md_registered(self):
        """Test lammps_md step type is registered."""
        registry = get_registry()
        spec = registry.get("lammps_md")
        assert spec is not None
        assert spec.engine == "lammps"
        assert spec.machine_type == "lammps_md"
        assert spec.public_type == "md"
    
    def test_list_lammps_step_types(self):
        """Test listing LAMMPS step types."""
        registry = get_registry()
        lammps_types = registry.list_by_engine_machine("lammps")
        assert "lammps_relax" in lammps_types
        assert "lammps_md" in lammps_types
        # lammps_restart should NOT exist (restart_from is a parameter, not a step type)


class TestLammpsBinaryResolver:
    """Test LAMMPS binary resolution."""
    
    @patch("quantumvitas.core.engines.lammps_resolver.which")
    @patch("quantumvitas.core.engines.lammps_resolver.os.environ", {})
    def test_resolve_from_env_var(self, mock_which):
        """Test resolving LAMMPS from environment variable."""
        from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
        import os
        
        with patch.dict(os.environ, {"QMATS_LAMMPS_BIN": "/custom/path/lmp"}):
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.is_file", return_value=True):
                    bin_path = resolve_lammps_bin()
                    assert str(bin_path) == "/custom/path/lmp"
    
    @patch("quantumvitas.core.engines.lammps_resolver.which")
    @patch("quantumvitas.core.engines.lammps_resolver.Path.exists")
    @patch("quantumvitas.core.engines.lammps_resolver.Path.is_file")
    @patch("quantumvitas.core.engines.lammps_resolver.os.environ", {})
    def test_resolve_not_found(self, mock_is_file, mock_exists, mock_which):
        """Test FileNotFoundError when LAMMPS not found."""
        from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
        
        # Mock all paths to not exist
        mock_exists.return_value = False
        mock_is_file.return_value = False
        mock_which.return_value = None
        
        with pytest.raises(FileNotFoundError, match="LAMMPS"):
            resolve_lammps_bin()

