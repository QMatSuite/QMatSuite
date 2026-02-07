"""Tests for Gaussian driver bundle.

Covers the 7-item MUST interface, registry registration,
and kernel isolation gates.
"""

import pytest
from quantumvitas.drivers.gaussian import GaussianDriver
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestGaussianDriver:
    """Test GaussianDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = GaussianDriver()
        assert driver.engine_family == "gaussian"
        assert driver.display_name == "Gaussian"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = GaussianDriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.step_type_spec for s in specs}
        assert "gaussian_scf" in spec_ids
        assert "gaussian_relax" in spec_ids
        assert "gaussian_freq" in spec_ids
        assert "gaussian_mp2" in spec_ids
        assert "gaussian_td" in spec_ids

        for spec in specs:
            assert spec.engine == "gaussian"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = GaussianDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = GaussianDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test gen->spec mappings."""
        driver = GaussianDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["scf"] == "gaussian_scf"
        assert mat_map["relax"] == "gaussian_relax"

    def test_workdir_policy_isolated(self):
        """Gaussian should use ISOLATED policy."""
        driver = GaussianDriver()
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED

    def test_capabilities(self):
        """Gaussian should have molecular capability."""
        driver = GaussianDriver()
        caps = driver.get_capabilities()
        assert "molecular" in caps
        assert "scf" in caps
        assert "relax" in caps

    def test_input_spec(self):
        """Test input spec is returned and properly configured."""
        driver = GaussianDriver()
        spec = driver.get_input_spec()
        assert spec is not None
        assert spec.engine_family == "gaussian"
        assert spec.syntax_family == "keyword-block"
        assert len(spec.input_files) == 1
        assert spec.input_files[0].filename == "input.gjf"
        assert spec.input_files[0].content_role == "combined"

    def test_artifact_patterns(self):
        """Test artifact pattern definitions."""
        driver = GaussianDriver()
        patterns = driver.get_artifact_patterns()
        assert "input" in patterns
        assert "output" in patterns
        assert "checkpoint" in patterns


class TestGaussianRegistration:
    """Test Gaussian driver registration."""

    def test_gaussian_registered(self):
        """Gaussian should be registered in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("gaussian")
        driver = DriverRegistry.get_driver("gaussian")
        assert driver.engine_family == "gaussian"

    def test_gaussian_step_types_registered(self):
        """Gaussian step types should be in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("gaussian_scf")
        assert DriverRegistry.is_step_type_registered("gaussian_relax")
        assert DriverRegistry.is_step_type_registered("gaussian_freq")

    def test_gaussian_handler_via_registry(self):
        """Should get Gaussian handler via registry."""
        import quantumvitas.drivers

        handler = DriverRegistry.get_handler("gaussian_scf")
        assert callable(handler)


class TestGaussianIsolation:
    """Gate tests: Gaussian isolation from kernel."""

    def test_handlers_no_gaussian_handler(self):
        """handlers.py should not contain gaussian_step_handler."""
        from pathlib import Path

        handlers_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "quantumvitas"
            / "execution"
            / "handlers.py"
        )
        source = handlers_path.read_text()

        assert "def gaussian_step_handler" not in source, (
            "gaussian_step_handler should be in drivers/gaussian/handler.py"
        )

    def test_recipes_no_gaussian_recipe(self):
        """recipes.py should not contain GaussianRecipe."""
        from pathlib import Path

        recipes_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "quantumvitas"
            / "execution"
            / "recipes.py"
        )
        source = recipes_path.read_text()

        assert "class GaussianRecipe" not in source, (
            "GaussianRecipe should be in drivers/gaussian/recipe.py"
        )

    def test_io_module_no_kernel_imports(self):
        """io/gaussian_input.py must not import kernel modules."""
        from pathlib import Path

        io_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "quantumvitas"
            / "drivers"
            / "gaussian"
            / "io"
            / "gaussian_input.py"
        )
        source = io_path.read_text()

        # Must not import from kernel, core, calculation, etc.
        for forbidden in [
            "from quantumvitas.core",
            "from quantumvitas.calculation",
            "from quantumvitas.execution",
            "from quantumvitas.api",
            "import quantumvitas.core",
        ]:
            assert forbidden not in source, (
                f"io/gaussian_input.py must not import '{forbidden}' (leaf package rule P5)"
            )

    def test_metadata_module_no_kernel_imports(self):
        """data/gaussian_metadata.py must not import kernel modules."""
        from pathlib import Path

        meta_path = (
            Path(__file__).parent.parent.parent.parent
            / "src"
            / "quantumvitas"
            / "drivers"
            / "gaussian"
            / "data"
            / "gaussian_metadata.py"
        )
        source = meta_path.read_text()

        for forbidden in [
            "from quantumvitas.core",
            "from quantumvitas.calculation",
            "from quantumvitas.execution",
        ]:
            assert forbidden not in source, (
                f"data/gaussian_metadata.py must not import '{forbidden}' (leaf package rule P5)"
            )
