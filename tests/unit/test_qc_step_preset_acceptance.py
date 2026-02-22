"""
Tests for QC step preset acceptance.

Verifies that pyscf_scf and orca_scf accept qc_precision presets,
while other QC steps and PW steps remain unchanged.

Uses new capability contract:
- Engine.supported_presets (engine capability declaration)
- ParamSpace gen-step applicability (Contract A)
"""

import pytest

from qmatsuite.workflow.registry import get_registry
from qmatsuite.presets.dimensions import DIMENSION_QC_PRECISION
from qmatsuite.presets.variants_registry import get_variant
from qmatsuite.engine.pyscf_engine import PySCFEngine
from qmatsuite.engine.orca_engine import ORCAEngine
from qmatsuite.engine.qe_engine import QeEngine
from qmatsuite.presets.catalog import list_presets_for_engine


def test_pyscf_scf_accepts_presets():
    """Test that PySCF engine supports qc_precision preset."""
    engine = PySCFEngine()
    
    # Engine must declare qc_precision in supported_presets
    assert "qc_precision" in engine.supported_presets


def test_orca_scf_accepts_presets():
    """Test that ORCA engine supports qc_precision preset."""
    # Use defer_binary_resolution=True for capability queries (binary not required)
    engine = ORCAEngine(defer_binary_resolution=True)
    
    # Engine must declare qc_precision in supported_presets
    assert "qc_precision" in engine.supported_presets


def test_pyscf_mp2_does_not_accept_presets():
    """Test that qc_precision does NOT apply to gen step 'mp2' (ParamSpace says N/A)."""
    # ParamSpace variant query: qc_precision does not apply to mp2
    variant = get_variant(DIMENSION_QC_PRECISION, "mp2")
    assert variant is None


def test_pyscf_td_does_not_accept_presets():
    """Test that qc_precision does NOT apply to gen step 'td' (ParamSpace says N/A)."""
    # ParamSpace variant query: qc_precision does not apply to td
    variant = get_variant(DIMENSION_QC_PRECISION, "td")
    assert variant is None


def test_orca_td_does_not_accept_presets():
    """Test that qc_precision does NOT apply to gen step 'td' (ParamSpace says N/A)."""
    # ParamSpace variant query: qc_precision does not apply to td
    variant = get_variant(DIMENSION_QC_PRECISION, "td")
    assert variant is None


def test_pw_step_types_unchanged():
    """Test that PW step types still work with PW presets."""
    engine = QeEngine()
    
    # QE engine must declare PW presets
    assert "precision" in engine.supported_presets
    assert "magnetism" in engine.supported_presets
    assert "occupations_scheme" in engine.supported_presets
    assert "convergence" in engine.supported_presets
    
    # QE engine should NOT support qc_precision
    assert "qc_precision" not in engine.supported_presets
    
    # Verify ParamSpace variant exists for PW precision on scf
    variant = get_variant("precision", "scf")
    assert variant is not None
    assert variant.dimension == "precision"


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
    """Test that PySCF engine only supports qc_precision (via supported_presets)."""
    engine = PySCFEngine()
    
    # PySCF engine should only support qc_precision
    assert engine.supported_presets == ["qc_precision"]


def test_orca_scf_allowed_dimensions_only_qc_precision():
    """Test that ORCA engine only supports qc_precision (via supported_presets)."""
    # Use defer_binary_resolution=True for capability queries (binary not required)
    engine = ORCAEngine(defer_binary_resolution=True)
    
    # ORCA engine should only support qc_precision
    assert engine.supported_presets == ["qc_precision"]


def test_list_accepting_presets_includes_qc_steps():
    """Test that list_accepting_presets_for_engine includes QC SCF steps."""
    registry = get_registry()
    
    # Use new contract function
    pyscf_result = registry.list_accepting_presets_for_engine("pyscf")
    orca_result = registry.list_accepting_presets_for_engine("orca")
    
    # Both should have "scf" gen step with qc_precision
    assert "scf" in pyscf_result
    assert DIMENSION_QC_PRECISION in pyscf_result["scf"]
    
    assert "scf" in orca_result
    assert DIMENSION_QC_PRECISION in orca_result["scf"]
    
    # mp2 and td should not be present (no presets available)
    assert "mp2" not in pyscf_result
    assert "td" not in pyscf_result
    assert "td" not in orca_result

