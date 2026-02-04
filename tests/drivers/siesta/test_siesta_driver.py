"""Unit tests for the Siesta driver bundle.

Tests driver protocol compliance, step type registration,
and handler/recipe retrieval via DriverRegistry.
"""

from __future__ import annotations

import pytest

from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestSiestaDriverProtocol:
    """Verify SiestaDriver implements the 7-item MUST interface."""

    def test_driver_imports_and_registers(self):
        """Driver is importable and registers with DriverRegistry."""
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("siesta")
        assert driver is not None

    def test_engine_family(self):
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("siesta")
        assert driver.engine_family == "siesta"

    def test_display_name(self):
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("siesta")
        assert driver.display_name == "Siesta"

    def test_driver_api_version(self):
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("siesta")
        assert driver.driver_api_version == "1.0.0"

    def test_prefix_and_supported_gen_steps(self):
        from quantumvitas.drivers.siesta.driver import SiestaDriver

        assert SiestaDriver.PREFIX == "siesta"
        assert SiestaDriver.SUPPORTED_GEN_STEPS == frozenset({
            "scf", "relax", "md", "bands", "dos",
        })

    def test_workdir_policy_is_isolated(self):
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("siesta")
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED


class TestSiestaStepTypeSpecs:
    """Verify step type specs are correctly defined and registered."""

    def test_all_step_types_registered(self):
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        expected_specs = [
            "siesta_scf", "siesta_relax", "siesta_md",
            "siesta_bands", "siesta_dos",
        ]
        for spec_name in expected_specs:
            spec = DriverRegistry.get_step_type_spec(spec_name)
            assert spec is not None, f"Step type {spec_name} not registered"
            assert spec.engine == "siesta"
            assert spec.executable == "siesta"

    def test_step_type_specs_have_correct_prefix(self):
        from quantumvitas.drivers.siesta.driver import SiestaDriver

        driver = SiestaDriver()
        for spec in driver.get_step_type_specs():
            assert spec.step_type_spec.startswith("siesta_"), (
                f"{spec.step_type_spec} does not start with siesta_"
            )

    def test_materialization_map(self):
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("siesta")
        mat_map = driver.get_materialization_map()
        assert mat_map["scf"] == "siesta_scf"
        assert mat_map["relax"] == "siesta_relax"
        assert mat_map["md"] == "siesta_md"
        assert mat_map["bands"] == "siesta_bands"
        assert mat_map["dos"] == "siesta_dos"


class TestSiestaHandlerAndRecipe:
    """Verify handler and recipe are retrievable."""

    def test_get_handler(self):
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        handler = DriverRegistry.get_handler("siesta_scf")
        assert handler is not None
        assert callable(handler)

    def test_get_recipe_class(self):
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        recipe_cls = DriverRegistry.get_recipe_class("siesta")
        assert recipe_cls is not None
        from quantumvitas.execution.recipes import BaseRecipe
        assert issubclass(recipe_cls, BaseRecipe)

    def test_handler_same_for_all_step_types(self):
        """All siesta step types should use the same handler."""
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        handlers = set()
        for spec_name in ["siesta_scf", "siesta_relax", "siesta_md"]:
            h = DriverRegistry.get_handler(spec_name)
            handlers.add(h)
        assert len(handlers) == 1, "All Siesta step types should share one handler"


class TestSiestaCapabilities:
    """Verify capabilities and other optional methods."""

    def test_capabilities(self):
        from quantumvitas.drivers.siesta.driver import SiestaDriver

        driver = SiestaDriver()
        caps = driver.get_capabilities()
        assert "scf" in caps
        assert "relax" in caps
        assert "periodic" in caps
        assert "mpi" in caps

    def test_md_not_skippable(self):
        from quantumvitas.drivers.siesta.driver import SiestaDriver

        driver = SiestaDriver()
        assert driver.supports_incremental_skip("siesta_scf") is True
        assert driver.supports_incremental_skip("siesta_md") is False

    def test_artifact_patterns(self):
        from quantumvitas.drivers.siesta.driver import SiestaDriver

        driver = SiestaDriver()
        patterns = driver.get_artifact_patterns()
        assert "restart" in patterns
        assert "log" in patterns
