"""
Unit tests for registry compatibility aliases.

Tests that deprecated step types (vc-relax, opt, geomopt) are correctly
mapped to the unified "relax" type with deprecation warnings.
"""

import pytest
import warnings

from quantumvitas.workflow.registry import (
    get_registry,
    normalize_step_type,
    STEP_TYPE_ALIASES,
)


class TestStepTypeAliases:
    """Test that compatibility aliases work correctly."""

    def test_vc_relax_maps_to_relax(self):
        """vc-relax should map to relax with deprecation warning."""
        with pytest.warns(DeprecationWarning, match="vc-relax.*deprecated"):
            normalized = normalize_step_type("vc-relax")
        assert normalized == "relax"

    def test_qe_vc_relax_maps_to_qe_relax(self):
        """qe_vc_relax should map to qe_relax with deprecation warning."""
        with pytest.warns(DeprecationWarning, match="qe_vc_relax.*deprecated"):
            normalized = normalize_step_type("qe_vc_relax")
        assert normalized == "qe_relax"

    def test_opt_maps_to_relax(self):
        """opt should map to relax with deprecation warning."""
        with pytest.warns(DeprecationWarning, match="opt.*deprecated"):
            normalized = normalize_step_type("opt")
        assert normalized == "relax"

    def test_geomopt_maps_to_relax(self):
        """geomopt should map to relax with deprecation warning."""
        with pytest.warns(DeprecationWarning, match="geomopt.*deprecated"):
            normalized = normalize_step_type("geomopt")
        assert normalized == "relax"

    def test_non_alias_unchanged(self):
        """Non-alias step types should be returned unchanged."""
        # Should not warn
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            normalized = normalize_step_type("qe_relax")
        assert normalized == "qe_relax"
        
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            normalized = normalize_step_type("scf")
        assert normalized == "scf"

    def test_empty_string_unchanged(self):
        """Empty string should be returned unchanged."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            normalized = normalize_step_type("")
        assert normalized == ""

    def test_all_aliases_in_dict(self):
        """All aliases should be in STEP_TYPE_ALIASES dict."""
        expected_aliases = {"vc-relax", "qe_vc_relax", "opt", "geomopt"}
        assert set(STEP_TYPE_ALIASES.keys()) == expected_aliases

    def test_alias_mapping_through_registry(self):
        """Aliases should work when used with registry lookup."""
        registry = get_registry()
        
        # vc-relax should normalize to relax, then lookup should find qe_relax
        # (since relax public_type maps to qe_relax by default)
        normalized = normalize_step_type("vc-relax")
        spec = registry.get(normalized)
        assert spec is not None
        assert spec.step_type_gen == "relax"

