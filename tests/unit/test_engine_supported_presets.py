"""
Tests for Engine.supported_presets property.

Verifies that each engine correctly declares which preset dimensions it supports.
This is the SSOT for engine capability declaration.
"""

import pytest

from quantumvitas.engine.qe_engine import QeEngine
from quantumvitas.engine.pyscf_engine import PySCFEngine
from quantumvitas.engine.orca_engine import ORCAEngine
from quantumvitas.engine.base import Engine, EngineConfig


def test_qe_engine_supported_presets():
    """Test that QE engine declares PW preset dimensions."""
    engine = QeEngine()
    
    presets = engine.supported_presets
    
    assert isinstance(presets, list)
    assert "precision" in presets
    assert "magnetism" in presets
    assert "occupations_scheme" in presets
    assert "convergence" in presets
    assert len(presets) == 4
    
    # QE should NOT support QC presets
    assert "qc_precision" not in presets


def test_pyscf_engine_supported_presets():
    """Test that PySCF engine declares QC preset dimensions."""
    engine = PySCFEngine()
    
    presets = engine.supported_presets
    
    assert isinstance(presets, list)
    assert "qc_precision" in presets
    assert len(presets) == 1
    
    # PySCF should NOT support PW presets
    assert "precision" not in presets
    assert "magnetism" not in presets


def test_orca_engine_supported_presets():
    """Test that ORCA engine declares QC preset dimensions."""
    # Use defer_binary_resolution=True for capability queries (binary not required)
    engine = ORCAEngine(defer_binary_resolution=True)
    
    presets = engine.supported_presets
    
    assert isinstance(presets, list)
    assert "qc_precision" in presets
    assert len(presets) == 1
    
    # ORCA should NOT support PW presets
    assert "precision" not in presets
    assert "magnetism" not in presets


def test_engine_base_class_has_abstract_property():
    """Test that Engine base class defines supported_presets as abstract."""
    # Create a concrete engine that doesn't implement supported_presets
    class IncompleteEngine(Engine):
        def run_step(self, step, working_dir):
            pass
    
    # Accessing supported_presets should raise NotImplementedError
    engine = IncompleteEngine(EngineConfig(name="test"))
    with pytest.raises(NotImplementedError):
        _ = engine.supported_presets


def test_all_engines_implement_supported_presets():
    """Test that all concrete engine classes implement supported_presets."""
    engines = [
        QeEngine(),
        PySCFEngine(),
        ORCAEngine(defer_binary_resolution=True),  # Binary not required for capability queries
    ]
    
    for engine in engines:
        presets = engine.supported_presets
        assert isinstance(presets, list)
        assert all(isinstance(p, str) for p in presets)
        assert len(presets) > 0  # Each engine must support at least one preset


def test_supported_presets_are_immutable():
    """Test that supported_presets returns a list (may be mutable, but values should be stable)."""
    engine = QeEngine()
    presets1 = engine.supported_presets
    presets2 = engine.supported_presets
    
    # Should return same values (even if different list instances)
    assert presets1 == presets2
    assert set(presets1) == set(presets2)

