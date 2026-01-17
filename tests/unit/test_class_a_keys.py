"""
Tests for Class A key registry.

Class A keys are strict-typed parameters that participate in IR/Preset system.
"""

import pytest

from quantumvitas.ir.backends.qe.mapping import (
    is_class_a_key,
    get_class_a_type,
    IR_TO_QE_MAPPING,
    CLASS_A_TYPES,
)


class TestClassAKeyRegistry:
    """Test Class A key identification."""
    
    def test_ir_mapped_keys_are_class_a(self):
        """All keys in IR_TO_QE_MAPPING should be Class A."""
        for ir_key in IR_TO_QE_MAPPING:
            _, section, key = IR_TO_QE_MAPPING[ir_key]
            assert is_class_a_key(section, key), \
                f"IR-mapped key {section}.{key} should be Class A"
    
    def test_magnetism_keys_are_class_a(self):
        """Magnetism dimension keys are Class A."""
        assert is_class_a_key("SYSTEM", "nspin")
        assert is_class_a_key("SYSTEM", "noncolin")
        assert is_class_a_key("SYSTEM", "lspinorb")
    
    def test_precision_keys_are_class_a(self):
        """Precision dimension keys are Class A."""
        assert is_class_a_key("SYSTEM", "ecutwfc")
        assert is_class_a_key("SYSTEM", "ecutrho")
        assert is_class_a_key("ELECTRONS", "conv_thr")
        assert is_class_a_key("SYSTEM", "degauss")
    
    def test_convergence_keys_are_class_a(self):
        """Convergence dimension keys are Class A."""
        assert is_class_a_key("ELECTRONS", "mixing_beta")
        assert is_class_a_key("ELECTRONS", "electron_maxstep")
        assert is_class_a_key("ELECTRONS", "mixing_mode")
        assert is_class_a_key("ELECTRONS", "mixing_ndim")
        assert is_class_a_key("ELECTRONS", "diagonalization")
    
    def test_other_ir_keys_are_class_a(self):
        """Other IR-mapped keys are Class A."""
        assert is_class_a_key("SYSTEM", "nbnd")
        assert is_class_a_key("SYSTEM", "nosym")
        assert is_class_a_key("SYSTEM", "noinv")
    
    def test_non_ir_keys_are_class_b(self):
        """Keys not in IR mapping are Class B."""
        assert not is_class_a_key("SYSTEM", "unknown_param")
        assert not is_class_a_key("ELECTRONS", "unknown_param")
        assert not is_class_a_key("CONTROL", "calculation")
    
    def test_case_insensitive_section(self):
        """Section name matching is case-insensitive."""
        assert is_class_a_key("system", "nspin")
        assert is_class_a_key("System", "nspin")
        assert is_class_a_key("SYSTEM", "nspin")
    
    def test_case_insensitive_key(self):
        """Key name matching is case-insensitive."""
        assert is_class_a_key("SYSTEM", "NSPIN")
        assert is_class_a_key("SYSTEM", "Nspin")
        assert is_class_a_key("SYSTEM", "nspin")


class TestClassATypeRegistry:
    """Test Class A type information."""
    
    def test_class_a_type_returns_correct_type(self):
        """get_class_a_type returns correct type for Class A keys."""
        assert get_class_a_type("SYSTEM", "nspin") == "int"
        assert get_class_a_type("SYSTEM", "noncolin") == "bool"
        assert get_class_a_type("SYSTEM", "lspinorb") == "bool"
        assert get_class_a_type("SYSTEM", "ecutwfc") == "float"
        assert get_class_a_type("SYSTEM", "ecutrho") == "float"
        assert get_class_a_type("ELECTRONS", "conv_thr") == "float"
        assert get_class_a_type("ELECTRONS", "mixing_beta") == "float"
        assert get_class_a_type("ELECTRONS", "electron_maxstep") == "int"
        assert get_class_a_type("ELECTRONS", "mixing_mode") == "str"
        assert get_class_a_type("SYSTEM", "occupations") == "str"
        assert get_class_a_type("SYSTEM", "smearing") == "str"
    
    def test_class_b_keys_return_none(self):
        """get_class_a_type returns None for Class B keys."""
        assert get_class_a_type("SYSTEM", "unknown_param") is None
        assert get_class_a_type("CONTROL", "calculation") is None
    
    def test_case_insensitive_type_lookup(self):
        """Type lookup is case-insensitive."""
        assert get_class_a_type("system", "nspin") == "int"
        assert get_class_a_type("SYSTEM", "NSPIN") == "int"
        assert get_class_a_type("System", "Nspin") == "int"
    
    def test_all_class_a_types_defined(self):
        """All Class A keys should have type information."""
        for (section, key), expected_type in CLASS_A_TYPES.items():
            assert expected_type in ("bool", "int", "float", "str"), \
                f"Invalid type '{expected_type}' for {section}.{key}"
            assert is_class_a_key(section, key), \
                f"Type registry key {section}.{key} should be Class A"

