"""Gate 1: Registry-based routing tests.

These tests verify that all routing goes through the registry
and that the registry provides correct mappings.
"""

import pytest
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestRegistryBasics:
    """Basic registry functionality tests."""

    def test_registry_is_singleton(self):
        """Registry should be a singleton."""
        from quantumvitas.core.driver_registry import DriverRegistry
        r1 = DriverRegistry.get_instance()
        r2 = DriverRegistry.get_instance()
        assert r1 is r2

    def test_qe_driver_registered(self):
        """QE driver should be auto-registered."""
        # Import drivers to trigger registration
        import quantumvitas.drivers

        from quantumvitas.core.driver_registry import DriverRegistry
        assert DriverRegistry.is_engine_registered("qe")
        driver = DriverRegistry.get_driver("qe")
        assert driver.engine_family == "qe"

    def test_unknown_engine_raises(self):
        """Unknown engine should raise UnknownEngineError."""
        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.core.driver_exceptions import UnknownEngineError

        with pytest.raises(UnknownEngineError) as exc_info:
            DriverRegistry.get_driver("nonexistent_engine_xyz")

        assert "nonexistent_engine_xyz" in str(exc_info.value)
        assert "qe" in str(exc_info.value)  # Should suggest available engines


class TestStepTypeRouting:
    """Step type to handler routing tests."""

    def test_known_step_type_returns_handler(self):
        """Known step type should return handler."""
        import quantumvitas.drivers

        from quantumvitas.core.driver_registry import DriverRegistry
        handler = DriverRegistry.get_handler("qe_scf")
        assert callable(handler)

    def test_unknown_step_type_raises(self):
        """Unknown step type should raise UnknownStepTypeError."""
        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.core.driver_exceptions import UnknownStepTypeError

        with pytest.raises(UnknownStepTypeError) as exc_info:
            DriverRegistry.get_handler("totally_unknown_step_xyz")

        assert "totally_unknown_step_xyz" in str(exc_info.value)

    def test_step_type_spec_retrieval(self):
        """Should retrieve full StepTypeSpec for step type."""
        import quantumvitas.drivers

        from quantumvitas.core.driver_registry import DriverRegistry
        spec = DriverRegistry.get_step_type_spec("qe_scf")
        assert spec.step_type_spec == "qe_scf"  # driver_protocol StepTypeSpec uses 'step_type_spec' field
        assert spec.engine == "qe"
        assert spec.executable == "pw.x"

    def test_engine_for_step_type(self):
        """Should retrieve engine family for step type."""
        import quantumvitas.drivers

        from quantumvitas.core.driver_registry import DriverRegistry
        engine = DriverRegistry.get_engine_for_step_type("qe_scf")
        assert engine == "qe"


class TestMaterialization:
    """Generalized to specific type materialization tests."""

    def test_materialize_known_type(self):
        """Known gen type should materialize to spec type."""
        import quantumvitas.drivers

        from quantumvitas.core.driver_registry import DriverRegistry
        spec_type = DriverRegistry.materialize_step_type("qe", "scf")
        assert spec_type == "qe_scf"

    def test_materialize_unknown_gen_type_raises(self):
        """Unknown gen type should raise UnknownMaterializationError."""
        import quantumvitas.drivers

        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.core.driver_exceptions import UnknownMaterializationError

        with pytest.raises(UnknownMaterializationError) as exc_info:
            DriverRegistry.materialize_step_type("qe", "nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_materialize_unknown_engine_raises(self):
        """Unknown engine should raise UnknownEngineError."""
        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.core.driver_exceptions import UnknownEngineError

        with pytest.raises(UnknownEngineError):
            DriverRegistry.materialize_step_type("nonexistent", "scf")


class TestRecipeRouting:
    """Recipe class routing tests."""

    def test_recipe_class_for_engine(self):
        """Should retrieve recipe class for engine."""
        import quantumvitas.drivers

        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.execution.recipes import BaseRecipe

        recipe_class = DriverRegistry.get_recipe_class("qe")
        assert recipe_class is not None
        assert issubclass(recipe_class, BaseRecipe)

    def test_recipe_class_unknown_engine_raises(self):
        """Unknown engine should raise UnknownEngineError."""
        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.core.driver_exceptions import UnknownEngineError

        with pytest.raises(UnknownEngineError):
            DriverRegistry.get_recipe_class("nonexistent_engine")


class TestDriverValidation:
    """Driver registration validation tests."""

    def setup_method(self):
        """Reset registry before each test."""
        from quantumvitas.core.driver_registry import DriverRegistry
        import importlib
        import sys
        
        # Reset registry first
        DriverRegistry.reset()
        
        # Remove driver modules from sys.modules so they can be re-imported fresh
        modules_to_remove = [
            'quantumvitas.drivers',
            'quantumvitas.drivers.qe',
            'quantumvitas.drivers.vasp',
            'quantumvitas.drivers.lammps',
            'quantumvitas.drivers.cp2k',
            'quantumvitas.drivers.w90',
            'quantumvitas.drivers.orca',
            'quantumvitas.drivers.pyscf',
            'quantumvitas.drivers.qmcpack',
            'quantumvitas.drivers.psi4',
            'quantumvitas.drivers.gpaw',
            'quantumvitas.drivers.siesta',
            'quantumvitas.drivers.xtb',
            'quantumvitas.drivers.yambo',
            'quantumvitas.drivers.abinit',
        ]
        for mod_name in modules_to_remove:
            if mod_name in sys.modules:
                del sys.modules[mod_name]
        
        # Now re-import drivers (they will register themselves)
        import quantumvitas.drivers

    def test_duplicate_engine_rejected(self):
        """Duplicate engine registration should raise."""
        # QE is already registered via drivers/qe/__init__.py
        from quantumvitas.drivers.qe.driver import QEDriver
        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.core.driver_exceptions import DuplicateEngineError

        with pytest.raises(DuplicateEngineError):
            DriverRegistry.register(QEDriver())

    def test_empty_engine_family_rejected(self):
        """Empty engine family should be rejected."""
        from quantumvitas.core.driver_registry import DriverRegistry
        from quantumvitas.core.driver_protocol import StepTypeSpec
        from quantumvitas.core.driver_exceptions import InvalidDriverError

        class BadDriver:
            engine_family = ""
            display_name = "Bad"
            driver_api_version = "1.0.0"

            def get_step_type_specs(self):
                return [StepTypeSpec(id="bad_scf", engine="bad", executable="bad")]

            def get_handler(self):
                return lambda j, c: None

            def get_recipe_class(self):
                return object

            def get_materialization_map(self):
                return {}

        with pytest.raises(InvalidDriverError):
            DriverRegistry.register(BadDriver())


class TestKernelIntegration:
    """Tests that kernel code uses registry."""

    def test_handlers_uses_registry(self):
        """handlers.py should use registry for dispatch."""
        source = (PROJECT_ROOT / "src/quantumvitas/execution/handlers.py").read_text()

        # After refactor, should import and use DriverRegistry
        assert "DriverRegistry" in source or "driver_registry" in source, (
            "handlers.py should use DriverRegistry for dispatch"
        )

    def test_recipes_uses_registry(self):
        """recipes.py should use registry for dispatch."""
        source = (PROJECT_ROOT / "src/quantumvitas/execution/recipes.py").read_text()

        # After refactor, should import and use DriverRegistry
        assert "DriverRegistry" in source or "driver_registry" in source, (
            "recipes.py should use DriverRegistry for dispatch"
        )

