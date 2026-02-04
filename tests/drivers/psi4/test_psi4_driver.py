"""
Tests for Psi4 engine driver.

These tests verify the driver metadata, step type specs, and registration.
No Psi4 installation is required — these test the driver bundle only.
"""

import pytest

from quantumvitas.drivers.psi4.driver import Psi4Driver
from quantumvitas.core.driver_protocol import WorkdirPolicy, ErrorClass


@pytest.fixture
def driver():
    return Psi4Driver()


class TestPsi4DriverProperties:
    """Test driver protocol properties."""

    def test_prefix(self, driver):
        assert driver.PREFIX == "psi4"

    def test_engine_family(self, driver):
        assert driver.engine_family == "psi4"

    def test_display_name(self, driver):
        assert driver.display_name == "Psi4"

    def test_driver_api_version(self, driver):
        assert driver.driver_api_version == "1.0.0"

    def test_supported_gen_steps(self, driver):
        expected = frozenset({"scf", "hf", "mp2", "relax", "td"})
        assert driver.SUPPORTED_GEN_STEPS == expected

    def test_workdir_policy(self, driver):
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED


class TestPsi4StepTypeSpecs:
    """Test step type specifications."""

    def test_step_type_specs_not_empty(self, driver):
        specs = driver.get_step_type_specs()
        assert len(specs) >= 5

    def test_all_specs_have_correct_engine(self, driver):
        for spec in driver.get_step_type_specs():
            assert spec.engine == "psi4", f"Spec {spec.step_type_spec} has wrong engine: {spec.engine}"

    def test_all_specs_have_psi4_prefix(self, driver):
        for spec in driver.get_step_type_specs():
            assert spec.step_type_spec.startswith("psi4_"), (
                f"Spec '{spec.step_type_spec}' does not start with 'psi4_'"
            )

    def test_scf_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "psi4_scf" in specs

    def test_hf_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "psi4_hf" in specs

    def test_mp2_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "psi4_mp2" in specs

    def test_relax_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "psi4_relax" in specs

    def test_td_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "psi4_td" in specs

    def test_specs_have_descriptions(self, driver):
        for spec in driver.get_step_type_specs():
            assert spec.description, f"Spec {spec.step_type_spec} has no description"

    def test_specs_have_executable(self, driver):
        for spec in driver.get_step_type_specs():
            assert spec.executable == "python"


class TestPsi4DriverMethods:
    """Test driver methods."""

    def test_handler_is_callable(self, driver):
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self, driver):
        from quantumvitas.drivers.psi4.recipe import Psi4Recipe
        recipe_class = driver.get_recipe_class()
        assert recipe_class is Psi4Recipe

    def test_capabilities(self, driver):
        caps = driver.get_capabilities()
        assert "scf" in caps
        assert "molecular" in caps
        assert "chain" in caps
        assert "python_native" in caps

    def test_supports_incremental_skip(self, driver):
        assert driver.supports_incremental_skip("psi4_scf") is True
        assert driver.supports_incremental_skip("psi4_mp2") is True

    def test_classify_convergence_error(self, driver):
        assert driver.classify_error("SCF not converged", 1) == ErrorClass.CONVERGENCE

    def test_classify_import_error(self, driver):
        assert driver.classify_error("ImportError: No module named 'psi4'", 2) == ErrorClass.EXECUTABLE_NOT_FOUND

    def test_classify_unknown_error(self, driver):
        assert driver.classify_error("something else", 1) == ErrorClass.UNKNOWN

    def test_artifact_patterns(self, driver):
        patterns = driver.get_artifact_patterns()
        assert "wavefunction" in patterns
        assert "output" in patterns


class TestPsi4Registration:
    """Test driver registration in the DriverRegistry."""

    def test_driver_registered(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        assert "psi4" in DriverRegistry.get_all_engines(), "Psi4 driver not registered"

    def test_registry_lookup(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("psi4")
        assert driver is not None
        assert driver.PREFIX == "psi4"

    def test_engine_registry_has_psi4(self):
        from quantumvitas.engine.registry import create_default_registry
        registry = create_default_registry()
        assert registry.has("psi4")

    def test_step_types_in_workflow_registry(self):
        """Verify Psi4 step types are registered in the workflow StepTypeRegistry."""
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()

        # The GEN steps should resolve for engine="psi4"
        for gen_type in ("scf", "hf", "mp2", "relax", "td"):
            spec = registry.get_for_engine(gen_type, "psi4")
            assert spec is not None, f"GEN type '{gen_type}' for psi4 not in registry"
            assert spec.step_type_spec == f"psi4_{gen_type}", (
                f"Expected 'psi4_{gen_type}', got '{spec.step_type_spec}'"
            )
            assert spec.engine == "psi4"
