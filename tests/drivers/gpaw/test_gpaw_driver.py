"""
Tests for GPAW engine driver.

These tests verify the driver metadata, step type specs, and registration.
No GPAW installation is required — these test the driver bundle only.
"""

import pytest

from quantumvitas.drivers.gpaw.driver import GPAWDriver
from quantumvitas.core.driver_protocol import WorkdirPolicy, ErrorClass


@pytest.fixture
def driver():
    return GPAWDriver()


class TestGPAWDriverProperties:
    """Test driver protocol properties."""

    def test_prefix(self, driver):
        assert driver.PREFIX == "gpaw"

    def test_engine_family(self, driver):
        assert driver.engine_family == "gpaw"

    def test_display_name(self, driver):
        assert driver.display_name == "GPAW"

    def test_driver_api_version(self, driver):
        assert driver.driver_api_version == "1.0.0"

    def test_supported_gen_steps(self, driver):
        expected = frozenset({"scf", "nscf", "relax", "bandspw", "dos", "md"})
        assert driver.SUPPORTED_GEN_STEPS == expected

    def test_workdir_policy(self, driver):
        assert driver.get_workdir_policy() == WorkdirPolicy.SHARED


class TestGPAWStepTypeSpecs:
    """Test step type specifications."""

    def test_step_type_specs_not_empty(self, driver):
        specs = driver.get_step_type_specs()
        assert len(specs) == 6

    def test_all_specs_have_correct_engine(self, driver):
        for spec in driver.get_step_type_specs():
            assert spec.engine == "gpaw", (
                f"Spec {spec.step_type_spec} has wrong engine: {spec.engine}"
            )

    def test_all_specs_have_gpaw_prefix(self, driver):
        for spec in driver.get_step_type_specs():
            assert spec.step_type_spec.startswith("gpaw_"), (
                f"Spec '{spec.step_type_spec}' does not start with 'gpaw_'"
            )

    def test_scf_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "gpaw_scf" in specs

    def test_nscf_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "gpaw_nscf" in specs

    def test_relax_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "gpaw_relax" in specs

    def test_bandspw_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "gpaw_bandspw" in specs

    def test_dos_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "gpaw_dos" in specs

    def test_md_spec_exists(self, driver):
        specs = {s.step_type_spec: s for s in driver.get_step_type_specs()}
        assert "gpaw_md" in specs

    def test_specs_have_descriptions(self, driver):
        for spec in driver.get_step_type_specs():
            assert spec.description, f"Spec {spec.step_type_spec} has no description"

    def test_specs_have_executable_python(self, driver):
        for spec in driver.get_step_type_specs():
            assert spec.executable == "python"

    def test_specs_are_mpi_aware(self, driver):
        for spec in driver.get_step_type_specs():
            assert spec.mpi_aware is True


class TestGPAWDriverMethods:
    """Test driver methods."""

    def test_handler_is_callable(self, driver):
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self, driver):
        from quantumvitas.drivers.gpaw.recipe import GPAWRecipe
        recipe_class = driver.get_recipe_class()
        assert recipe_class is GPAWRecipe

    def test_materialization_map(self, driver):
        mat_map = driver.get_materialization_map()
        assert mat_map["scf"] == "gpaw_scf"
        assert mat_map["nscf"] == "gpaw_nscf"
        assert mat_map["relax"] == "gpaw_relax"
        assert mat_map["bandspw"] == "gpaw_bandspw"
        assert mat_map["dos"] == "gpaw_dos"
        assert mat_map["md"] == "gpaw_md"

    def test_capabilities(self, driver):
        caps = driver.get_capabilities()
        assert "scf" in caps
        assert "periodic" in caps
        assert "molecular" in caps
        assert "python_native" in caps
        assert "mpi" in caps

    def test_supports_incremental_skip_scf(self, driver):
        assert driver.supports_incremental_skip("gpaw_scf") is True

    def test_supports_incremental_skip_md(self, driver):
        assert driver.supports_incremental_skip("gpaw_md") is False

    def test_classify_convergence_error(self, driver):
        assert driver.classify_error("SCF not converged", 1) == ErrorClass.CONVERGENCE

    def test_classify_memory_error(self, driver):
        assert driver.classify_error("MemoryError: unable to allocate", 1) == ErrorClass.MEMORY

    def test_classify_import_error(self, driver):
        assert driver.classify_error("ImportError: No module named 'gpaw'", 2) == ErrorClass.EXECUTABLE_NOT_FOUND

    def test_classify_missing_file(self, driver):
        assert driver.classify_error("FileNotFoundError: No such file", 1) == ErrorClass.MISSING_FILE

    def test_classify_input_error(self, driver):
        assert driver.classify_error("ValueError: invalid parameter", 1) == ErrorClass.INPUT_ERROR

    def test_classify_unknown_error(self, driver):
        assert driver.classify_error("something else", 1) == ErrorClass.UNKNOWN

    def test_artifact_patterns(self, driver):
        patterns = driver.get_artifact_patterns()
        assert "restart" in patterns
        assert "results" in patterns
        assert "log" in patterns


class TestGPAWRegistration:
    """Test driver registration in the DriverRegistry."""

    def test_driver_registered(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        assert "gpaw" in DriverRegistry.get_all_engines(), "GPAW driver not registered"

    def test_registry_lookup(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("gpaw")
        assert driver is not None
        assert driver.PREFIX == "gpaw"

    def test_engine_registry_has_gpaw(self):
        from quantumvitas.engine.registry import create_default_registry
        registry = create_default_registry()
        assert registry.has("gpaw")

    def test_step_types_in_workflow_registry(self):
        """Verify GPAW step types are registered in the workflow StepTypeRegistry."""
        from quantumvitas.workflow.registry import get_registry
        registry = get_registry()

        for gen_type in ("scf", "nscf", "relax", "bandspw", "dos", "md"):
            spec = registry.get_for_engine(gen_type, "gpaw")
            assert spec is not None, f"GEN type '{gen_type}' for gpaw not in registry"
            assert spec.step_type_spec == f"gpaw_{gen_type}", (
                f"Expected 'gpaw_{gen_type}', got '{spec.step_type_spec}'"
            )
            assert spec.engine == "gpaw"


class TestGPAWIsolation:
    """Enforcement tests: GPAW must be isolated from kernel."""

    def test_handlers_no_gpaw_handler(self):
        """handlers.py should not contain gpaw_step_handler."""
        from pathlib import Path
        handlers_path = (
            Path(__file__).parent.parent.parent.parent
            / "src" / "quantumvitas" / "execution" / "handlers.py"
        )
        source = handlers_path.read_text()
        assert "def gpaw_step_handler" not in source, (
            "gpaw_step_handler should be in drivers/gpaw/handler.py"
        )

    def test_recipes_no_gpaw_recipe(self):
        """recipes.py should not contain GPAWRecipe."""
        from pathlib import Path
        recipes_path = (
            Path(__file__).parent.parent.parent.parent
            / "src" / "quantumvitas" / "execution" / "recipes.py"
        )
        source = recipes_path.read_text()
        assert "class GPAWRecipe" not in source, (
            "GPAWRecipe should be in drivers/gpaw/recipe.py"
        )
