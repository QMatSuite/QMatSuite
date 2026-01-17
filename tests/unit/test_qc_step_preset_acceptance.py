"""
Tests for QC step preset acceptance.

Verifies that pyscf_scf and orca_scf accept qc_precision presets,
while other QC steps and PW steps remain unchanged.
"""

import pytest

from quantumvitas.workflow.registry import get_registry
from quantumvitas.presets.dimensions import DIMENSION_QC_PRECISION
from quantumvitas.presets.variants_registry import get_variant


def test_pyscf_scf_accepts_presets():
    """Test that pyscf_scf accepts presets."""
    registry = get_registry()
    spec = registry.get("pyscf_scf")
    
    assert spec is not None
    assert spec.accepts_presets is True
    assert DIMENSION_QC_PRECISION in spec.allowed_dimensions


def test_orca_scf_accepts_presets():
    """Test that orca_scf accepts presets."""
    registry = get_registry()
    spec = registry.get("orca_scf")
    
    assert spec is not None
    assert spec.accepts_presets is True
    assert DIMENSION_QC_PRECISION in spec.allowed_dimensions


def test_pyscf_mp2_does_not_accept_presets():
    """Test that pyscf_mp2 does NOT accept presets."""
    registry = get_registry()
    spec = registry.get("pyscf_mp2")
    
    assert spec is not None
    assert spec.accepts_presets is False
    assert len(spec.allowed_dimensions) == 0


def test_pyscf_td_does_not_accept_presets():
    """Test that pyscf_td does NOT accept presets."""
    registry = get_registry()
    spec = registry.get("pyscf_td")
    
    assert spec is not None
    assert spec.accepts_presets is False
    assert len(spec.allowed_dimensions) == 0


def test_orca_td_does_not_accept_presets():
    """Test that orca_td does NOT accept presets."""
    registry = get_registry()
    spec = registry.get("orca_td")
    
    assert spec is not None
    assert spec.accepts_presets is False
    assert len(spec.allowed_dimensions) == 0


def test_pw_step_types_unchanged():
    """Test that PW step types are unchanged."""
    registry = get_registry()
    
    # Check a few key PW step types
    pw_steps = ["qe_scf", "qe_nscf", "qe_relax"]
    
    for step_type in pw_steps:
        spec = registry.get(step_type)
        assert spec is not None
        assert spec.accepts_presets is True
        # PW steps should have PW_DIMENSIONS, not qc_precision
        assert DIMENSION_QC_PRECISION not in spec.allowed_dimensions
        # Should have PW dimensions
        assert "precision" in spec.allowed_dimensions or "magnetism" in spec.allowed_dimensions


def test_qc_precision_variant_applies_to_scf():
    """Test that QC precision variant applies to gen step 'scf'."""
    # Test with public_type "scf" (gen step)
    variant = get_variant(DIMENSION_QC_PRECISION, "scf")
    
    assert variant is not None
    assert variant.dimension == DIMENSION_QC_PRECISION
    assert "scf" in variant.applies_to_step_types


def test_qc_precision_variant_does_not_apply_to_mp2():
    """Test that QC precision variant does NOT apply to gen step 'mp2'."""
    variant = get_variant(DIMENSION_QC_PRECISION, "mp2")
    
    assert variant is None


def test_qc_precision_variant_does_not_apply_to_td():
    """Test that QC precision variant does NOT apply to gen step 'td'."""
    variant = get_variant(DIMENSION_QC_PRECISION, "td")
    
    assert variant is None


def test_pyscf_scf_allowed_dimensions_only_qc_precision():
    """Test that pyscf_scf only allows qc_precision dimension."""
    registry = get_registry()
    spec = registry.get("pyscf_scf")
    
    assert spec.allowed_dimensions == frozenset({DIMENSION_QC_PRECISION})


def test_orca_scf_allowed_dimensions_only_qc_precision():
    """Test that orca_scf only allows qc_precision dimension."""
    registry = get_registry()
    spec = registry.get("orca_scf")
    
    assert spec.allowed_dimensions == frozenset({DIMENSION_QC_PRECISION})


def test_list_accepting_presets_includes_qc_steps():
    """Test that list_accepting_presets includes QC SCF steps."""
    registry = get_registry()
    accepting = registry.list_accepting_presets()
    
    # Should include "scf" (public type, shared by qe_scf, pyscf_scf, orca_scf)
    assert "scf" in accepting
    
    # Verify machine types
    pyscf_spec = registry.get("pyscf_scf")
    orca_spec = registry.get("orca_scf")
    
    assert pyscf_spec.accepts_presets is True
    assert orca_spec.accepts_presets is True

