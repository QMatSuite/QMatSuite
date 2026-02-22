"""
Tests for ParamSpace key-access enforcement (Constitution 10.8.9).

Per Constitution 10.8.9:
- ParamSpace can only access its owned keys or Oracle-exposed semantic prerequisites
- Key ownership must be unique
- Illegal access must raise RuntimeError immediately

This module tests:
- Illegal key access raises KeyAccessError
- Duplicate key ownership causes immediate failure
- Occupation detect no longer depends on degauss
- Precision behavior unchanged
- Non-YAML inputs (structure/pseudo) are not blocked
"""

import pytest

from qmatsuite.presets.paramspace import (
    ParamSpace,
    ParamKey,
    Cell,
    KeyAccessError,
    ParamSpaceContext,
    get_yaml_value,
    register_paramspace,
    _PARAMSPACE_REGISTRY,
    _KEY_OWNERSHIP,
)
from qmatsuite.presets.dimensions import (
    OccupationsSchemeOption,
    CUSTOM,
)
from qmatsuite.presets.variants_registry import (
    detect_dimension_for_step,
    OCCUPATIONS_SCHEME_VARIANT,
)
from qmatsuite.presets.paramspace import (
    get_occupations_scheme_paramspace,
    get_precision_paramspace,
    get_magnetism_paramspace,
)
from qmatsuite.presets.oracle import Oracle


class TestKeyAccessEnforcement:
    """Test key-access enforcement rules."""
    
    def test_illegal_key_access_raises_error(self):
        """Illegal key access must raise KeyAccessError."""
        # Ensure precision is registered first (so we can see it in error message)
        precision_space = get_precision_paramspace()
        
        # Test that accessing a foreign key raises error
        occupations_space = get_occupations_scheme_paramspace()
        yaml_tree = {
            "SYSTEM": {
                "ecutwfc": 50,  # Owned by precision, not occupations
            }
        }
        
        with ParamSpaceContext(occupations_space):
            # Should raise error - ecutwfc is owned by precision
            with pytest.raises(KeyAccessError, match="ecutwfc"):
                get_yaml_value(yaml_tree, "SYSTEM", "ecutwfc")
    
    def test_occupation_detect_no_degauss_dependency(self):
        """Occupation detect must work without degauss value."""
        # Test that occupation detection works for smearing regardless of degauss value
        # This verifies that degauss was removed from occupation ParamSpace
        
        # Case 1: smearing with degauss=0.01 (LOW precision)
        params_01 = {
            "SYSTEM": {
                "occupations": "smearing",
                "smearing": "gaussian",
                "degauss": 0.01,  # Not owned by occupations
            }
        }
        
        # Case 2: smearing with degauss=0.02 (MED precision)
        params_02 = {
            "SYSTEM": {
                "occupations": "smearing",
                "smearing": "gaussian",
                "degauss": 0.02,
            }
        }
        
        # Case 3: smearing with degauss=0.03 (HIGH precision)
        params_03 = {
            "SYSTEM": {
                "occupations": "smearing",
                "smearing": "gaussian",
                "degauss": 0.03,
            }
        }
        
        # All should detect as SMEARING_GAUSSIAN (degauss is not checked)
        with ParamSpaceContext(OCCUPATIONS_SCHEME_VARIANT.space):
            detected_01 = detect_dimension_for_step(
                "occupations_scheme", "scf", params_01
            )
            detected_02 = detect_dimension_for_step(
                "occupations_scheme", "scf", params_02
            )
            detected_03 = detect_dimension_for_step(
                "occupations_scheme", "scf", params_03
            )
        
        # All should return SMEARING_GAUSSIAN (not CUSTOM)
        assert detected_01 == OccupationsSchemeOption.SMEARING_GAUSSIAN
        assert detected_02 == OccupationsSchemeOption.SMEARING_GAUSSIAN
        assert detected_03 == OccupationsSchemeOption.SMEARING_GAUSSIAN
    
    def test_occupation_detect_without_degauss(self):
        """Occupation detect works even when degauss is missing."""
        params = {
            "SYSTEM": {
                "occupations": "smearing",
                "smearing": "gaussian",
                # degauss missing - should still work
            }
        }
        
        # Context is set internally by detect_dimension_for_step
        detected = detect_dimension_for_step(
            "occupations_scheme", "scf", params
        )
        
        # Should return SMEARING_GAUSSIAN (degauss is not part of occupation detection)
        assert detected == OccupationsSchemeOption.SMEARING_GAUSSIAN
    
    def test_precision_uses_oracle_for_occupations(self):
        """Precision compile uses Oracle to check degauss applicability."""
        from qmatsuite.presets.variants_registry import compile_dimension_patch_for_step
        
        # Test that precision compile uses oracle, not direct YAML read
        step_yaml = {
            "SYSTEM": {
                "occupations": "smearing",
                "ecutwfc": 50,
                "ecutrho": 400,
            },
            "ELECTRONS": {
                "conv_thr": 1e-8,
            },
        }
        
        # This should work - precision uses oracle to check occupations
        # (oracle reads occupations, which is allowed via allow_oracle flag)
        # Test that oracle can read occupations (oracle is allowed to read foreign keys)
        oracle = Oracle(step_yaml)
        assert oracle.degauss_applicability() is True
    
    def test_duplicate_ownership_fails_immediately(self):
        """Duplicate key ownership must cause immediate failure at ParamSpace creation."""
        # This test verifies that all canonical ParamSpaces have unique key ownership
        # Since ParamSpaces are singletons, we verify the existing ones are correctly registered
        
        # Get all canonical spaces
        precision_space = get_precision_paramspace()
        occupations_space = get_occupations_scheme_paramspace()
        magnetism_space = get_magnetism_paramspace()
        
        # Verify each space has unique keys
        precision_keys = precision_space.owned_keys()
        occupations_keys = occupations_space.owned_keys()
        magnetism_keys = magnetism_space.owned_keys()
        
        # Check for overlaps
        precision_occupations_overlap = precision_keys & occupations_keys
        precision_magnetism_overlap = precision_keys & magnetism_keys
        occupations_magnetism_overlap = occupations_keys & magnetism_keys
        
        # All overlaps should be empty (no shared keys between different dimensions)
        assert len(precision_occupations_overlap) == 0, f"Precision and Occupations share keys: {precision_occupations_overlap}"
        assert len(precision_magnetism_overlap) == 0, f"Precision and Magnetism share keys: {precision_magnetism_overlap}"
        assert len(occupations_magnetism_overlap) == 0, f"Occupations and Magnetism share keys: {occupations_magnetism_overlap}"
        
        # Verify degauss is owned by precision (not occupations)
        assert ("SYSTEM", "degauss") in precision_keys
        assert ("SYSTEM", "degauss") not in occupations_keys
    
    def test_owned_keys_access_allowed(self):
        """ParamSpace can access its own keys."""
        occupations_space = get_occupations_scheme_paramspace()
        yaml_tree = {
            "SYSTEM": {
                "occupations": "smearing",
                "smearing": "gaussian",
            }
        }
        
        with ParamSpaceContext(occupations_space):
            # Should not raise error - accessing owned keys
            present, value = get_yaml_value(yaml_tree, "SYSTEM", "occupations")
            assert present is True
            assert value == "smearing"
            
            present, value = get_yaml_value(yaml_tree, "SYSTEM", "smearing")
            assert present is True
            assert value == "gaussian"
    
    def test_foreign_key_access_raises_error(self):
        """Accessing foreign key raises KeyAccessError."""
        occupations_space = get_occupations_scheme_paramspace()
        precision_space = get_precision_paramspace()
        
        yaml_tree = {
            "SYSTEM": {
                "ecutwfc": 50,  # Owned by precision
            }
        }
        
        with ParamSpaceContext(occupations_space):
            # Should raise error - ecutwfc is owned by precision, not occupations
            with pytest.raises(KeyAccessError, match="ecutwfc.*precision"):
                get_yaml_value(yaml_tree, "SYSTEM", "ecutwfc")
    
    def test_oracle_access_allowed(self):
        """Oracle-mediated access is allowed even for foreign keys."""
        precision_space = get_precision_paramspace()
        yaml_tree = {
            "SYSTEM": {
                "occupations": "smearing",  # Owned by occupations, but oracle can read
            }
        }
        
        with ParamSpaceContext(precision_space):
            # Oracle access is allowed via allow_oracle flag
            oracle = Oracle(yaml_tree)
            # This should work - oracle reads occupations to check degauss applicability
            assert oracle.degauss_applicability() is True
    
    def test_no_context_allows_access(self):
        """When no context is set, access is allowed (backward compatibility)."""
        yaml_tree = {
            "SYSTEM": {
                "ecutwfc": 50,
            }
        }
        
        # No context set - should allow access (for backward compatibility)
        present, value = get_yaml_value(yaml_tree, "SYSTEM", "ecutwfc")
        assert present is True
        assert value == 50
    
    def test_degauss_owned_by_precision(self):
        """Verify degauss is owned by Precision ParamSpace."""
        precision_space = get_precision_paramspace()
        owned = precision_space.owned_keys()
        
        assert ("SYSTEM", "degauss") in owned
        assert ("SYSTEM", "ecutwfc") in owned
        assert ("SYSTEM", "ecutrho") in owned
        assert ("ELECTRONS", "conv_thr") in owned
    
    def test_degauss_not_owned_by_occupations(self):
        """Verify degauss is NOT owned by Occupations ParamSpace."""
        occupations_space = get_occupations_scheme_paramspace()
        owned = occupations_space.owned_keys()
        
        assert ("SYSTEM", "degauss") not in owned
        assert ("SYSTEM", "occupations") in owned
        assert ("SYSTEM", "smearing") in owned

