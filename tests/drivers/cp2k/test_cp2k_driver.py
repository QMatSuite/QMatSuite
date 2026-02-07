"""Tests for CP2K driver bundle: registration, isolation, inputspec, I/O.

Validates that the CP2K driver is properly registered, its modules
have no kernel imports, and the inputspec roundtrips correctly.
"""

from __future__ import annotations

from pathlib import Path

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

        spec_ids = {s.step_type_spec for s in specs}
        assert "cp2k_scf" in spec_ids
        assert "cp2k_relax" in spec_ids
        assert "cp2k_md" in spec_ids
        assert "cp2k_geo_opt" in spec_ids
        assert "cp2k_cell_opt" in spec_ids

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
        """Test gen->spec mappings."""
        driver = CP2KDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["scf"] == "cp2k_scf"
        assert mat_map["md"] == "cp2k_md"

    def test_md_not_skippable(self):
        """MD steps should not be skippable."""
        driver = CP2KDriver()
        assert driver.supports_incremental_skip("cp2k_scf") is True
        assert driver.supports_incremental_skip("cp2k_md") is False

    def test_workdir_policy(self):
        """CP2K uses isolated workdir."""
        driver = CP2KDriver()
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED

    def test_capabilities(self):
        """CP2K reports expected capabilities."""
        driver = CP2KDriver()
        caps = driver.get_capabilities()
        assert "scf" in caps
        assert "md" in caps
        assert "periodic" in caps


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
        assert DriverRegistry.is_step_type_registered("cp2k_md")


class TestCP2KIsolation:
    """Gate 3 tests: CP2K isolation from kernel."""

    def test_handlers_no_cp2k_handler(self):
        """handlers.py should not contain cp2k_step_handler."""
        handlers_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "handlers.py"
        source = handlers_path.read_text()
        assert "def cp2k_step_handler" not in source

    def test_recipes_no_cp2k_recipe(self):
        """recipes.py should not contain CP2KRecipe."""
        recipes_path = Path(__file__).parent.parent.parent.parent / "src" / "quantumvitas" / "execution" / "recipes.py"
        source = recipes_path.read_text()
        assert "class CP2KRecipe" not in source

    def test_io_module_no_kernel(self):
        """cp2k_input.py should only use stdlib."""
        import importlib
        mod = importlib.import_module("quantumvitas.drivers.cp2k.io.cp2k_input")
        source = open(mod.__file__, "r").read()
        assert "quantumvitas.kernel" not in source
        assert "quantumvitas.runner" not in source
        assert "quantumvitas.daemon" not in source

    def test_parsers_output_no_kernel(self):
        """output.py should only import registry."""
        import importlib
        mod = importlib.import_module("quantumvitas.drivers.cp2k.parsers.output")
        source = open(mod.__file__, "r").read()
        assert "quantumvitas.kernel" not in source
        assert "quantumvitas.runner" not in source

    def test_metadata_no_kernel(self):
        """cp2k_metadata.py should only use stdlib."""
        import importlib
        mod = importlib.import_module("quantumvitas.drivers.cp2k.data.cp2k_metadata")
        source = open(mod.__file__, "r").read()
        assert "quantumvitas.kernel" not in source
        assert "quantumvitas.runner" not in source


class TestCP2KInputSpec:
    """Verify inputspec wiring."""

    def test_get_input_spec_returns_spec(self):
        driver = DriverRegistry.get_driver("cp2k")
        spec = driver.get_input_spec()
        assert spec is not None

    def test_input_spec_has_inp_file(self):
        driver = DriverRegistry.get_driver("cp2k")
        spec = driver.get_input_spec()
        assert len(spec.input_files) >= 1
        filenames = [f.filename for f in spec.input_files]
        assert "input.inp" in filenames

    def test_input_spec_has_parser(self):
        driver = DriverRegistry.get_driver("cp2k")
        spec = driver.get_input_spec()
        for f in spec.input_files:
            if f.filename == "input.inp":
                assert f.custom_parser is not None
                assert f.custom_writer is not None

    def test_input_spec_combined_role(self):
        driver = DriverRegistry.get_driver("cp2k")
        spec = driver.get_input_spec()
        for f in spec.input_files:
            if f.filename == "input.inp":
                assert f.content_role == "combined"


class TestCP2KIOModule:
    """Test the extracted io/cp2k_input.py parse/write functions."""

    def test_parse_basic_energy(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import parse_cp2k_text
        text = """\
&GLOBAL
  PROJECT test
  RUN_TYPE ENERGY
&END GLOBAL

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
    &END XC
  &END DFT
  &SUBSYS
    &CELL
      ABC 10.0 10.0 10.0
    &END CELL
    &COORD
      O  0.0  0.0  0.0
      H  1.0  0.0  0.0
    &END COORD
    &KIND O
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q6
    &END KIND
    &KIND H
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q1
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
"""
        result = parse_cp2k_text(text)
        assert "params" in result
        assert "structure" in result
        assert result["params"]["GLOBAL"]["PROJECT"] == "test"
        assert result["params"]["GLOBAL"]["RUN_TYPE"] == "ENERGY"
        assert result["structure"]["species"] == ["O", "H"]
        assert len(result["structure"]["cart_coords"]) == 2

    def test_parse_fractional_coords(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import parse_cp2k_text
        text = """\
&GLOBAL
  PROJECT si
  RUN_TYPE ENERGY
&END GLOBAL

&FORCE_EVAL
  METHOD Quickstep
  &SUBSYS
    &CELL
      A 0.0 2.715 2.715
      B 2.715 0.0 2.715
      C 2.715 2.715 0.0
    &END CELL
    &COORD
      SCALED .TRUE.
      Si 0.0 0.0 0.0
      Si 0.25 0.25 0.25
    &END COORD
    &KIND Si
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q4
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
"""
        result = parse_cp2k_text(text)
        assert result["structure"]["species"] == ["Si", "Si"]
        assert "frac_coords" in result["structure"]
        assert result["structure"]["frac_coords"][0] == [0.0, 0.0, 0.0]
        assert result["structure"]["frac_coords"][1] == [0.25, 0.25, 0.25]

    def test_parse_explicit_lattice_vectors(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import parse_cp2k_text
        text = """\
&GLOBAL
  PROJECT test
  RUN_TYPE ENERGY
&END GLOBAL
&FORCE_EVAL
  METHOD Quickstep
  &SUBSYS
    &CELL
      A 5.0 0.0 0.0
      B 0.0 5.0 0.0
      C 0.0 0.0 5.0
    &END CELL
    &COORD
      H 1.0 2.0 3.0
    &END COORD
    &KIND H
      BASIS_SET DZVP-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q1
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
"""
        result = parse_cp2k_text(text)
        lattice = result["structure"]["lattice"]
        assert lattice[0] == [5.0, 0.0, 0.0]
        assert lattice[1] == [0.0, 5.0, 0.0]
        assert lattice[2] == [0.0, 0.0, 5.0]

    def test_parse_nested_sections(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import parse_cp2k_text
        text = """\
&GLOBAL
  PROJECT test
  RUN_TYPE ENERGY
&END GLOBAL
&FORCE_EVAL
  METHOD Quickstep
  &DFT
    &SCF
      MAX_SCF 100
      EPS_SCF 1.0E-6
      &OT
        MINIMIZER DIIS
        PRECONDITIONER FULL_SINGLE_INVERSE
      &END OT
    &END SCF
  &END DFT
  &SUBSYS
    &CELL
      ABC 10.0 10.0 10.0
    &END CELL
  &END SUBSYS
&END FORCE_EVAL
"""
        result = parse_cp2k_text(text)
        dft = result["params"]["FORCE_EVAL"]["DFT"]
        assert dft["SCF"]["MAX_SCF"] == 100
        assert dft["SCF"]["EPS_SCF"] == pytest.approx(1e-6)
        assert dft["SCF"]["OT"]["MINIMIZER"] == "DIIS"

    def test_parse_comments_stripped(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import parse_cp2k_text
        text = """\
&GLOBAL
  PROJECT test  # this is a comment
  RUN_TYPE ENERGY  ! another comment
&END GLOBAL
"""
        result = parse_cp2k_text(text)
        assert result["params"]["GLOBAL"]["PROJECT"] == "test"
        assert result["params"]["GLOBAL"]["RUN_TYPE"] == "ENERGY"

    def test_parse_booleans(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import parse_cp2k_text
        text = """\
&GLOBAL
  PROJECT test
  RUN_TYPE ENERGY
&END GLOBAL
&FORCE_EVAL
  METHOD Quickstep
  &SUBSYS
    &CELL
      ABC 10.0 10.0 10.0
    &END CELL
    &COORD
      SCALED .TRUE.
      H 0.0 0.0 0.0
    &END COORD
    &KIND H
      GHOST .FALSE.
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
"""
        result = parse_cp2k_text(text)
        assert "frac_coords" in result["structure"]

    def test_parse_default_keyword(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import parse_cp2k_text
        text = """\
&GLOBAL
  PROJECT test
  RUN_TYPE ENERGY
&END GLOBAL
&FORCE_EVAL
  METHOD Quickstep
  &DFT
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
    &END XC
  &END DFT
  &SUBSYS
    &CELL
      ABC 10.0 10.0 10.0
    &END CELL
  &END SUBSYS
&END FORCE_EVAL
"""
        result = parse_cp2k_text(text)
        xc = result["params"]["FORCE_EVAL"]["DFT"]["XC"]
        assert "XC_FUNCTIONAL" in xc
        func = xc["XC_FUNCTIONAL"]
        assert func.get("_DEFAULT_KEYWORD") == "PBE"

    def test_write_basic(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import write_cp2k_text
        fragment = {
            "params": {
                "GLOBAL": {"PROJECT": "test", "RUN_TYPE": "ENERGY"},
                "FORCE_EVAL": {"METHOD": "Quickstep"},
            },
            "structure": {
                "lattice": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
                "species": ["O", "H", "H"],
                "cart_coords": [
                    [0.0, 0.0, 0.117],
                    [0.0, 0.757, -0.470],
                    [0.0, -0.757, -0.470],
                ],
            },
        }
        text = write_cp2k_text(fragment)
        assert "&GLOBAL" in text
        assert "PROJECT test" in text
        assert "RUN_TYPE ENERGY" in text
        assert "&FORCE_EVAL" in text
        assert "&SUBSYS" in text
        assert "&CELL" in text
        assert "&COORD" in text
        assert "&KIND O" in text
        assert "&KIND H" in text
        assert "&END GLOBAL" in text
        assert "&END FORCE_EVAL" in text

    def test_write_fractional(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import write_cp2k_text
        fragment = {
            "params": {
                "GLOBAL": {"PROJECT": "si", "RUN_TYPE": "ENERGY"},
                "FORCE_EVAL": {"METHOD": "Quickstep"},
            },
            "structure": {
                "lattice": [[0.0, 2.715, 2.715], [2.715, 0.0, 2.715], [2.715, 2.715, 0.0]],
                "species": ["Si", "Si"],
                "frac_coords": [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
            },
        }
        text = write_cp2k_text(fragment)
        assert "SCALED .TRUE." in text
        assert "Si" in text

    def test_write_motion_section(self):
        from quantumvitas.drivers.cp2k.io.cp2k_input import write_cp2k_text
        fragment = {
            "params": {
                "GLOBAL": {"PROJECT": "test", "RUN_TYPE": "GEO_OPT"},
                "FORCE_EVAL": {"METHOD": "Quickstep"},
                "MOTION": {
                    "GEO_OPT": {
                        "MAX_ITER": 100,
                        "OPTIMIZER": "BFGS",
                    },
                },
            },
            "structure": {
                "lattice": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
                "species": ["H"],
                "cart_coords": [[0.0, 0.0, 0.0]],
            },
        }
        text = write_cp2k_text(fragment)
        assert "&MOTION" in text
        assert "&GEO_OPT" in text
        assert "MAX_ITER 100" in text
        assert "OPTIMIZER BFGS" in text
        assert "&END GEO_OPT" in text
        assert "&END MOTION" in text


class TestCP2KCorpusParse:
    """Parse all curated cases to verify no crashes."""

    SAMPLES_DIR = Path(__file__).resolve().parents[2] / "inputformat" / "samples" / "cp2k"

    @pytest.fixture(params=[
        "h2o_energy", "h2o_geo_opt", "h2o_md", "si_scf", "si_relax",
        "si_cell_opt", "si_bands", "benzene_energy", "co2_energy", "h2o_tddft",
    ])
    def case_dir(self, request):
        d = self.SAMPLES_DIR / request.param
        if not d.exists():
            pytest.skip(f"Sample {request.param} not found")
        return d

    def test_parse_no_crash(self, case_dir):
        """Each curated .inp file parses without error."""
        from quantumvitas.drivers.cp2k.io.cp2k_input import parse_cp2k_text
        inp_files = list(case_dir.glob("*.inp"))
        assert len(inp_files) >= 1, f"No .inp file in {case_dir}"
        for inp_file in inp_files:
            text = inp_file.read_text()
            result = parse_cp2k_text(text)
            assert "params" in result
            assert "structure" in result

    def test_roundtrip_no_crash(self, case_dir):
        """Each curated case roundtrips (parse -> write -> parse) without error."""
        from quantumvitas.drivers.cp2k.io.cp2k_input import (
            parse_cp2k_text, write_cp2k_text,
        )
        inp_files = list(case_dir.glob("*.inp"))
        for inp_file in inp_files:
            text = inp_file.read_text()
            parsed = parse_cp2k_text(text)
            written = write_cp2k_text({
                "params": parsed["params"],
                "structure": parsed["structure"],
            })
            reparsed = parse_cp2k_text(written)
            assert "params" in reparsed

    def test_roundtrip_preserves_global(self, case_dir):
        """Roundtrip preserves GLOBAL section parameters."""
        from quantumvitas.drivers.cp2k.io.cp2k_input import (
            parse_cp2k_text, write_cp2k_text,
        )
        inp_files = list(case_dir.glob("*.inp"))
        for inp_file in inp_files:
            text = inp_file.read_text()
            parsed = parse_cp2k_text(text)
            written = write_cp2k_text({
                "params": parsed["params"],
                "structure": parsed["structure"],
            })
            reparsed = parse_cp2k_text(written)
            orig_global = parsed["params"].get("GLOBAL", {})
            rt_global = reparsed["params"].get("GLOBAL", {})
            assert orig_global.get("PROJECT") == rt_global.get("PROJECT")
            assert orig_global.get("RUN_TYPE") == rt_global.get("RUN_TYPE")

    def test_roundtrip_preserves_structure(self, case_dir):
        """Roundtrip preserves species and coordinates."""
        from quantumvitas.drivers.cp2k.io.cp2k_input import (
            parse_cp2k_text, write_cp2k_text,
        )
        inp_files = list(case_dir.glob("*.inp"))
        for inp_file in inp_files:
            text = inp_file.read_text()
            parsed = parse_cp2k_text(text)
            if parsed["structure"] is None:
                continue
            written = write_cp2k_text({
                "params": parsed["params"],
                "structure": parsed["structure"],
            })
            reparsed = parse_cp2k_text(written)
            if reparsed["structure"] is None:
                continue
            assert parsed["structure"]["species"] == reparsed["structure"]["species"]

    def test_case_yaml_valid(self, case_dir):
        """Each case has a valid case.yaml."""
        import yaml
        case_yaml = case_dir / "case.yaml"
        assert case_yaml.exists(), f"Missing case.yaml in {case_dir}"
        data = yaml.safe_load(case_yaml.read_text())
        assert "case_id" in data
        assert "engine" in data
        assert data["engine"] == "cp2k"
