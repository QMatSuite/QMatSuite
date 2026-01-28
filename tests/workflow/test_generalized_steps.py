"""
Tests for generalized step taxonomy and materialization.

Note: MATERIALIZATION_MAP has been removed. Step-type mappings are now
defined in each driver's get_materialization_map() method (SSOT).
See test_materialization_ssot.py for comprehensive SSOT tests.
"""

import pytest

from quantumvitas.workflow.generalized_steps import (
    GeneralizedStep,
    materialize_step,
    materialize_workflow,
    dematerialize_step,
    dematerialize_to_generalized_step,
    get_supported_generalized_steps,
    get_engine_families_for_step,
)
from quantumvitas.core.driver_registry import DriverRegistry
import quantumvitas.drivers  # Ensure drivers are loaded


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
    
    def test_materialize_workflow_qe_bands(self):
        """Materialize QE bands workflow.

        Note: "BANDS" maps to qe_bands (bands.x post-processing) via StepTypeRegistry.
        For pw.x bands calculation, use "BANDS_PW" or direct GEN_BANDS.
        """
        result = materialize_workflow(
            ["SCF", "NSCF", "BANDS"],
            "qe"
        )
        # BANDS maps to qe_bands (bands.x), not qe_bands_pw (pw.x)
        assert result == ["qe_scf", "qe_nscf", "qe_bands"]

    def test_materialize_workflow_wannier_convert(self):
        """Materialize QE Wannier convert step."""
        result = materialize_workflow(
            ["SCF", "NSCF", "WANNIER_CONVERT"],
            "qe"
        )
        assert result == ["qe_scf", "qe_nscf", "qe_pw2wannier90"]
    
    def test_materialize_workflow_fails_on_unsupported(self):
        """Materialization fails if step is unsupported."""
        with pytest.raises(ValueError, match="not supported"):
            materialize_workflow(["SCF", "WANNIER"], "pyscf")


class TestDematerialization:
    """Test reverse materialization (engine-specific → generalized)."""

    def test_dematerialize_qe_scf(self):
        """qe_scf dematerializes to (qe, GEN_SCF)."""
        result = dematerialize_step("qe_scf")
        assert result == ("qe", "GEN_SCF")

    def test_dematerialize_to_generalized_step(self):
        """Dematerialize to generalized step only (GEN_ prefix stripped)."""
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
    """Test materialization map invariants via DriverRegistry SSOT."""

    def test_zero_one_rule(self):
        """Each (family, generalized_step) maps to at most one specific step."""
        # Check each driver's materialization map for duplicates
        for engine in DriverRegistry.get_all_engines():
            driver = DriverRegistry.get_driver(engine)
            mat_map = driver.get_materialization_map()
            # Each gen_type should map to exactly one specific step
            seen_gen_types = set()
            for gen_type in mat_map.keys():
                assert gen_type not in seen_gen_types, \
                    f"Duplicate gen_type {gen_type} in {engine} driver"
                seen_gen_types.add(gen_type)

    def test_all_mappings_return_valid_step_type(self):
        """All mappings return registered step types."""
        for engine in DriverRegistry.get_all_engines():
            driver = DriverRegistry.get_driver(engine)
            mat_map = driver.get_materialization_map()
            for gen_type, specific_step in mat_map.items():
                assert DriverRegistry.is_step_type_registered(specific_step), \
                    f"Step type '{specific_step}' from {engine} driver not registered"


class TestSupportedSteps:
    """Test functions for querying supported steps."""

    def test_get_supported_generalized_steps_qe(self):
        """Get generalized steps supported by qe family."""
        supported = get_supported_generalized_steps("qe")
        assert "SCF" in supported
        assert "NSCF" in supported
        assert "DOS" in supported
        # WANNIER is now in w90 driver, not QE
        assert "WANNIER_CONVERT" in supported  # QE has pw2wannier90

    def test_get_supported_generalized_steps_pyscf(self):
        """Get generalized steps supported by pyscf family."""
        supported = get_supported_generalized_steps("pyscf")
        assert "SCF" in supported
        assert len(supported) >= 1  # At least SCF

    def test_get_supported_generalized_steps_w90(self):
        """Get generalized steps supported by w90 family."""
        supported = get_supported_generalized_steps("w90")
        assert "WANNIER" in supported

    def test_get_engine_families_for_step(self):
        """Get engine families that support a generalized step."""
        families = get_engine_families_for_step("SCF")
        assert "qe" in families
        assert "pyscf" in families

        families = get_engine_families_for_step("WANNIER")
        assert "w90" in families  # WANNIER is now in w90 driver


class TestGeneralizedStepEnum:
    """Test GeneralizedStep enum."""
    
    def test_enum_values(self):
        """Generalized step enum has expected values."""
        assert GeneralizedStep.SCF == "SCF"
        assert GeneralizedStep.NSCF == "NSCF"
        assert GeneralizedStep.BANDS == "BANDS"
        assert GeneralizedStep.BANDS_POST == "BANDS_POST"
        assert GeneralizedStep.WANNIER == "WANNIER"

