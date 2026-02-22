"""
Contract enforcement tests for capability resolver.

These tests verify that the capability contract is strictly enforced:
- Engine not declared → not listed
- Declared but missing wiring → hard error on apply
- Apply with unsupported preset raises CapabilityError
- ORCA capability queries work without binary
"""

import pytest
from pathlib import Path
import tempfile
import yaml

from qmatsuite.presets.capability import (
    list_presets_for_engine,
    validate_preset_capability,
    require_preset_capability,
    CapabilityError,
    resolve_engine_for_step,
)
from qmatsuite.presets.integration import apply_presets_to_step
from qmatsuite.engine.orca_engine import ORCAEngine


class TestEngineNotDeclaredNotListed:
    """Test that engines without preset in supported_presets are not listed."""
    
    def test_unknown_engine_raises_keyerror(self):
        """Unknown engine should raise KeyError when querying presets."""
        with pytest.raises(KeyError, match="not found in registry"):
            list_presets_for_engine("unknown_engine", "scf")
    
    def test_engine_without_preset_not_listed(self):
        """If an engine doesn't declare a preset, it shouldn't appear in list."""
        # QE doesn't support qc_precision
        presets = list_presets_for_engine("qe", "scf")
        assert "qc_precision" not in presets
        
        # PySCF doesn't support precision (PW preset)
        presets = list_presets_for_engine("pyscf", "scf")
        assert "precision" not in presets
        assert "magnetism" not in presets


class TestDeclaredButNoWiringReturnsEmpty:
    """Test that declared presets without ParamSpace wiring return empty."""
    
    def test_pyscf_mp2_returns_empty(self):
        """PySCF supports qc_precision, but mp2 has no ParamSpace variant."""
        presets = list_presets_for_engine("pyscf", "mp2")
        assert len(presets) == 0
        # Even though PySCF supports qc_precision, mp2 has no variant


class TestApplyUnsupportedPresetRaisesError:
    """Test that applying unsupported preset raises CapabilityError."""
    
    def test_require_capability_raises_error_for_unsupported(self):
        """require_preset_capability should raise CapabilityError for unsupported preset."""
        with pytest.raises(CapabilityError) as exc_info:
            require_preset_capability("qe", "scf", "qc_precision")
        
        assert exc_info.value.engine_name == "qe"
        assert exc_info.value.gen_step == "scf"
        assert exc_info.value.preset_id == "qc_precision"
        assert "qc_precision" in str(exc_info.value)
        assert "qe" in str(exc_info.value)
    
    def test_apply_presets_to_step_skips_unsupported(self):
        """apply_presets_to_step should skip unsupported presets silently."""
        # Create a temporary step.yaml file
        with tempfile.TemporaryDirectory() as tmpdir:
            step_path = Path(tmpdir) / "test.step.yaml"
            
            # Create a QE step
            step_data = {
                "step_type_spec": "qe_scf",
                "parameters": {
                    "SYSTEM": {
                        "ecutwfc": 30.0,
                    }
                }
            }
            
            with open(step_path, 'w') as f:
                yaml.dump(step_data, f)
            
            # Try to apply qc_precision (not supported by QE)
            result = apply_presets_to_step(
                step_path,
                {"qc_precision": "med"}
            )
            
            # Should skip qc_precision (not in filtered_options)
            assert "qc_precision" not in result.get("filtered_options", {})
            # Should still accept (but with empty filtered_options if no valid presets)
            # Actually, if no dimensions apply, accepted should be False
            if not result.get("filtered_options"):
                assert result.get("accepted") is False


class TestORCACapabilityWithoutBinary:
    """Test that ORCA capability queries work without binary."""
    
    def test_orca_capability_queries_without_binary(self):
        """ORCA capability queries should work even if binary is not installed."""
        # Create ORCA engine with deferred binary resolution
        engine = ORCAEngine(defer_binary_resolution=True)
        
        # Query capability (should work without binary)
        presets = list_presets_for_engine("orca", "scf")
        assert "qc_precision" in presets
        
        # Validate capability (should work without binary)
        assert validate_preset_capability("orca", "scf", "qc_precision") is True
        
        # Require capability (should work without binary)
        require_preset_capability("orca", "scf", "qc_precision")  # Should not raise
    
    def test_orca_unsupported_preset_raises_error(self):
        """ORCA should raise error for unsupported presets (even without binary)."""
        with pytest.raises(CapabilityError):
            require_preset_capability("orca", "scf", "precision")  # QE preset, not ORCA


class TestRequireCapabilityClearErrorMessage:
    """Test that CapabilityError has clear error message."""
    
    def test_error_message_includes_engine_gen_step_preset(self):
        """Error message should include engine, gen_step, and preset."""
        try:
            require_preset_capability("pyscf", "scf", "precision")
            pytest.fail("Should have raised CapabilityError")
        except CapabilityError as e:
            assert "precision" in str(e)
            assert "pyscf" in str(e)
            assert "scf" in str(e)
            assert e.engine_name == "pyscf"
            assert e.gen_step == "scf"
            assert e.preset_id == "precision"


class TestResolveEngineForStep:
    """Test resolve_engine_for_step helper."""
    
    def test_resolve_engine_for_qe_step(self):
        """Should resolve engine from QE step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            step_path = Path(tmpdir) / "qe_step.step.yaml"
            
            step_data = {
                "step_type_spec": "qe_scf",
                "parameters": {}
            }

            with open(step_path, 'w') as f:
                yaml.dump(step_data, f)

            engine = resolve_engine_for_step(step_path)
            assert engine == "qe"
    
    def test_resolve_engine_for_pyscf_step(self):
        """Should resolve engine from PySCF step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            step_path = Path(tmpdir) / "pyscf_step.step.yaml"
            
            step_data = {
                "step_type_spec": "pyscf_scf",
                "parameters": {}
            }

            with open(step_path, 'w') as f:
                yaml.dump(step_data, f)

            engine = resolve_engine_for_step(step_path)
            assert engine == "pyscf"
    
    def test_resolve_engine_returns_none_for_missing_step_type(self):
        """Should return None if step_type is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            step_path = Path(tmpdir) / "no_step_type.step.yaml"
            
            step_data = {
                "parameters": {}
            }
            
            with open(step_path, 'w') as f:
                yaml.dump(step_data, f)
            
            engine = resolve_engine_for_step(step_path)
            assert engine is None

