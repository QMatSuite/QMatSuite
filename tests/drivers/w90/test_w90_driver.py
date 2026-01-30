"""Tests for Wannier90 driver bundle."""

import pytest
from pathlib import Path
from quantumvitas.drivers.w90 import W90Driver
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.core.driver_protocol import WorkdirPolicy


class TestW90Driver:
    """Test W90Driver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = W90Driver()
        assert driver.engine_family == "w90"
        assert driver.display_name == "Wannier90"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = W90Driver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.step_type_spec for s in specs}
        assert "w90_run" in spec_ids
        # w90_preproc is NOT in this driver
        assert "w90_preproc" not in spec_ids

        for spec in specs:
            assert spec.engine == "w90"

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = W90Driver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = W90Driver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_cross_engine_capability(self):
        """W90 should have cross_engine capability."""
        driver = W90Driver()
        assert "cross_engine" in driver.get_capabilities()

    def test_materialization_map(self):
        """W90 has GEN_WANNIER mapping (SSOT for Wannier steps)."""
        driver = W90Driver()
        mat_map = driver.get_materialization_map()
        assert mat_map == {"GEN_WANNIER": "w90_run"}


class TestW90Registration:
    """Test W90 driver registration."""

    def test_w90_registered(self):
        """W90 should be registered in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_engine_registered("w90")
        driver = DriverRegistry.get_driver("w90")
        assert driver.engine_family == "w90"

    def test_w90_run_registered(self):
        """w90_run step type should be in registry."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("w90_run")

    def test_w90_preproc_in_qe(self):
        """w90_preproc should be registered with QE."""
        import quantumvitas.drivers

        assert DriverRegistry.is_step_type_registered("w90_preproc")
        engine = DriverRegistry.get_engine_for_step_type("w90_preproc")
        assert engine == "qe"  # Preprocessing runs via QE


class TestW90Isolation:
    """Gate 3 tests: W90 isolation from kernel."""

    def test_w90_driver_exists(self):
        """W90 driver package should exist."""
        from quantumvitas.drivers.w90 import W90Driver
        assert W90Driver is not None


class TestW90ArtifactResolver:
    """Tests for W90 artifact resolution."""

    def test_find_artifacts(self, tmp_path):
        """Test finding W90 artifacts in directory."""
        from quantumvitas.drivers.w90.artifact_resolver import _find_artifacts_in_dir

        # Create mock artifact files
        (tmp_path / "wannier90.amn").touch()
        (tmp_path / "wannier90.mmn").touch()
        (tmp_path / "wannier90.eig").touch()

        found = _find_artifacts_in_dir(
            tmp_path,
            ["w90_amn", "w90_mmn", "w90_eig"]
        )

        assert len(found) == 3
        assert "w90_amn" in found
        assert "w90_mmn" in found
        assert "w90_eig" in found

    def test_missing_artifacts(self, tmp_path):
        """Test partial artifacts found."""
        from quantumvitas.drivers.w90.artifact_resolver import _find_artifacts_in_dir

        # Only create one artifact
        (tmp_path / "wannier90.amn").touch()

        found = _find_artifacts_in_dir(
            tmp_path,
            ["w90_amn", "w90_mmn", "w90_eig"]
        )

        assert len(found) == 1
        assert "w90_amn" in found


class TestW90Recipe:
    """Tests for W90 recipe."""

    def test_win_file_generation(self, tmp_path):
        """Test .win file generation."""
        from quantumvitas.drivers.w90.recipe import W90Recipe

        recipe = W90Recipe()
        config = {
            "seedname": "test",
            "num_wann": 4,
            "num_bands": 8,
            "mp_grid": [4, 4, 4],
            "projections": ["Si:sp3"],
        }

        recipe.stage(tmp_path, config)

        win_path = tmp_path / "test.win"
        assert win_path.exists()

        content = win_path.read_text()
        assert "num_wann = 4" in content
        assert "num_bands = 8" in content
        assert "mp_grid = 4 4 4" in content
        assert "Si:sp3" in content

