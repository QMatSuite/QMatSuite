"""Tests for PySCF driver bundle."""

import pytest
from qmatsuite.drivers.pyscf import PySCFDriver
from qmatsuite.core.driver_registry import DriverRegistry
from qmatsuite.core.driver_protocol import WorkdirPolicy


class TestPySCFDriver:
    """Test PySCFDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = PySCFDriver()
        assert driver.engine_family == "pyscf"
        assert driver.display_name == "PySCF"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = PySCFDriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.step_type_spec for s in specs}
        assert "pyscf_scf" in spec_ids
        assert "pyscf_opt" in spec_ids
        assert "pyscf_mp2" in spec_ids

        for spec in specs:
            assert spec.engine == "pyscf"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = PySCFDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = PySCFDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test gen→spec mappings."""
        driver = PySCFDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["scf"] == "pyscf_scf"
        assert mat_map["relax"] == "pyscf_relax"

    def test_python_native_capability(self):
        """PySCF should have python_native capability."""
        driver = PySCFDriver()
        assert "python_native" in driver.get_capabilities()


class TestPySCFRegistration:
    """Test PySCF driver registration."""

    def test_pyscf_registered(self):
        """PySCF should be registered in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_engine_registered("pyscf")
        driver = DriverRegistry.get_driver("pyscf")
        assert driver.engine_family == "pyscf"

    def test_pyscf_step_types_registered(self):
        """PySCF step types should be in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_step_type_registered("pyscf_scf")
        assert DriverRegistry.is_step_type_registered("pyscf_opt")


class TestPySCFIsolation:
    """Gate 3 tests: PySCF isolation from kernel."""

    def test_handlers_no_pyscf_handler(self):
        """handlers.py should not contain pyscf_chain_handler."""
        from pathlib import Path
        # Use absolute path from project root
        handlers_path = Path(__file__).parent.parent.parent.parent / "src" / "qmatsuite" / "execution" / "handlers.py"
        source = handlers_path.read_text()

        assert "def pyscf_chain_handler" not in source, (
            "pyscf_chain_handler should be moved to drivers/pyscf/handler.py"
        )

    def test_recipes_no_pyscf_recipe(self):
        """recipes.py should not contain PySCFRecipe."""
        from pathlib import Path
        # Use absolute path from project root
        recipes_path = Path(__file__).parent.parent.parent.parent / "src" / "qmatsuite" / "execution" / "recipes.py"
        source = recipes_path.read_text()

        assert "class PySCFRecipe" not in source, (
            "PySCFRecipe should be moved to drivers/pyscf/recipe.py"
        )

