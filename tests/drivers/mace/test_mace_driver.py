"""Tests for MACE driver bundle."""

from __future__ import annotations

from pathlib import Path

from qmatsuite.core.driver_protocol import WorkdirPolicy
from qmatsuite.core.driver_registry import DriverRegistry
from qmatsuite.drivers.mace import MACEDriver


class TestMACEDriverProperties:
    def test_engine_family(self):
        driver = MACEDriver()
        assert driver.engine_family == "mace"

    def test_display_name(self):
        driver = MACEDriver()
        assert driver.display_name == "MACE"

    def test_driver_api_version(self):
        driver = MACEDriver()
        assert driver.driver_api_version == "1.0.0"

    def test_prefix(self):
        driver = MACEDriver()
        assert driver.PREFIX == "mace"

    def test_supported_gen_steps(self):
        driver = MACEDriver()
        assert driver.SUPPORTED_GEN_STEPS == frozenset({"scf", "relax", "md"})


class TestMACEDriverMethods:
    def test_step_type_specs_scf(self):
        driver = MACEDriver()
        specs = driver.get_step_type_specs()
        scf_specs = [s for s in specs if s.step_type_spec == "mace_scf"]
        assert len(scf_specs) == 1
        assert scf_specs[0].engine == "mace"
        assert scf_specs[0].executable == "python"
        assert scf_specs[0].supports_restart is False

    def test_step_type_specs_relax(self):
        driver = MACEDriver()
        specs = driver.get_step_type_specs()
        assert any(s.step_type_spec == "mace_relax" for s in specs)

    def test_step_type_specs_md(self):
        driver = MACEDriver()
        specs = driver.get_step_type_specs()
        assert any(s.step_type_spec == "mace_md" for s in specs)

    def test_handler_callable(self):
        driver = MACEDriver()
        assert callable(driver.get_handler())

    def test_recipe_class(self):
        driver = MACEDriver()
        cls = driver.get_recipe_class()
        assert cls is not None
        assert cls.__name__ == "MACERecipe"

    def test_input_spec(self):
        driver = MACEDriver()
        spec = driver.get_input_spec()
        assert spec.engine_family == "mace"
        assert spec.syntax_family == "python-script"
        names = [f.filename for f in spec.input_files]
        assert "structure.json" in names

    def test_workdir_policy(self):
        driver = MACEDriver()
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED

    def test_capabilities(self):
        driver = MACEDriver()
        caps = driver.get_capabilities()
        assert "scf" in caps
        assert "relax" in caps
        assert "md" in caps


class TestMACERegistration:
    def test_mace_registered(self):
        import qmatsuite.drivers  # noqa: F401
        assert DriverRegistry.is_engine_registered("mace")
        driver = DriverRegistry.get_driver("mace")
        assert driver.engine_family == "mace"

    def test_mace_step_types_registered(self):
        import qmatsuite.drivers  # noqa: F401
        assert DriverRegistry.is_step_type_registered("mace_scf")
        assert DriverRegistry.is_step_type_registered("mace_relax")
        assert DriverRegistry.is_step_type_registered("mace_md")


class TestMACELeafIsolation:
    def test_io_module_no_kernel_imports(self):
        io_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "qmatsuite"
            / "drivers"
            / "mace"
            / "io"
            / "mace_script.py"
        )
        source = io_path.read_text(encoding="utf-8")
        forbidden = [
            "from qmatsuite.core",
            "from qmatsuite.calculation",
            "from qmatsuite.execution",
            "from qmatsuite.api",
        ]
        for text in forbidden:
            assert text not in source, f"Forbidden import '{text}' found in mace_script.py"

    def test_metadata_module_no_kernel_imports(self):
        meta_path = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "qmatsuite"
            / "drivers"
            / "mace"
            / "data"
            / "mace_metadata.py"
        )
        source = meta_path.read_text(encoding="utf-8")
        forbidden = [
            "from qmatsuite.core",
            "from qmatsuite.calculation",
            "from qmatsuite.execution",
            "from qmatsuite.api",
        ]
        for text in forbidden:
            assert text not in source, f"Forbidden import '{text}' found in mace_metadata.py"
