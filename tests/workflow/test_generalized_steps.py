"""
Tests for generalized step taxonomy and materialization.

Note: MATERIALIZATION_MAP has been removed. Step-type mappings are now
defined in each driver's get_materialization_map() method (SSOT).
See test_materialization_ssot.py for comprehensive SSOT tests.
"""

import pytest

from quantumvitas.workflow.generalized_steps import (
    materialize_step,
    materialize_workflow,
    dematerialize_step,
    dematerialize_to_generalized_step,
    get_supported_generalized_steps,
    get_engine_families_for_step,
)
from quantumvitas.core.driver_registry import DriverRegistry
import quantumvitas.drivers  # Ensure drivers are loaded


class TestGenStepMaterialization:
    """Test materialization of generalized steps to engine-specific steps."""
    
    def test_materialize_scf_qe(self):
        """scf materializes to qe_scf for qe family."""
        result = materialize_step("scf", "qe")
        assert result == "qe_scf"
    
    def test_materialize_scf_pyscf(self):
        """scf materializes to pyscf_scf for pyscf family."""
        result = materialize_step("scf", "pyscf")
        assert result == "pyscf_scf"
    
    def test_materialize_unsupported_combination(self):
        """Unsupported combinations return None."""
        result = materialize_step("wannier", "pyscf")
        assert result is None
    
    def test_materialize_workflow_basic(self):
        """Materialize a simple workflow."""
        result = materialize_workflow(["scf", "nscf", "dos"], "qe")
        assert result == ["qe_scf", "qe_nscf", "qe_dos"]
    
    def test_materialize_workflow_qe_bands(self):
        """Materialize QE bands workflow.

        Note: "bands" maps to qe_bands (bands.x post-processing).
        For pw.x bands calculation, use "bandspw".
        """
        result = materialize_workflow(
            ["scf", "nscf", "bands"],
            "qe"
        )
        # bands maps to qe_bands (bands.x), not qe_bandspw (pw.x)
        assert result == ["qe_scf", "qe_nscf", "qe_bands"]

    def test_materialize_workflow_pw2wannier(self):
        """Materialize QE pw2wannier step."""
        result = materialize_workflow(
            ["scf", "nscf", "pw2wannier"],
            "qe"
        )
        assert result == ["qe_scf", "qe_nscf", "qe_pw2wannier"]
    
    def test_materialize_workflow_fails_on_unsupported(self):
        """Materialization fails if step is unsupported."""
        with pytest.raises(ValueError, match="not supported"):
            materialize_workflow(["SCF", "WANNIER"], "pyscf")


class TestDematerialization:
    """Test reverse materialization (engine-specific → generalized)."""

    def test_dematerialize_qe_scf(self):
        """qe_scf dematerializes to (qe, scf)."""
        result = dematerialize_step("qe_scf")
        assert result == ("qe", "scf")

    def test_dematerialize_to_generalized_step(self):
        """Dematerialize to generalized step only."""
        result = dematerialize_to_generalized_step("qe_scf")
        assert result == "scf"

        result = dematerialize_to_generalized_step("pyscf_scf")
        assert result == "scf"

        result = dematerialize_to_generalized_step("w90_wannier")
        assert result == "wannier"

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
        assert "scf" in supported
        assert "nscf" in supported
        assert "dos" in supported
        # wannier is now in w90 driver, not QE
        assert "pw2wannier" in supported  # QE has pw2wannier90

    def test_get_supported_generalized_steps_pyscf(self):
        """Get generalized steps supported by pyscf family."""
        supported = get_supported_generalized_steps("pyscf")
        assert "scf" in supported
        assert len(supported) >= 1  # At least scf

    def test_get_supported_generalized_steps_w90(self):
        """Get generalized steps supported by w90 family."""
        supported = get_supported_generalized_steps("w90")
        assert "wannier" in supported

    def test_get_engine_families_for_step(self):
        """Get engine families that support a generalized step."""
        families = get_engine_families_for_step("scf")
        assert "qe" in families
        assert "pyscf" in families

        families = get_engine_families_for_step("wannier")
        assert "w90" in families  # wannier is now in w90 driver

