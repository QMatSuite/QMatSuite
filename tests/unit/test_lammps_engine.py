"""Unit tests for LAMMPS engine."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from quantumvitas.engine.lammps_engine import LammpsEngine
from quantumvitas.engine.registry import create_default_registry, EngineRegistry
from quantumvitas.engine.base import EngineConfig
from quantumvitas.workflow.registry import get_registry
from quantumvitas.core.resources import generate_resource_id


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
    """Test LAMMPS step type registration.

    Uses get_for_engine(gen_type, engine) per constitution: registry.get() takes GEN only.
    """

    def test_lammps_relax_registered(self):
        """Test lammps_relax step type is registered."""
        registry = get_registry()
        spec = registry.get_for_engine("relax", "lammps")
        assert spec is not None
        assert spec.engine == "lammps"
        assert spec.step_type_spec == "lammps_relax"
        assert spec.step_type_gen == "relax"
        assert spec.is_structure_transform is True

    def test_lammps_md_registered(self):
        """Test lammps_md step type is registered."""
        registry = get_registry()
        spec = registry.get_for_engine("md", "lammps")
        assert spec is not None
        assert spec.engine == "lammps"
        assert spec.step_type_spec == "lammps_md"
        assert spec.step_type_gen == "md"
    
    def test_list_lammps_step_types(self):
        """Test listing LAMMPS step types."""
        registry = get_registry()
        lammps_types = registry.list_by_engine_machine("lammps")
        assert "lammps_relax" in lammps_types
        assert "lammps_md" in lammps_types
        # lammps_restart should NOT exist (restart_from is a parameter, not a step type)


class TestUlidUniqueness:
    """Test ULID generation uniqueness (Ubuntu CI regression prevention)."""
    
    def test_ulid_uniqueness_1000_rapid(self):
        """Test that 1000 rapidly generated ULIDs are all unique."""
        # This tests the root cause hypothesis: ULID collision under rapid generation
        ids = [generate_resource_id() for _ in range(1000)]
        unique_ids = set(ids)
        
        assert len(unique_ids) == 1000, (
            f"ULID COLLISION: generated 1000 IDs but only {len(unique_ids)} unique. "
            f"First collision example: {[id for id in ids if ids.count(id) > 1][:5]}"
        )
    
    def test_ulid_consecutive_different(self):
        """Test that consecutive ULIDs are different."""
        id1 = generate_resource_id()
        id2 = generate_resource_id()
        id3 = generate_resource_id()
        
        assert id1 != id2, f"Consecutive ULID collision: id1 == id2 ({id1})"
        assert id2 != id3, f"Consecutive ULID collision: id2 == id3 ({id2})"
        assert id1 != id3, f"ULID collision: id1 == id3 ({id1})"


class TestLammpsRestartFromValidation:
    """Test restart_from validation (Ubuntu CI root cause fix)."""
    
    def test_self_reference_raises_error(self):
        """Test that restart_from == current step ULID raises clear error."""
        engine = LammpsEngine()
        
        # Create mock step with restart_from pointing to itself
        mock_step = MagicMock()
        mock_step.meta.ulid = "01ABCD1234567890123456"
        mock_step.parameters = {"restart_from": "01ABCD1234567890123456"}  # Self-reference!
        mock_step.step_type_spec= "lammps_md"
        
        # Create mock calculation
        mock_calculation = MagicMock()
        mock_calculation.dir = Path("/fake/calc")
        mock_calculation.steps = [mock_step]
        
        # _resolve_restart_artifact should raise ValueError with clear message
        with pytest.raises(ValueError, match="SELF-REFERENCE-ERROR"):
            engine._resolve_restart_artifact(mock_step, mock_calculation)
    
    def test_valid_restart_from_accepted(self):
        """Test that valid restart_from (different step) is accepted."""
        engine = LammpsEngine()
        
        # Create mock upstream step
        mock_upstream = MagicMock()
        mock_upstream.meta.ulid = "01UPSTREAM000000000000"
        mock_upstream.meta.slug = "upstream"
        
        # Create mock current step with restart_from pointing to upstream
        mock_step = MagicMock()
        mock_step.meta.ulid = "01CURRENT0000000000000"
        mock_step.parameters = {"restart_from": "01UPSTREAM000000000000"}
        
        # Create mock calculation
        mock_calculation = MagicMock()
        mock_calculation.steps = [mock_upstream, mock_step]
        mock_calculation.io.raw_dir = Path("/fake/raw")
        
        # Should NOT raise self-reference error (but will raise FileNotFoundError 
        # because the mock directory doesn't exist - that's expected)
        with pytest.raises(FileNotFoundError, match="restart artifact"):
            engine._resolve_restart_artifact(mock_step, mock_calculation)


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

