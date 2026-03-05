"""
Tests for generic engine RPCs (M4).

These test the RPC handler logic directly, not through the daemon socket.
"""
import pytest

from qmatsuite.core.driver_registry import DriverRegistry
import qmatsuite.drivers


class TestListEngineFamilies:
    """Test list_engine_families RPC."""

    def test_returns_all_16_engines(self):
        engines = sorted(DriverRegistry.get_all_engines())
        assert len(engines) == 16

    def test_engine_has_required_fields(self):
        for family in DriverRegistry.get_all_engines():
            driver = DriverRegistry.get_driver(family)
            assert hasattr(driver, 'display_name')
            assert hasattr(driver, 'ENGINE_ROLE')
            assert hasattr(driver, 'COMPANION_ENGINES')
            assert hasattr(driver, 'SUPPORTED_GEN_STEPS')

    def test_qe_has_companions(self):
        driver = DriverRegistry.get_driver("qe")
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        assert "w90" in companions
        assert "qmcpack" in companions
        assert "yambo" in companions

    def test_postproc_engines_have_correct_role(self):
        for family in ["w90", "qmcpack", "yambo"]:
            driver = DriverRegistry.get_driver(family)
            assert getattr(driver, 'ENGINE_ROLE', 'base') == 'postprocessing'


class TestListStepPalette:
    """Test list_step_palette RPC logic."""

    def test_qe_palette_has_base_steps(self):
        driver = DriverRegistry.get_driver("qe")
        supported = getattr(driver, 'SUPPORTED_GEN_STEPS', set())
        assert "scf" in supported
        assert "nscf" in supported
        assert "relax" in supported

    def test_qe_palette_has_companions(self):
        driver = DriverRegistry.get_driver("qe")
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        assert len(companions) == 3

    def test_vasp_palette_has_no_companions(self):
        driver = DriverRegistry.get_driver("vasp")
        companions = getattr(driver, 'COMPANION_ENGINES', frozenset())
        assert len(companions) == 0

    def test_undecided_returns_empty(self):
        """UNDECIDED (engine_family=None) returns no base steps."""
        # This tests the logic that the handler implements
        # When engine_family is None, base_steps and companion_steps are empty
        pass  # Handler-level test would mock the daemon


class TestResolveCompanionStep:
    """Test DriverRegistry.resolve_companion_step (added in M3)."""

    def test_qe_scf(self):
        assert DriverRegistry.resolve_companion_step("qe", "scf") == "qe_scf"

    def test_qe_wannierprep(self):
        assert DriverRegistry.resolve_companion_step("qe", "wannierprep") == "w90_wannierprep"

    def test_qe_postwannier(self):
        assert DriverRegistry.resolve_companion_step("qe", "postwannier") == "w90_postwannier"

    def test_vasp_no_companions(self):
        assert DriverRegistry.resolve_companion_step("vasp", "wannierprep") is None


