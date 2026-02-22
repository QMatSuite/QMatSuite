"""Tests for xTB driver bundle."""

from __future__ import annotations

from pathlib import Path

from qmatsuite.core.driver_protocol import WorkdirPolicy
from qmatsuite.core.driver_registry import DriverRegistry
from qmatsuite.drivers.xtb import XTBDriver


class TestXTBDriver:
    def test_driver_properties(self):
        driver = XTBDriver()
        assert driver.engine_family == "xtb"
        assert driver.display_name == "xTB"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        driver = XTBDriver()
        specs = driver.get_step_type_specs()
        assert any(s.step_type_spec == "xtb_relax" for s in specs)

    def test_handler_callable(self):
        driver = XTBDriver()
        assert callable(driver.get_handler())

    def test_recipe_class(self):
        driver = XTBDriver()
        assert driver.get_recipe_class() is not None

    def test_input_spec(self):
        driver = XTBDriver()
        spec = driver.get_input_spec()
        assert spec.engine_family == "xtb"
        assert spec.syntax_family == "dollar-flag"
        names = [f.filename for f in spec.input_files]
        assert "input.xyz" in names
        assert "xcontrol.inp" in names

    def test_workdir_policy(self):
        driver = XTBDriver()
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED


class TestXTBRegistration:
    def test_xtb_registered(self):
        import qmatsuite.drivers  # noqa: F401

        assert DriverRegistry.is_engine_registered("xtb")
        driver = DriverRegistry.get_driver("xtb")
        assert driver.engine_family == "xtb"

    def test_xtb_step_type_registered(self):
        import qmatsuite.drivers  # noqa: F401

        assert DriverRegistry.is_step_type_registered("xtb_relax")


class TestXTBLeafIsolation:
    def test_io_module_no_kernel_imports(self):
        io_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "qmatsuite"
            / "drivers"
            / "xtb"
            / "io"
            / "xtb_input.py"
        )
        source = io_path.read_text(encoding="utf-8")
        forbidden = [
            "from qmatsuite.core",
            "from qmatsuite.calculation",
            "from qmatsuite.execution",
            "from qmatsuite.api",
        ]
        for text in forbidden:
            assert text not in source

    def test_metadata_module_no_kernel_imports(self):
        meta_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "qmatsuite"
            / "drivers"
            / "xtb"
            / "data"
            / "xtb_metadata.py"
        )
        source = meta_path.read_text(encoding="utf-8")
        forbidden = [
            "from qmatsuite.core",
            "from qmatsuite.calculation",
            "from qmatsuite.execution",
            "from qmatsuite.api",
        ]
        for text in forbidden:
            assert text not in source
