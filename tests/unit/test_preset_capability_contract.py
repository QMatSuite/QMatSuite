"""
Tests for preset capability contract functions.

Verifies that the new contract functions correctly compute available presets
from the intersection of Engine.supported_presets and ParamSpace gen-step applicability.
"""

import pytest

from qmatsuite.presets.variants_registry import list_dimensions_for_gen_step
from qmatsuite.presets.catalog import list_presets_for_engine
from qmatsuite.workflow.registry import get_registry
from qmatsuite.engine.qe_engine import QeEngine
from qmatsuite.engine.pyscf_engine import PySCFEngine
from qmatsuite.engine.orca_engine import ORCAEngine


class TestListDimensionsForGenStep:
    """Tests for list_dimensions_for_gen_step function."""
    
    def test_scf_has_multiple_dimensions(self):
        """Gen step 'scf' should have multiple applicable dimensions."""
        dimensions = list_dimensions_for_gen_step("scf")
        
        assert isinstance(dimensions, list)
        assert "precision" in dimensions
        assert "magnetism" in dimensions
        assert "occupations_scheme" in dimensions
        assert "convergence" in dimensions
        assert len(dimensions) >= 4
    
    def test_nscf_has_precision_and_others(self):
        """Gen step 'nscf' should have precision and other dimensions."""
        dimensions = list_dimensions_for_gen_step("nscf")
        
        assert isinstance(dimensions, list)
        assert "precision" in dimensions
        assert "magnetism" in dimensions
        assert "occupations_scheme" in dimensions
        assert "convergence" in dimensions
    
    def test_mp2_has_no_dimensions(self):
        """Gen step 'mp2' should have no applicable dimensions (no variants defined)."""
        dimensions = list_dimensions_for_gen_step("mp2")
        
        assert isinstance(dimensions, list)
        assert len(dimensions) == 0
    
    def test_td_has_no_dimensions(self):
        """Gen step 'td' should have no applicable dimensions (no variants defined)."""
        dimensions = list_dimensions_for_gen_step("td")
        
        assert isinstance(dimensions, list)
        assert len(dimensions) == 0
    
    def test_qc_precision_applies_to_scf(self):
        """QC precision dimension should apply to gen step 'scf'."""
        dimensions = list_dimensions_for_gen_step("scf")
        
        assert "qc_precision" in dimensions
    
    def test_qc_precision_does_not_apply_to_mp2(self):
        """QC precision dimension should NOT apply to gen step 'mp2'."""
        dimensions = list_dimensions_for_gen_step("mp2")
        
        assert "qc_precision" not in dimensions


class TestListPresetsForEngine:
    """Tests for list_presets_for_engine function."""
    
    def test_qe_engine_scf_has_pw_presets(self):
        """QE engine with gen step 'scf' should return PW presets."""
        presets = list_presets_for_engine("qe", "scf")
        
        assert isinstance(presets, list)
        assert "precision" in presets
        assert "magnetism" in presets
        assert "occupations_scheme" in presets
        assert "convergence" in presets
        # QE should NOT have qc_precision
        assert "qc_precision" not in presets
    
    def test_qe_engine_nscf_has_pw_presets(self):
        """QE engine with gen step 'nscf' should return PW presets."""
        presets = list_presets_for_engine("qe", "nscf")
        
        assert isinstance(presets, list)
        assert "precision" in presets
        assert "magnetism" in presets
        assert "occupations_scheme" in presets
        assert "convergence" in presets
    
    def test_pyscf_engine_scf_has_qc_precision(self):
        """PySCF engine with gen step 'scf' should return qc_precision."""
        presets = list_presets_for_engine("pyscf", "scf")
        
        assert isinstance(presets, list)
        assert "qc_precision" in presets
        # PySCF should NOT have PW presets
        assert "precision" not in presets
        assert "magnetism" not in presets
    
    def test_pyscf_engine_mp2_has_no_presets(self):
        """PySCF engine with gen step 'mp2' should return empty (ParamSpace says N/A)."""
        presets = list_presets_for_engine("pyscf", "mp2")
        
        assert isinstance(presets, list)
        assert len(presets) == 0
        # Even though PySCF supports qc_precision, ParamSpace says mp2 is not applicable
    
    def test_orca_engine_scf_has_qc_precision(self):
        """ORCA engine with gen step 'scf' should return qc_precision."""
        presets = list_presets_for_engine("orca", "scf")
        
        assert isinstance(presets, list)
        assert "qc_precision" in presets
        # ORCA should NOT have PW presets
        assert "precision" not in presets
        assert "magnetism" not in presets
    
    def test_orca_engine_td_has_no_presets(self):
        """ORCA engine with gen step 'td' should return empty (ParamSpace says N/A)."""
        presets = list_presets_for_engine("orca", "td")
        
        assert isinstance(presets, list)
        assert len(presets) == 0
    
    def test_unknown_engine_raises_keyerror(self):
        """Unknown engine name should raise KeyError."""
        with pytest.raises(KeyError, match="not found in registry"):
            list_presets_for_engine("unknown_engine", "scf")
    
    def test_intersection_logic(self):
        """Test that intersection logic works correctly."""
        # QE supports precision, and precision applies to scf
        # So qe + scf should return precision
        presets = list_presets_for_engine("qe", "scf")
        assert "precision" in presets
        
        # PySCF supports qc_precision, but qc_precision does NOT apply to mp2
        # So pyscf + mp2 should return empty
        presets = list_presets_for_engine("pyscf", "mp2")
        assert len(presets) == 0


class TestListAcceptingPresetsForEngine:
    """Tests for registry.list_accepting_presets_for_engine method."""
    
    def test_qe_engine_has_multiple_gen_steps(self):
        """QE engine should have presets for multiple gen steps."""
        registry = get_registry()
        result = registry.list_accepting_presets_for_engine("qe")
        
        assert isinstance(result, dict)
        assert "scf" in result
        assert "nscf" in result
        assert "relax" in result
        
        # Check that scf has multiple presets
        assert len(result["scf"]) >= 4
        assert "precision" in result["scf"]
        assert "magnetism" in result["scf"]
    
    def test_pyscf_engine_has_scf_only(self):
        """PySCF engine should only have presets for 'scf' gen step."""
        registry = get_registry()
        result = registry.list_accepting_presets_for_engine("pyscf")
        
        assert isinstance(result, dict)
        assert "scf" in result
        assert "qc_precision" in result["scf"]
        # mp2 and td should not be in result (no presets available)
        assert "mp2" not in result
        assert "td" not in result
    
    def test_orca_engine_has_scf_only(self):
        """ORCA engine should only have presets for 'scf' gen step."""
        registry = get_registry()
        result = registry.list_accepting_presets_for_engine("orca")
        
        assert isinstance(result, dict)
        assert "scf" in result
        assert "qc_precision" in result["scf"]
        # td should not be in result (no presets available)
        assert "td" not in result
    
    def test_unknown_engine_raises_keyerror(self):
        """Unknown engine name should raise KeyError."""
        registry = get_registry()
        with pytest.raises(KeyError, match="not found in registry"):
            registry.list_accepting_presets_for_engine("unknown_engine")
    
    def test_result_structure(self):
        """Test that result has correct structure."""
        registry = get_registry()
        result = registry.list_accepting_presets_for_engine("qe")
        
        # Should be a dict
        assert isinstance(result, dict)
        
        # Each value should be a sorted list of strings
        for gen_step, presets in result.items():
            assert isinstance(gen_step, str)
            assert isinstance(presets, list)
            assert all(isinstance(p, str) for p in presets)
            # Should be sorted
            assert presets == sorted(presets)

