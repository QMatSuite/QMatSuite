"""Tests for QMCPACK driver bundle."""

import math
import tempfile
from pathlib import Path

import pytest

from qmatsuite.drivers.qmcpack import QMCPACKDriver
from qmatsuite.core.driver_registry import DriverRegistry
from qmatsuite.core.driver_protocol import WorkdirPolicy


GOLDEN_DIR = Path(__file__).parent / "golden"


class TestQMCPACKDriver:
    """Test QMCPACKDriver implementation."""

    def test_driver_properties(self):
        """Test required driver properties."""
        driver = QMCPACKDriver()
        assert driver.engine_family == "qmcpack"
        assert driver.display_name == "QMCPACK"
        assert driver.driver_api_version == "1.0.0"

    def test_step_type_specs(self):
        """Test step type registration."""
        driver = QMCPACKDriver()
        specs = driver.get_step_type_specs()

        spec_ids = {s.step_type_spec for s in specs}
        assert "qmcpack_vmc" in spec_ids
        assert "qmcpack_dmc" in spec_ids
        assert "qmcpack_wfopt" in spec_ids

        for spec in specs:
            assert spec.engine == "qmcpack"
            assert spec.mpi_aware is True

    def test_handler_callable(self):
        """Test handler is callable."""
        driver = QMCPACKDriver()
        handler = driver.get_handler()
        assert callable(handler)

    def test_recipe_class(self):
        """Test recipe class is returned."""
        driver = QMCPACKDriver()
        recipe_class = driver.get_recipe_class()
        assert recipe_class is not None

    def test_materialization_map(self):
        """Test gen->spec mappings."""
        driver = QMCPACKDriver()
        mat_map = driver.get_materialization_map()

        assert mat_map["vmc"] == "qmcpack_vmc"
        assert mat_map["dmc"] == "qmcpack_dmc"
        assert mat_map["wfopt"] == "qmcpack_wfopt"

    def test_workdir_policy(self):
        """QMCPACK should use ISOLATED workdir."""
        driver = QMCPACKDriver()
        assert driver.get_workdir_policy() == WorkdirPolicy.ISOLATED

    def test_qmc_capabilities(self):
        """QMCPACK should have QMC capabilities."""
        driver = QMCPACKDriver()
        caps = driver.get_capabilities()
        assert "qmc" in caps
        assert "vmc" in caps
        assert "dmc" in caps
        assert "mpi" in caps


class TestQMCPACKRegistration:
    """Test QMCPACK driver registration."""

    def test_qmcpack_registered(self):
        """QMCPACK should be registered in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_engine_registered("qmcpack")
        driver = DriverRegistry.get_driver("qmcpack")
        assert driver.engine_family == "qmcpack"

    def test_qmcpack_step_types_registered(self):
        """QMCPACK step types should be in registry."""
        import qmatsuite.drivers

        assert DriverRegistry.is_step_type_registered("qmcpack_vmc")
        assert DriverRegistry.is_step_type_registered("qmcpack_dmc")
        assert DriverRegistry.is_step_type_registered("qmcpack_wfopt")


class TestQMCPACKIsolation:
    """Gate 3 tests: QMCPACK isolation from kernel."""

    def test_handlers_no_qmcpack_handler(self):
        """handlers.py should not contain qmcpack_step_handler."""
        handlers_path = Path(__file__).parent.parent.parent.parent / "src" / "qmatsuite" / "execution" / "handlers.py"
        source = handlers_path.read_text()

        assert "def qmcpack_step_handler" not in source

    def test_recipes_no_qmcpack_recipe(self):
        """recipes.py should not contain QMCPACKRecipe."""
        recipes_path = Path(__file__).parent.parent.parent.parent / "src" / "qmatsuite" / "execution" / "recipes.py"
        source = recipes_path.read_text()

        assert "class QMCPACKRecipe" not in source


class TestQMCPACKParser:
    """Tests for QMCPACK output parser."""

    def test_parse_scalar_dat(self):
        """Parse a golden scalar.dat file."""
        from qmatsuite.drivers.qmcpack.parser import parse_scalar_dat

        result = parse_scalar_dat(GOLDEN_DIR / "vmc_scalar.dat")
        assert result.num_blocks == 5
        assert "LocalEnergy" in result.columns
        assert "AcceptRatio" in result.columns
        assert -11.0 < result.mean_energy < -10.0

    def test_parse_scalar_dat_properties(self):
        """Test computed properties of scalar data."""
        from qmatsuite.drivers.qmcpack.parser import parse_scalar_dat

        result = parse_scalar_dat(GOLDEN_DIR / "vmc_scalar.dat")
        assert not math.isnan(result.mean_energy)
        assert not math.isnan(result.energy_variance)
        assert not math.isnan(result.energy_error)
        assert result.energy_error > 0
        assert 0.0 < result.mean_accept_ratio < 1.0

    def test_parse_scalar_dat_empty(self, tmp_path):
        """Empty file should raise ValueError."""
        from qmatsuite.drivers.qmcpack.parser import parse_scalar_dat

        empty_file = tmp_path / "empty.dat"
        empty_file.write_text("")
        with pytest.raises(ValueError):
            parse_scalar_dat(empty_file)

    def test_parse_scalar_dat_no_header(self, tmp_path):
        """File without # header should raise ValueError."""
        from qmatsuite.drivers.qmcpack.parser import parse_scalar_dat

        bad_file = tmp_path / "bad.dat"
        bad_file.write_text("1.0 2.0 3.0\n")
        with pytest.raises(ValueError, match="Expected header"):
            parse_scalar_dat(bad_file)

    def test_parse_dmc_dat(self):
        """Parse a golden dmc.dat file."""
        from qmatsuite.drivers.qmcpack.parser import parse_dmc_dat

        result = parse_dmc_dat(GOLDEN_DIR / "dmc_dmc.dat")
        assert result.num_steps == 3
        assert "NumOfWalkers" in result.columns
        assert "LocalEnergy" in result.columns
        assert not math.isnan(result.mean_energy)

    def test_parse_stdout_success(self):
        """Parse QMCPACK stdout with success message."""
        from qmatsuite.drivers.qmcpack.parser import parse_qmcpack_stdout

        fake_stdout = """
====================================================
  End of a VMC section
    QMC counter        = 0
    time step          = 0.3
    reference energy   = -10.4905
    reference variance = 0.373664
====================================================
QMCPACK execution completed successfully
"""
        result = parse_qmcpack_stdout(fake_stdout)
        assert result["success"] is True
        assert len(result["sections"]) == 1
        assert result["sections"][0]["method"] == "VMC"
        assert abs(result["sections"][0]["reference_energy"] - (-10.4905)) < 1e-4

    def test_parse_stdout_failure(self):
        """Parse QMCPACK stdout without success message."""
        from qmatsuite.drivers.qmcpack.parser import parse_qmcpack_stdout

        result = parse_qmcpack_stdout("some error output")
        assert result["success"] is False
        assert len(result["sections"]) == 0

    def test_parse_qmcpack_run(self, tmp_path):
        """Test full run parsing with scalar.dat files."""
        from qmatsuite.drivers.qmcpack.parser import parse_qmcpack_run
        import shutil

        # Copy golden scalar.dat and rename to match expected pattern
        shutil.copy(
            GOLDEN_DIR / "vmc_scalar.dat",
            tmp_path / "qmc.s000.scalar.dat",
        )

        result = parse_qmcpack_run(tmp_path, "qmc")
        assert result.success is True
        assert len(result.series) == 1
        assert result.series[0]["series_idx"] == 0
        assert result.series[0]["method"] == "vmc"
        assert not math.isnan(result.final_energy)


class TestQMCPACKWriter:
    """Tests for QMCPACK input writer."""

    def _make_test_inputs(self):
        """Create test inputs for writer tests."""
        from qmatsuite.drivers.qmcpack.writer import (
            QMCPACKCell, QMCPACKSpecies, QMCPACKWavefunction,
            QMCPACKVMCParams, QMCPACKDMCParams, QMCPACKOptParams,
        )

        cell = QMCPACKCell(
            lattice=[
                [3.37316115, 3.37316115, 0.0],
                [0.0, 3.37316115, 3.37316115],
                [3.37316115, 0.0, 3.37316115],
            ],
        )

        carbon = QMCPACKSpecies(
            symbol="C",
            charge=4,
            valence=4,
            atomic_number=6,
            mass=21894.7135906,
            positions=[[0.0, 0.0, 0.0], [1.68658058, 1.68658058, 1.68658058]],
            pseudo_file="C.BFD.xml",
        )

        wf = QMCPACKWavefunction(
            href="pwscf.pwscf.h5",
            num_up=4,
            num_down=4,
            num_orbitals=4,
        )

        vmc = QMCPACKVMCParams(blocks=200, steps=10, timestep=0.3)
        dmc = QMCPACKDMCParams(targetwalkers=64, blocks=100, timestep=0.005)
        opt = QMCPACKOptParams(num_loops=3, blocks=100, steps=50)

        return cell, [carbon], wf, vmc, dmc, opt

    def test_write_vmc_input(self, tmp_path):
        """Test VMC input XML generation."""
        from qmatsuite.drivers.qmcpack.writer import write_vmc_input

        cell, species, wf, vmc, _, _ = self._make_test_inputs()
        output = tmp_path / "vmc.xml"
        write_vmc_input(output, "test_vmc", cell, species, wf, vmc)

        content = output.read_text()
        assert "<simulation>" in content
        assert 'method="vmc"' in content
        assert "C.BFD.xml" in content
        assert "pwscf.pwscf.h5" in content
        assert 'method="dmc"' not in content

    def test_write_dmc_input(self, tmp_path):
        """Test VMC+DMC input XML generation."""
        from qmatsuite.drivers.qmcpack.writer import write_vmc_dmc_input

        cell, species, wf, vmc, dmc, _ = self._make_test_inputs()
        output = tmp_path / "dmc.xml"
        write_vmc_dmc_input(output, "test_dmc", cell, species, wf, vmc, dmc)

        content = output.read_text()
        assert 'method="vmc"' in content
        assert 'method="dmc"' in content
        assert "targetwalkers" in content

    def test_write_wfopt_input(self, tmp_path):
        """Test wavefunction optimization input XML generation."""
        from qmatsuite.drivers.qmcpack.writer import write_wfopt_input

        cell, species, wf, _, _, opt = self._make_test_inputs()
        output = tmp_path / "wfopt.xml"
        write_wfopt_input(output, "test_opt", cell, species, wf, opt)

        content = output.read_text()
        assert "<loop" in content
        assert 'method="linear"' in content
        assert "Minmethod" in content

    def test_write_wfopt_with_vmc(self, tmp_path):
        """Test wfopt followed by VMC production."""
        from qmatsuite.drivers.qmcpack.writer import write_wfopt_input

        cell, species, wf, vmc, _, opt = self._make_test_inputs()
        output = tmp_path / "opt_vmc.xml"
        write_wfopt_input(output, "test_opt_vmc", cell, species, wf, opt, vmc)

        content = output.read_text()
        assert "<loop" in content
        assert 'method="linear"' in content
        assert 'method="vmc"' in content

    def test_write_with_jastrow(self, tmp_path):
        """Test writer with Jastrow factors."""
        from qmatsuite.drivers.qmcpack.writer import (
            write_vmc_input, QMCPACKCell, QMCPACKSpecies,
            QMCPACKWavefunction, QMCPACKVMCParams,
        )

        cell = QMCPACKCell(lattice=[[5, 0, 0], [0, 5, 0], [0, 0, 5]])
        species = [QMCPACKSpecies(
            symbol="C", charge=4, valence=4, atomic_number=6,
            mass=21894.0, positions=[[0, 0, 0]],
        )]
        wf = QMCPACKWavefunction(
            href="test.h5", num_up=2, num_down=2, num_orbitals=2,
            j1_coeffs={"C": [-0.2, -0.1, -0.05]},
            j2_uu_coeffs=[0.3, 0.2, 0.1],
            j2_ud_coeffs=[0.5, 0.3, 0.1],
        )
        vmc = QMCPACKVMCParams()
        output = tmp_path / "jastrow.xml"
        write_vmc_input(output, "test_j", cell, species, wf, vmc)

        content = output.read_text()
        assert "One-Body" in content
        assert "Two-Body" in content
        assert "eC" in content  # J1 coefficient id


class TestQMCPACKRecipe:
    """Tests for QMCPACK recipe."""

    def test_materialize_empty_steps(self):
        """Empty steps should produce empty JobGraph."""
        from qmatsuite.drivers.qmcpack.recipe import QMCPACKRecipe

        recipe = QMCPACKRecipe()
        graph = recipe.materialize([], Path("/tmp/test"))
        assert len(graph.jobs) == 0


class TestQMCPACKEngineRegistry:
    """Test QMCPACK engine registration."""

    def test_qmcpack_in_default_registry(self):
        """QMCPACK should be in default engine registry."""
        from qmatsuite.engine.registry import create_default_registry

        registry = create_default_registry()
        assert registry.has("qmcpack")
        engine = registry.get("qmcpack")
        assert engine.name == "qmcpack"

    def test_qmcpack_supported_presets(self):
        """Test QMCPACK supported presets."""
        from qmatsuite.engine.registry import create_default_registry

        registry = create_default_registry()
        engine = registry.get("qmcpack")
        assert "qmc_method" in engine.supported_presets


class TestQMCPACKResolver:
    """Tests for QMCPACK binary resolver."""

    def test_resolver_env_var(self, tmp_path, monkeypatch):
        """Test resolver with QMATS_QMCPACK_BIN environment variable."""
        from qmatsuite.core.engines.qmcpack_resolver import resolve_qmcpack_bin

        fake_bin = tmp_path / "qmcpack"
        fake_bin.touch()

        monkeypatch.setenv("QMATS_QMCPACK_BIN", str(fake_bin))
        result = resolve_qmcpack_bin()
        assert result == fake_bin

    def test_resolver_invalid_env_var(self, monkeypatch):
        """Test resolver with invalid QMATS_QMCPACK_BIN."""
        from qmatsuite.core.engines.qmcpack_resolver import resolve_qmcpack_bin

        monkeypatch.setenv("QMATS_QMCPACK_BIN", "/nonexistent/qmcpack")
        with pytest.raises(FileNotFoundError, match="QMATS_QMCPACK_BIN"):
            resolve_qmcpack_bin()

    def test_resolver_not_found(self, tmp_path, monkeypatch):
        """Test resolver when QMCPACK is not found."""
        from qmatsuite.core.engines.qmcpack_resolver import resolve_qmcpack_bin
        import qmatsuite.core.engines.qmcpack_resolver as qr

        monkeypatch.delenv("QMATS_QMCPACK_BIN", raising=False)
        monkeypatch.delenv("CONDA_PREFIX", raising=False)
        monkeypatch.setenv("QMATSUITE_HOME", str(tmp_path / "qms-home"))
        # Override PATH to exclude qmcpack
        monkeypatch.setenv("PATH", "/nonexistent")
        # Prevent finding bundled binary via repo root detection
        monkeypatch.setattr(
            "qmatsuite.core.engines.discovery._find_repo_root",
            lambda: None,
        )
        with pytest.raises(FileNotFoundError, match="QMCPACK not found"):
            resolve_qmcpack_bin()


class TestQMCPACKGenSteps:
    """Test that QMCPACK GEN steps are in the registry."""

    def test_vmc_gen_step(self):
        """vmc should be a valid GEN step."""
        from qmatsuite.workflow.gen_steps import GenStepRegistry
        assert GenStepRegistry.is_valid("vmc")

    def test_dmc_gen_step(self):
        """dmc should be a valid GEN step."""
        from qmatsuite.workflow.gen_steps import GenStepRegistry
        assert GenStepRegistry.is_valid("dmc")

    def test_wfopt_gen_step(self):
        """wfopt should be a valid GEN step."""
        from qmatsuite.workflow.gen_steps import GenStepRegistry
        assert GenStepRegistry.is_valid("wfopt")


class TestQMCPACKStepTypeConvert:
    """Test step type conversion with QMCPACK prefix."""

    def test_qmcpack_prefix_recognized(self):
        """qmcpack should be a recognized engine prefix."""
        from qmatsuite.workflow.step_type_convert import ENGINE_PREFIXES
        assert "qmcpack" in ENGINE_PREFIXES

    def test_spec_from_gen(self):
        """Test SPEC creation from prefix + gen."""
        from qmatsuite.workflow.step_type_convert import spec_from
        assert spec_from("qmcpack", "vmc") == "qmcpack_vmc"
        assert spec_from("qmcpack", "dmc") == "qmcpack_dmc"

    def test_gen_from_spec(self):
        """Test GEN extraction from SPEC."""
        from qmatsuite.workflow.step_type_convert import gen_from
        assert gen_from("qmcpack_vmc") == "vmc"
        assert gen_from("qmcpack_dmc") == "dmc"
        assert gen_from("qmcpack_wfopt") == "wfopt"

    def test_prefix_from_spec(self):
        """Test prefix extraction from SPEC."""
        from qmatsuite.workflow.step_type_convert import prefix_from
        assert prefix_from("qmcpack_vmc") == "qmcpack"
