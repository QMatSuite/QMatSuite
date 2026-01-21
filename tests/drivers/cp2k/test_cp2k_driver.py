"""Tests for CP2K driver bundle."""

import pytest
from quantumvitas.drivers.cp2k import CP2KDriver
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestCP2KDriver:
    """Test CP2KDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = CP2KDriver()
        assert driver.engine_family == "cp2k"
        assert driver.display_name == "CP2K"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = CP2KDriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.id for s in specs}
        assert "cp2k_scf" in spec_ids
        assert "cp2k_relax" in spec_ids
        assert "cp2k_md" in spec_ids

        for spec in specs:
            assert spec.engine == "cp2k"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = CP2KDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = CP2KDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test GEN→SPEC mappings."""
        driver = CP2KDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["GEN_SCF"] == "cp2k_scf"
        assert mat_map["GEN_MD"] == "cp2k_md"

    def test_md_not_skippable(self):
        """MD steps should not be skippable."""
        driver = CP2KDriver()
        assert driver.supports_incremental_skip("cp2k_scf") is True
        assert driver.supports_incremental_skip("cp2k_md") is False


class TestCP2KRegistration:
    """Test CP2K driver registration."""

    def test_cp2k_registered(self):
        """CP2K should be registered in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("cp2k")
        driver = DriverRegistry.get_driver("cp2k")
        assert driver.engine_family == "cp2k"

    def test_cp2k_step_types_registered(self):
        """CP2K step types should be in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("cp2k_scf")
        assert DriverRegistry.is_step_type_registered("cp2k_relax")


class TestCP2KIsolation:
    """Gate 3 tests: CP2K isolation from kernel."""

    def test_handlers_no_cp2k_handler(self):
        """handlers.py should not contain cp2k_step_handler."""
        from pathlib import Path
        handlers_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "handlers.py"
        source = handlers_path.read_text()

        assert "def cp2k_step_handler" not in source

    def test_recipes_no_cp2k_recipe(self):
        """recipes.py should not contain CP2KRecipe."""
        from pathlib import Path
        recipes_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "recipes.py"
        source = recipes_path.read_text()

        assert "class CP2KRecipe" not in source

