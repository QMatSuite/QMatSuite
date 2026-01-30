"""Tests for ORCA driver bundle."""

import pytest
from quantumvitas.drivers.orca import ORCADriver
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestORCADriver:
    """Test ORCADriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = ORCADriver()
        assert driver.engine_family == "orca"
        assert driver.display_name == "ORCA"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = ORCADriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.step_type_spec for s in specs}
        assert "orca_scf" in spec_ids
        assert "orca_opt" in spec_ids
        assert "orca_freq" in spec_ids

        for spec in specs:
            assert spec.engine == "orca"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = ORCADriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = ORCADriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test GEN→SPEC mappings."""
        driver = ORCADriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["GEN_SCF"] == "orca_scf"
        assert mat_map["GEN_OPT"] == "orca_opt"

    def test_workdir_policy_isolated(self):
        """ORCA should use ISOLATED policy (default)."""
        driver = ORCADriver()
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED

    def test_chain_capability(self):
        """ORCA should have chain capability."""
        driver = ORCADriver()
        assert "chain" in driver.get_capabilities()


class TestORCARegistration:
    """Test ORCA driver registration."""

    def test_orca_registered(self):
        """ORCA should be registered in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("orca")
        driver = DriverRegistry.get_driver("orca")
        assert driver.engine_family == "orca"

    def test_orca_step_types_registered(self):
        """ORCA step types should be in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("orca_scf")
        assert DriverRegistry.is_step_type_registered("orca_opt")

    def test_orca_handler_via_registry(self):
        """Should get ORCA handler via registry."""
        import quantumvitas.drivers

        handler = DriverRegistry.get_handler("orca_scf")
        assert callable(handler)


class TestORCAIsolation:
    """Gate 3 tests: ORCA isolation from kernel."""

    def test_handlers_no_orca_handler(self):
        """handlers.py should not contain orca_chain_handler."""
        from pathlib import Path
        # Use absolute path from project root
        handlers_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "handlers.py"
        source = handlers_path.read_text()

        assert "def orca_chain_handler" not in source, (
            "orca_chain_handler should be moved to drivers/orca/handler.py"
        )

    def test_recipes_no_orca_recipe(self):
        """recipes.py should not contain ORCARecipe."""
        from pathlib import Path
        # Use absolute path from project root
        recipes_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "recipes.py"
        source = recipes_path.read_text()

        assert "class ORCARecipe" not in source, (
            "ORCARecipe should be moved to drivers/orca/recipe.py"
        )

