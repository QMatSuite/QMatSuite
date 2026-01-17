"""
Constitution-grade capability resolver invariant tests.

Verifies capability resolver SSOT and edge cases, including ORCA binary-optional behavior.
"""

import pytest

from quantumvitas.presets.capability import (
    list_presets_for_engine,
    validate_preset_capability,
    require_preset_capability,
    CapabilityError,
)
from quantumvitas.engine.registry import create_default_registry


class TestCapabilityResolverInvariants:
    """Constitution-grade capability tests."""
    
    def test_engine_not_in_registry_raises_keyerror(self):
        """Test that unknown engine raises KeyError."""
        with pytest.raises(KeyError, match="not found in registry"):
            list_presets_for_engine("unknown_engine", "scf")
    
    def test_preset_not_in_supported_returns_empty(self):
        """Test that preset not in supported_presets returns empty."""
        # PySCF does not support "magnetism" preset
        presets = list_presets_for_engine("pyscf", "scf")
        assert "magnetism" not in presets, \
            "PySCF should not support magnetism preset"
    
    def test_preset_in_supported_but_not_applicable_returns_empty(self):
        """Test that preset in supported but not applicable returns empty."""
        # PySCF supports qc_precision, but qc_precision does NOT apply to "td" step
        presets = list_presets_for_engine("pyscf", "td")
        assert "qc_precision" not in presets, \
            "qc_precision should not apply to 'td' step type"
    
    def test_intersection_logic_correct(self):
        """Test that intersection logic works correctly."""
        # QE supports precision, and precision applies to scf
        # So qe + scf should return precision
        presets = list_presets_for_engine("qe", "scf")
        assert "precision" in presets, \
            "QE should support precision preset on scf step"
        
        # PySCF supports qc_precision, but qc_precision does NOT apply to mp2
        # So pyscf + mp2 should return empty (or not include qc_precision)
        presets = list_presets_for_engine("pyscf", "mp2")
        assert "qc_precision" not in presets, \
            "qc_precision should not apply to mp2 step type"
    
    def test_orca_in_registry_without_binary(self):
        """Test that ORCA is in registry even without binary."""
        registry = create_default_registry()
        assert registry.has("orca"), \
            "ORCA should be in registry even if binary is not available"
        
        # Should be able to query capability without binary
        orca_engine = registry.get("orca")
        assert orca_engine is not None, \
            "ORCA engine should be retrievable from registry"
    
    def test_orca_supported_presets_without_binary(self):
        """Test that ORCA supported_presets query works without binary."""
        registry = create_default_registry()
        orca_engine = registry.get("orca")
        
        # Should be able to query supported_presets without binary
        supported = orca_engine.supported_presets
        assert isinstance(supported, list), \
            "supported_presets should return a list"
        assert "qc_precision" in supported, \
            "ORCA should declare qc_precision in supported_presets"
    
    def test_validate_preset_capability_returns_false_for_unsupported(self):
        """Test that validate_preset_capability returns False for unsupported preset."""
        # PySCF does not support magnetism
        result = validate_preset_capability("pyscf", "scf", "magnetism")
        assert result is False, \
            "validate_preset_capability should return False for unsupported preset"
    
    def test_require_preset_capability_raises_for_unsupported(self):
        """Test that require_preset_capability raises CapabilityError for unsupported preset."""
        # PySCF does not support magnetism
        with pytest.raises(CapabilityError, match="not available"):
            require_preset_capability("pyscf", "scf", "magnetism")
    
    def test_qe_supports_precision_on_scf(self):
        """Test that QE supports precision preset on scf step."""
        presets = list_presets_for_engine("qe", "scf")
        assert "precision" in presets, \
            "QE should support precision preset on scf step"
    
    def test_pyscf_supports_qc_precision_on_scf(self):
        """Test that PySCF supports qc_precision preset on scf step."""
        presets = list_presets_for_engine("pyscf", "scf")
        assert "qc_precision" in presets, \
            "PySCF should support qc_precision preset on scf step"
    
    def test_orca_supports_qc_precision_on_scf(self):
        """Test that ORCA supports qc_precision preset on scf step (without binary)."""
        presets = list_presets_for_engine("orca", "scf")
        assert "qc_precision" in presets, \
            "ORCA should support qc_precision preset on scf step (even without binary)"

