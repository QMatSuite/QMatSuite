"""
Tests for generalized step taxonomy and materialization.
"""

import pytest

from quantumvitas.workflow.generalized_steps import (
    GeneralizedStep,
    MATERIALIZATION_MAP,
    materialize_step,
    materialize_workflow,
    dematerialize_step,
    dematerialize_to_generalized_step,
    get_supported_generalized_steps,
    get_engine_families_for_step,
)


class TestGeneralizedStepMaterialization:
    """Test materialization of generalized steps to engine-specific steps."""
    
    def test_materialize_scf_qe(self):
        """SCF materializes to qe_scf for qe family."""
        result = materialize_step("SCF", "qe")
        assert result == "qe_scf"
    
    def test_materialize_scf_pyscf(self):
        """SCF materializes to pyscf_scf for pyscf family."""
        result = materialize_step("SCF", "pyscf")
        assert result == "pyscf_scf"
    
    def test_materialize_unsupported_combination(self):
        """Unsupported combinations return None."""
        result = materialize_step("WANNIER", "pyscf")
        assert result is None
    
    def test_materialize_workflow_basic(self):
        """Materialize a simple workflow."""
        result = materialize_workflow(["SCF", "NSCF", "DOS"], "qe")
        assert result == ["qe_scf", "qe_nscf", "qe_dos"]
    
    def test_materialize_workflow_wannier(self):
        """Materialize Wannier workflow."""
        result = materialize_workflow(
            ["SCF", "NSCF", "WANNIER_CONVERT", "WANNIER"],
            "qe"
        )
        assert result == ["qe_scf", "qe_nscf", "qe_pw2wannier90", "w90_run"]
    
    def test_materialize_workflow_fails_on_unsupported(self):
        """Materialization fails if step is unsupported."""
        with pytest.raises(ValueError, match="not supported"):
            materialize_workflow(["SCF", "WANNIER"], "pyscf")


class TestDematerialization:
    """Test reverse materialization (engine-specific → generalized)."""
    
    def test_dematerialize_qe_scf(self):
        """qe_scf dematerializes to (qe, SCF)."""
        result = dematerialize_step("qe_scf")
        assert result == ("qe", "SCF")
    
    def test_dematerialize_to_generalized_step(self):
        """Dematerialize to generalized step only."""
        result = dematerialize_to_generalized_step("qe_scf")
        assert result == "SCF"
        
        result = dematerialize_to_generalized_step("pyscf_scf")
        assert result == "SCF"
        
        result = dematerialize_to_generalized_step("w90_run")
        assert result == "WANNIER"
    
    def test_dematerialize_unknown_step(self):
        """Unknown steps return None."""
        result = dematerialize_step("unknown_step")
        assert result is None


class TestMaterializationMap:
    """Test materialization map invariants."""
    
    def test_zero_one_rule(self):
        """Each (family, generalized_step) maps to at most one specific step."""
        # Build reverse mapping to check for duplicates
        family_gen_to_specific: dict = {}
        for (family, gen_step), specific_step in MATERIALIZATION_MAP.items():
            key = (family, gen_step)
            if key in family_gen_to_specific:
                # Check that it's the same mapping (not a conflict)
                assert family_gen_to_specific[key] == specific_step, \
                    f"Conflict: {key} maps to both {family_gen_to_specific[key]} and {specific_step}"
            else:
                family_gen_to_specific[key] = specific_step
    
    def test_all_mappings_return_valid_step_type(self):
        """All mappings return either a valid step type string or None."""
        from quantumvitas.workflow.registry import get_registry, normalize_step_type
        
        registry = get_registry()
        for (family, gen_step), specific_step in MATERIALIZATION_MAP.items():
            if specific_step is not None:
                # Normalize deprecated types (qe_vc_relax maps to qe_relax)
                normalized = normalize_step_type(specific_step)
                # Should be a valid step type in registry (or backward compat mapped)
                assert registry.has(normalized), \
                    f"Materialized step '{specific_step}' (normalized: {normalized}) for ({family}, {gen_step}) not found in registry"


class TestSupportedSteps:
    """Test functions for querying supported steps."""
    
    def test_get_supported_generalized_steps_qe(self):
        """Get generalized steps supported by qe family."""
        supported = get_supported_generalized_steps("qe")
        assert "SCF" in supported
        assert "NSCF" in supported
        assert "DOS" in supported
        assert "WANNIER" in supported
    
    def test_get_supported_generalized_steps_pyscf(self):
        """Get generalized steps supported by pyscf family."""
        supported = get_supported_generalized_steps("pyscf")
        assert "SCF" in supported
        assert len(supported) >= 1  # At least SCF
    
    def test_get_engine_families_for_step(self):
        """Get engine families that support a generalized step."""
        families = get_engine_families_for_step("SCF")
        assert "qe" in families
        assert "pyscf" in families
        
        families = get_engine_families_for_step("WANNIER")
        assert "qe" in families  # w90 is part of qe family


class TestGeneralizedStepEnum:
    """Test GeneralizedStep enum."""
    
    def test_enum_values(self):
        """Generalized step enum has expected values."""
        assert GeneralizedStep.SCF == "SCF"
        assert GeneralizedStep.NSCF == "NSCF"
        assert GeneralizedStep.BANDS == "BANDS"
        assert GeneralizedStep.BANDS_POST == "BANDS_POST"
        assert GeneralizedStep.WANNIER == "WANNIER"

