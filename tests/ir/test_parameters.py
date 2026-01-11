"""
Tests for IR parameter registry.

Tests that IR registry is complete, valid, and contains all required parameters.
"""

import pytest

from quantumvitas.ir.parameters import (
    IR_REGISTRY,
    IRParameter,
    validate_ir_registry,
    get_ir_parameter,
    list_ir_parameters,
)


class TestIRRegistry:
    """Test IR parameter registry."""
    
    def test_registry_not_empty(self):
        """Registry must not be empty."""
        assert len(IR_REGISTRY) > 0, "IR_REGISTRY is empty"
    
    def test_registry_validation(self):
        """Registry validation should pass."""
        validate_ir_registry()  # Should not raise
    
    def test_all_expected_parameters_present(self):
        """All 18 expected IR parameters should be present."""
        expected_keys = {
            # Magnetism dimension (3)
            "nspin", "noncolin", "lspinorb",
            # OccupationsScheme dimension (3)
            "occupations", "smearing", "degauss",
            # Precision dimension (4)
            "ecutwfc", "ecutrho", "conv_thr", "K_POINTS",
            # Convergence dimension (5)
            "mixing_beta", "electron_maxstep", "mixing_mode", "mixing_ndim", "diagonalization",
            # Low-hanging additions (3)
            "nbnd", "nosym", "noinv",
        }
        
        actual_keys = set(IR_REGISTRY.keys())
        missing = expected_keys - actual_keys
        extra = actual_keys - expected_keys
        
        assert not missing, f"Missing IR parameters: {missing}"
        assert not extra, f"Unexpected IR parameters: {extra}"
        assert len(IR_REGISTRY) == 18, f"Expected 18 IR parameters, got {len(IR_REGISTRY)}"
    
    def test_parameter_structure(self):
        """Each parameter must have required fields."""
        for ir_key, param in IR_REGISTRY.items():
            assert isinstance(param, IRParameter), f"Parameter '{ir_key}' is not IRParameter"
            assert param.ir_key == ir_key, f"Parameter key mismatch: {ir_key} != {param.ir_key}"
            assert param.physical_meaning, f"Parameter '{ir_key}' missing physical_meaning"
            assert param.dimension, f"Parameter '{ir_key}' missing dimension"
            assert param.type, f"Parameter '{ir_key}' missing type"
            assert param.comment, f"Parameter '{ir_key}' missing comment"
            
            # Validate dimension
            assert param.dimension in (
                "Energy", "Length", "Dimensionless", "Bool", "Enum", "Integer", "Struct"
            ), f"Parameter '{ir_key}' has invalid dimension: {param.dimension}"
            
            # Validate type
            assert param.type in ("float", "int", "bool", "str", "dict"), (
                f"Parameter '{ir_key}' has invalid type: {param.type}"
            )
            
            # Validate units for dimensional parameters
            if param.dimension in ("Energy", "Length"):
                assert param.ir_base_unit, (
                    f"Parameter '{ir_key}' has dimension '{param.dimension}' but missing ir_base_unit"
                )
                if param.dimension == "Energy":
                    assert param.ir_base_unit == "Ry", (
                        f"Parameter '{ir_key}' Energy dimension should have ir_base_unit='Ry', "
                        f"got '{param.ir_base_unit}'"
                    )
                elif param.dimension == "Length":
                    assert param.ir_base_unit == "Bohr", (
                        f"Parameter '{ir_key}' Length dimension should have ir_base_unit='Bohr', "
                        f"got '{param.ir_base_unit}'"
                    )
    
    def test_no_engine_references_in_ir_definitions(self):
        """IR definitions must not contain engine-specific references."""
        forbidden_terms = ["qe_key", "qe_section", "qe_", "pw.x", "Quantum ESPRESSO"]
        
        for ir_key, param in IR_REGISTRY.items():
            physical_meaning_lower = param.physical_meaning.lower()
            comment_lower = param.comment.lower()
            
            for term in forbidden_terms:
                assert term.lower() not in physical_meaning_lower, (
                    f"Parameter '{ir_key}' physical_meaning contains engine reference: '{term}'"
                )
                assert term.lower() not in comment_lower, (
                    f"Parameter '{ir_key}' comment contains engine reference: '{term}'"
                )
    
    def test_get_ir_parameter(self):
        """Test getting IR parameter by key."""
        param = get_ir_parameter("ecutwfc")
        assert param is not None
        assert param.ir_key == "ecutwfc"
        assert param.dimension == "Energy"
        
        # Non-existent parameter
        param = get_ir_parameter("nonexistent")
        assert param is None
    
    def test_list_ir_parameters(self):
        """Test listing all IR parameter keys."""
        keys = list_ir_parameters()
        assert len(keys) == len(IR_REGISTRY)
        assert "ecutwfc" in keys
        assert "nspin" in keys
        assert sorted(keys) == keys  # Should be sorted

