"""Tests for ABINIT driver bundle: registration, isolation, inputspec.

Validates that the ABINIT driver is properly registered, its modules
have no kernel imports, and the inputspec roundtrips correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestABINITDriverRegistration:
    """Verify ABINIT driver is registered and accessible."""

    def test_driver_in_registry(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("abinit")
        assert driver is not None

    def test_engine_family(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("abinit")
        assert driver.engine_family == "abinit"

    def test_prefix(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("abinit")
        assert driver.PREFIX == "abinit"

    def test_supported_gen_steps(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("abinit")
        gen_steps = driver.SUPPORTED_GEN_STEPS
        assert "scf" in gen_steps
        assert "relax" in gen_steps

    def test_get_handler(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("abinit")
        handler = driver.get_handler()
        assert handler is not None

    def test_get_recipe_class(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("abinit")
        recipe_cls = driver.get_recipe_class()
        assert recipe_cls is not None


class TestABINITDriverIsolation:
    """Verify no kernel imports in leaf modules."""

    def test_io_module_no_kernel(self):
        """abinit_input.py should only use stdlib."""
        import importlib
        mod = importlib.import_module("quantumvitas.drivers.abinit.io.abinit_input")
        # Check it doesn't import kernel modules
        source = open(mod.__file__, "r").read()
        assert "quantumvitas.kernel" not in source
        assert "quantumvitas.runner" not in source
        assert "quantumvitas.daemon" not in source

    def test_parsers_output_no_kernel(self):
        """output.py should only import registry."""
        import importlib
        mod = importlib.import_module("quantumvitas.drivers.abinit.parsers.output")
        source = open(mod.__file__, "r").read()
        assert "quantumvitas.kernel" not in source
        assert "quantumvitas.runner" not in source

    def test_metadata_no_kernel(self):
        """abinit_metadata.py should only use stdlib."""
        import importlib
        mod = importlib.import_module("quantumvitas.drivers.abinit.data.abinit_metadata")
        source = open(mod.__file__, "r").read()
        assert "quantumvitas.kernel" not in source
        assert "quantumvitas.runner" not in source


class TestABINITInputSpec:
    """Verify inputspec wiring."""

    def test_get_input_spec_returns_spec(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("abinit")
        spec = driver.get_input_spec()
        assert spec is not None

    def test_input_spec_has_abi_file(self):
        from quantumvitas.core.driver_registry import DriverRegistry
        driver = DriverRegistry.get_driver("abinit")
        spec = driver.get_input_spec()
        # ABINIT uses a single .abi combined file
        assert len(spec.input_files) >= 1
        filenames = [f.filename for f in spec.input_files]
        abi_files = [f for f in filenames if f.endswith(".abi")]
        assert len(abi_files) >= 1


class TestABINITIOModule:
    """Test the extracted io/abinit_input.py parse/write functions."""

    def test_parse_basic_input(self):
        from quantumvitas.drivers.abinit.io.abinit_input import parse_abinit_text
        text = """\
# Test input
ecut 10
natom 2
ntypat 1
typat 1 1
znucl 14
acell 3*10.26
rprim
  0.0  0.5  0.5
  0.5  0.0  0.5
  0.5  0.5  0.0
xred
  0.0  0.0  0.0
  0.25 0.25 0.25
nstep 30
toldfe 1.0d-8
"""
        result = parse_abinit_text(text)
        assert "params" in result
        assert "structure" in result
        assert result["params"]["ecut"] == 10
        assert result["params"]["nstep"] == 30
        assert result["params"]["toldfe"] == pytest.approx(1e-8)
        assert result["structure"]["species"] == ["Si", "Si"]
        assert len(result["structure"]["frac_coords"]) == 2
        assert result["structure"]["lattice"] is not None

    def test_write_roundtrip(self):
        from quantumvitas.drivers.abinit.io.abinit_input import (
            parse_abinit_text, write_abinit_text,
        )
        text = """\
ecut 10
natom 2
ntypat 1
typat 1 1
znucl 14
acell 3*10.26
rprim
  0.0  0.5  0.5
  0.5  0.0  0.5
  0.5  0.5  0.0
xred
  0.0  0.0  0.0
  0.25 0.25 0.25
nstep 30
toldfe 1.0d-8
"""
        parsed = parse_abinit_text(text)
        written = write_abinit_text({
            "params": parsed["params"],
            "structure": parsed["structure"],
        })
        reparsed = parse_abinit_text(written)
        assert reparsed["params"]["ecut"] == 10
        assert reparsed["params"]["nstep"] == 30
        assert reparsed["structure"]["species"] == ["Si", "Si"]

    def test_star_expansion(self):
        from quantumvitas.drivers.abinit.io.abinit_input import parse_abinit_text
        text = "acell 3*10.26\nrprim\n1.0 0.0 0.0\n0.0 1.0 0.0\n0.0 0.0 1.0\n"
        result = parse_abinit_text(text)
        # acell 3*10.26 expands to [10.26, 10.26, 10.26]
        # rprim is stored as raw dimensionless matrix (writer applies acell)
        assert result["structure"]["lattice"] is not None
        assert result["structure"]["lattice"][0][0] == pytest.approx(1.0)
        assert result["structure"]["lattice"][1][1] == pytest.approx(1.0)

    def test_fortran_d_notation(self):
        from quantumvitas.drivers.abinit.io.abinit_input import parse_abinit_text
        text = "toldfe 1.0d-8\nnstep 30\n"
        result = parse_abinit_text(text)
        assert result["params"]["toldfe"] == pytest.approx(1e-8)

    def test_comment_stripping(self):
        from quantumvitas.drivers.abinit.io.abinit_input import parse_abinit_text
        text = "ecut 10 # this is a comment\nnstep 30 ! another comment\n"
        result = parse_abinit_text(text)
        assert result["params"]["ecut"] == 10
        assert result["params"]["nstep"] == 30


class TestABINITCorpusParse:
    """Parse all curated cases to verify no crashes."""

    SAMPLES_DIR = Path(__file__).resolve().parents[2] / "inputformat" / "samples" / "abinit"

    @pytest.fixture(params=[
        "si_scf", "si_relax", "si_bands", "si_dos", "si_spin",
        "al_scf", "si_dfpt", "si_vcrelax", "fe_magnetic", "si_paw",
    ])
    def case_dir(self, request):
        d = self.SAMPLES_DIR / request.param
        if not d.exists():
            pytest.skip(f"Sample {request.param} not found")
        return d

    def test_parse_no_crash(self, case_dir):
        """Each curated .abi file parses without error."""
        from quantumvitas.drivers.abinit.io.abinit_input import parse_abinit_text
        abi_files = list(case_dir.glob("*.abi"))
        assert len(abi_files) >= 1, f"No .abi file in {case_dir}"
        for abi_file in abi_files:
            text = abi_file.read_text()
            result = parse_abinit_text(text)
            assert "params" in result
            assert "structure" in result

    def test_roundtrip_no_crash(self, case_dir):
        """Each curated case roundtrips (parse -> write -> parse) without error."""
        from quantumvitas.drivers.abinit.io.abinit_input import (
            parse_abinit_text, write_abinit_text,
        )
        abi_files = list(case_dir.glob("*.abi"))
        for abi_file in abi_files:
            text = abi_file.read_text()
            parsed = parse_abinit_text(text)
            written = write_abinit_text({
                "params": parsed["params"],
                "structure": parsed["structure"],
            })
            reparsed = parse_abinit_text(written)
            assert "params" in reparsed
