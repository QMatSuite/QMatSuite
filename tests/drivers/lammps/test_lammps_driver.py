"""Tests for LAMMPS driver bundle."""

import pytest
from quantumvitas.drivers.lammps import LAMMPSDriver
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestLAMMPSDriver:
    """Test LAMMPSDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = LAMMPSDriver()
        assert driver.engine_family == "lammps"
        assert driver.display_name == "LAMMPS"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = LAMMPSDriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.step_type_spec for s in specs}
        assert "lammps_minimize" in spec_ids
        assert "lammps_md" in spec_ids
        assert "lammps_npt" in spec_ids

        for spec in specs:
            assert spec.engine == "lammps"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = LAMMPSDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = LAMMPSDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test GEN→SPEC mappings."""
        driver = LAMMPSDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["GEN_MD"] == "lammps_md"
        assert mat_map["GEN_MINIMIZE"] == "lammps_minimize"

    def test_md_not_skippable(self):
        """MD steps should not be skippable."""
        driver = LAMMPSDriver()
        assert driver.supports_incremental_skip("lammps_minimize") is True
        assert driver.supports_incremental_skip("lammps_md") is False
        assert driver.supports_incremental_skip("lammps_npt") is False

    def test_restart_capability(self):
        """LAMMPS should have restart capability."""
        driver = LAMMPSDriver()
        assert "restart" in driver.get_capabilities()


class TestLAMMPSRegistration:
    """Test LAMMPS driver registration."""

    def test_lammps_registered(self):
        """LAMMPS should be registered in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("lammps")
        driver = DriverRegistry.get_driver("lammps")
        assert driver.engine_family == "lammps"

    def test_lammps_step_types_registered(self):
        """LAMMPS step types should be in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("lammps_minimize")
        assert DriverRegistry.is_step_type_registered("lammps_md")


class TestLAMMPSIsolation:
    """Gate 3 tests: LAMMPS isolation from kernel."""

    def test_handlers_no_lammps_handler(self):
        """handlers.py should not contain lammps_step_handler."""
        from pathlib import Path
        handlers_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "handlers.py"
        source = handlers_path.read_text()

        assert "def lammps_step_handler" not in source

    def test_recipes_no_lammps_recipe(self):
        """recipes.py should not contain LAMMPSRecipe."""
        from pathlib import Path
        recipes_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "recipes.py"
        source = recipes_path.read_text()

        assert "class LAMMPSRecipe" not in source


class TestLAMMPSRestart:
    """Tests for LAMMPS restart handling."""

    def test_find_restart_file(self, tmp_path):
        """Test finding latest restart file."""
        from quantumvitas.drivers.lammps.restart import find_restart_file
        import time

        # Create mock restart files (LAMMPS uses restart*.bin pattern typically)
        (tmp_path / "restart.1000.bin").touch()
        time.sleep(0.01)
        (tmp_path / "restart.2000.bin").touch()

        latest = find_restart_file(tmp_path, pattern="restart*.bin")
        assert latest is not None
        assert latest.name == "restart.2000.bin"

    def test_find_restart_file_none(self, tmp_path):
        """Test no restart file found."""
        from quantumvitas.drivers.lammps.restart import find_restart_file

        result = find_restart_file(tmp_path)
        assert result is None

