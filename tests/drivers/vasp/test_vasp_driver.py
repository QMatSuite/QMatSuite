"""Tests for VASP driver bundle."""

import pytest
from quantumvitas.drivers.vasp import VASPDriver
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestVASPDriver:
    """Test VASPDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = VASPDriver()
        assert driver.engine_family == "vasp"
        assert driver.display_name == "VASP"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = VASPDriver()
        specs = driver.get_step_type_specs()

        # Check required step types exist
        spec_ids = {s.id for s in specs}
        assert "vasp_scf" in spec_ids
        assert "vasp_relax" in spec_ids
        assert "vasp_md" in spec_ids
        assert "vasp_bands" in spec_ids

        # Check all specs have correct engine
        for spec in specs:
            assert spec.engine == "vasp"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = VASPDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = VASPDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None
        assert hasattr(recipe_class, "materialize")

    def test_materialization_map(self):
        """Test GEN→SPEC mappings."""
        driver = VASPDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["GEN_SCF"] == "vasp_scf"
        assert mat_map["GEN_RELAX"] == "vasp_relax"
        assert mat_map["GEN_MD"] == "vasp_md"

    def test_workdir_policy_cleanup(self):
        """VASP should use CLEANUP policy."""
        driver = VASPDriver()
        assert driver.get_workdir_policy() == WorkdirPolicy.CLEANUP

    def test_md_not_skippable(self):
        """MD steps should not be skippable."""
        driver = VASPDriver()
        assert driver.supports_incremental_skip("vasp_scf") is True
        assert driver.supports_incremental_skip("vasp_md") is False


class TestVASPRegistration:
    """Test VASP driver registration."""

    def test_vasp_registered(self):
        """VASP should be registered in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("vasp")
        driver = DriverRegistry.get_driver("vasp")
        assert driver.engine_family == "vasp"

    def test_vasp_step_types_registered(self):
        """VASP step types should be in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("vasp_scf")
        assert DriverRegistry.is_step_type_registered("vasp_relax")
        assert DriverRegistry.is_step_type_registered("vasp_md")

    def test_vasp_handler_via_registry(self):
        """Should get VASP handler via registry."""
        import quantumvitas.drivers

        handler = DriverRegistry.get_handler("vasp_scf")
        assert callable(handler)

    def test_vasp_recipe_via_registry(self):
        """Should get VASP recipe via registry."""
        import quantumvitas.drivers

        recipe_class = DriverRegistry.get_recipe_class("vasp")
        assert recipe_class is not None


class TestVASPIsolation:
    """Gate 3 tests: VASP isolation from kernel."""

    def test_handlers_no_vasp_handler(self):
        """handlers.py should not contain vasp_step_handler."""
        from pathlib import Path
        # Use absolute path from project root
        handlers_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "handlers.py"
        source = handlers_path.read_text()

        assert "def vasp_step_handler" not in source, (
            "vasp_step_handler should be moved to drivers/vasp/handler.py"
        )

    def test_recipes_no_vasp_recipe(self):
        """recipes.py should not contain VASPRecipe."""
        from pathlib import Path
        # Use absolute path from project root
        recipes_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "recipes.py"
        source = recipes_path.read_text()

        assert "class VASPRecipe" not in source, (
            "VASPRecipe should be moved to drivers/vasp/recipe.py"
        )

    def test_no_vasp_hardcoding_in_kernel(self):
        """Kernel files should not have VASP-specific logic."""
        from pathlib import Path

        kernel_files = [
            "src/quantumvitas/core/calc_identity.py",
            "src/quantumvitas/calculation/step_done.py",
            "src/quantumvitas/calculation/structure_steps.py",
        ]

        for filepath in kernel_files:
            file_path = Path(__file__).parent.parent.parent.parent / filepath
            source = file_path.read_text()
            # Should not have hardcoded VASP step types
            assert "VASP_STEP_TYPES" not in source or "get_step_types" in source, (
                f"{filepath} should not have hardcoded VASP_STEP_TYPES"
            )

