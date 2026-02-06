"""Per-engine materialize tests via write_engine_inputs.

Tests get_input_spec + write_engine_inputs for each engine,
verifying that expected files are produced with correct content.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.inputformat import write_engine_inputs

# ─────────────────────────────────────────────────────────────────────
# Shared test data
# ─────────────────────────────────────────────────────────────────────

SI_STRUCTURE = {
    "lattice": [
        [5.4309, 0.0, 0.0],
        [0.0, 5.4309, 0.0],
        [0.0, 0.0, 5.4309],
    ],
    "species": ["Si", "Si"],
    "frac_coords": [
        [0.0, 0.0, 0.0],
        [0.25, 0.25, 0.25],
    ],
    "comment": "Si diamond",
}


# ─────────────────────────────────────────────────────────────────────
# VASP
# ─────────────────────────────────────────────────────────────────────


class TestVASPMaterialize:
    """Test VASP input file generation via write_engine_inputs."""

    @pytest.fixture
    def vasp_spec(self):
        from quantumvitas.drivers.vasp.inputspec import get_vasp_input_spec
        return get_vasp_input_spec()

    def test_produces_three_files(self, tmp_path, vasp_spec):
        params = {
            "ENCUT": 300,
            "ISMEAR": 0,
            "SIGMA": 0.05,
            "kpoints": {"mode": "automatic", "mesh": [4, 4, 4]},
        }
        written = write_engine_inputs(vasp_spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 3
        names = [p.name for p in written]
        assert "INCAR" in names
        assert "POSCAR" in names
        assert "KPOINTS" in names

    def test_incar_content(self, tmp_path, vasp_spec):
        params = {"ENCUT": 300, "ISMEAR": 0, "kpoints": {}}
        write_engine_inputs(vasp_spec, tmp_path, params=params, structure=SI_STRUCTURE)
        incar = (tmp_path / "INCAR").read_text()
        assert "ENCUT = 300" in incar
        assert "ISMEAR = 0" in incar

    def test_poscar_content(self, tmp_path, vasp_spec):
        params = {"kpoints": {}}
        write_engine_inputs(vasp_spec, tmp_path, params=params, structure=SI_STRUCTURE)
        poscar = (tmp_path / "POSCAR").read_text()
        assert "Si diamond" in poscar
        assert "Si" in poscar
        assert "Direct" in poscar
        assert "5.4309" in poscar

    def test_kpoints_content(self, tmp_path, vasp_spec):
        params = {"kpoints": {"mode": "automatic", "mesh": [6, 6, 6]}}
        write_engine_inputs(vasp_spec, tmp_path, params=params, structure=SI_STRUCTURE)
        kp = (tmp_path / "KPOINTS").read_text()
        assert "6  6  6" in kp
        assert "Gamma" in kp

    def test_spec_metadata(self, vasp_spec):
        assert vasp_spec.engine_family == "vasp"
        assert vasp_spec.syntax_family == "flat-keyval"
        assert len(vasp_spec.input_files) == 3
        assert len(vasp_spec.resource_refs) == 1
        assert vasp_spec.resource_refs[0].name == "potcar"


# ─────────────────────────────────────────────────────────────────────
# Gaussian
# ─────────────────────────────────────────────────────────────────────


class TestGaussianMaterialize:
    """Test Gaussian input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.gaussian.inputspec import get_gaussian_input_spec
        return get_gaussian_input_spec()

    def test_produces_gjf(self, tmp_path, spec):
        params = {
            "method": "B3LYP",
            "basis": "6-31G*",
            "charge": 0,
            "multiplicity": 1,
            "gen_type": "scf",
        }
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 1
        assert written[0].name == "input.gjf"

    def test_gjf_content(self, tmp_path, spec):
        params = {
            "method": "B3LYP",
            "basis": "6-31G*",
            "gen_type": "relax",
        }
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "input.gjf").read_text()
        assert "#p B3LYP/6-31G*" in content
        assert "Opt" in content
        assert "Si" in content


# ─────────────────────────────────────────────────────────────────────
# xTB
# ─────────────────────────────────────────────────────────────────────


class TestXTBMaterialize:
    """Test xTB input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.xtb.inputspec import get_xtb_input_spec
        return get_xtb_input_spec()

    def test_produces_xyz(self, tmp_path, spec):
        written = write_engine_inputs(spec, tmp_path, structure=SI_STRUCTURE)
        assert len(written) == 1
        assert written[0].name == "input.xyz"

    def test_xyz_content(self, tmp_path, spec):
        write_engine_inputs(spec, tmp_path, structure=SI_STRUCTURE)
        content = (tmp_path / "input.xyz").read_text()
        lines = content.strip().splitlines()
        assert lines[0] == "2"  # atom count
        assert "Si" in lines[2]


# ─────────────────────────────────────────────────────────────────────
# Siesta
# ─────────────────────────────────────────────────────────────────────


class TestSiestaMaterialize:
    """Test Siesta input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.siesta.inputspec import get_siesta_input_spec
        return get_siesta_input_spec(system_label="si_test")

    def test_produces_fdf(self, tmp_path, spec):
        params = {"system_name": "Si test", "system_label": "si_test"}
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 1
        assert written[0].name == "si_test.fdf"

    def test_fdf_content(self, tmp_path, spec):
        params = {"system_name": "Si test", "system_label": "si_test"}
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "si_test.fdf").read_text()
        assert "SystemName" in content
        assert "LatticeVectors" in content
        assert "Si" in content


# ─────────────────────────────────────────────────────────────────────
# QE
# ─────────────────────────────────────────────────────────────────────


class TestQEMaterialize:
    """Test QE input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.qe.inputspec import get_qe_input_spec
        return get_qe_input_spec(gen_type="pw")

    def test_produces_pw_in(self, tmp_path, spec):
        params = {
            "CONTROL": {"calculation": "scf", "pseudo_dir": "./pseudo/"},
            "SYSTEM": {"ecutwfc": 30, "nat": 2, "ntyp": 1},
            "ELECTRONS": {"conv_thr": 1.0e-8},
            "kpoints": {"mesh": [4, 4, 4]},
        }
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 1
        assert written[0].name == "pw.in"

    def test_pw_content(self, tmp_path, spec):
        params = {
            "CONTROL": {"calculation": "scf"},
            "SYSTEM": {"ecutwfc": 30},
            "ELECTRONS": {},
            "kpoints": {"mesh": [4, 4, 4]},
        }
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "pw.in").read_text()
        assert "ATOMIC_POSITIONS" in content
        assert "Si" in content

    def test_dynamic_filename(self):
        from quantumvitas.drivers.qe.inputspec import get_qe_input_spec
        spec = get_qe_input_spec(gen_type="ph")
        assert spec.input_files[0].filename == "ph.in"


# ─────────────────────────────────────────────────────────────────────
# ABINIT
# ─────────────────────────────────────────────────────────────────────


class TestABINITMaterialize:
    """Test ABINIT input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.abinit.inputspec import get_abinit_input_spec
        return get_abinit_input_spec(step_prefix="scf")

    def test_produces_abi(self, tmp_path, spec):
        params = {"ecut": 30, "ngkpt": "4 4 4"}
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 1
        assert written[0].name == "scf.abi"

    def test_abi_content(self, tmp_path, spec):
        params = {"ecut": 30}
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "scf.abi").read_text()
        assert "natom" in content
        assert "xred" in content
        assert "ecut" in content


# ─────────────────────────────────────────────────────────────────────
# Wannier90
# ─────────────────────────────────────────────────────────────────────


class TestW90Materialize:
    """Test Wannier90 input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.w90.inputspec import get_w90_input_spec
        return get_w90_input_spec()

    def test_produces_win(self, tmp_path, spec):
        params = {"num_bands": 12, "num_wann": 8}
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 1
        assert written[0].name == "wannier90.win"

    def test_win_content(self, tmp_path, spec):
        params = {"num_bands": 12, "num_wann": 8}
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "wannier90.win").read_text()
        assert "num_bands" in content
        assert "unit_cell_cart" in content
        assert "atoms_frac" in content


# ─────────────────────────────────────────────────────────────────────
# CP2K
# ─────────────────────────────────────────────────────────────────────


class TestCP2KMaterialize:
    """Test CP2K input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.cp2k.inputspec import get_cp2k_input_spec
        return get_cp2k_input_spec()

    def test_produces_inp(self, tmp_path, spec):
        params = {
            "GLOBAL": {"PROJECT": "si_scf", "RUN_TYPE": "ENERGY"},
        }
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 1
        assert written[0].name == "input.inp"

    def test_inp_content(self, tmp_path, spec):
        params = {"GLOBAL": {"PROJECT": "si_test"}}
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "input.inp").read_text()
        assert "&GLOBAL" in content
        assert "si_test" in content
        assert "&FORCE_EVAL" in content
        assert "&SUBSYS" in content
        assert "Si" in content


# ─────────────────────────────────────────────────────────────────────
# LAMMPS
# ─────────────────────────────────────────────────────────────────────


class TestLAMMPSMaterialize:
    """Test LAMMPS input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.lammps.inputspec import get_lammps_input_spec
        return get_lammps_input_spec()

    def test_produces_two_files(self, tmp_path, spec):
        params = {"units": "metal", "pair_style": "lj/cut 10.0"}
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 2
        names = [p.name for p in written]
        assert "in.lammps" in names
        assert "structure.data" in names

    def test_script_content(self, tmp_path, spec):
        params = {"units": "metal"}
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "in.lammps").read_text()
        assert "units" in content
        assert "metal" in content

    def test_data_content(self, tmp_path, spec):
        params = {}
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "structure.data").read_text()
        assert "2 atoms" in content
        assert "1 atom types" in content


# ─────────────────────────────────────────────────────────────────────
# QMCPACK
# ─────────────────────────────────────────────────────────────────────


class TestQMCPACKMaterialize:
    """Test QMCPACK input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.qmcpack.inputspec import get_qmcpack_input_spec
        return get_qmcpack_input_spec()

    def test_produces_xml(self, tmp_path, spec):
        params = {"project_id": "si_vmc", "walkers": 1, "blocks": 10}
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 1
        assert written[0].name == "qmc_input.xml"

    def test_xml_content(self, tmp_path, spec):
        params = {"project_id": "si_vmc"}
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "qmc_input.xml").read_text()
        assert "<simulation" in content
        assert "si_vmc" in content
        assert "simulationcell" in content


# ─────────────────────────────────────────────────────────────────────
# ORCA
# ─────────────────────────────────────────────────────────────────────


class TestORCAMaterialize:
    """Test ORCA input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.orca.inputspec import get_orca_input_spec
        return get_orca_input_spec(basename="si_calc")

    def test_produces_inp(self, tmp_path, spec):
        params = {"method": "B3LYP", "basis": "def2-SVP"}
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 1
        assert written[0].name == "si_calc.inp"

    def test_inp_content(self, tmp_path, spec):
        params = {"method": "B3LYP", "basis": "def2-SVP", "charge": 0, "multiplicity": 1}
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        content = (tmp_path / "si_calc.inp").read_text()
        assert "! B3LYP def2-SVP" in content
        assert "* xyz 0 1" in content
        assert "Si" in content


# ─────────────────────────────────────────────────────────────────────
# Yambo
# ─────────────────────────────────────────────────────────────────────


class TestYamboMaterialize:
    """Test Yambo input file generation."""

    def test_setup_spec_empty(self, tmp_path):
        from quantumvitas.drivers.yambo.inputspec import get_yambo_input_spec
        spec = get_yambo_input_spec(gen_type="setup")
        written = write_engine_inputs(spec, tmp_path)
        assert written == []

    def test_gw_produces_file(self, tmp_path):
        from quantumvitas.drivers.yambo.inputspec import get_yambo_input_spec
        spec = get_yambo_input_spec(gen_type="gw")
        params = {"gen_type": "gw", "polarization_bands": (1, 20)}
        written = write_engine_inputs(spec, tmp_path, params=params)
        assert len(written) == 1
        assert written[0].name == "gw.in"
        assert (tmp_path / "gw.in").stat().st_size > 0


# ─────────────────────────────────────────────────────────────────────
# GPAW
# ─────────────────────────────────────────────────────────────────────


class TestGPAWMaterialize:
    """Test GPAW input file generation."""

    @pytest.fixture
    def spec(self):
        from quantumvitas.drivers.gpaw.inputspec import get_gpaw_input_spec
        return get_gpaw_input_spec(gen_type="scf")

    def test_produces_two_files(self, tmp_path, spec):
        params = {"gen_type": "scf"}
        written = write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        assert len(written) == 2
        names = [p.name for p in written]
        assert "scf.py" in names
        assert "structure.json" in names

    def test_structure_json_content(self, tmp_path, spec):
        params = {"gen_type": "scf"}
        write_engine_inputs(spec, tmp_path, params=params, structure=SI_STRUCTURE)
        import json
        content = json.loads((tmp_path / "structure.json").read_text())
        assert content["species"] == ["Si", "Si"]
        assert len(content["lattice"]) == 3


# ─────────────────────────────────────────────────────────────────────
# Psi4 / PySCF (trivial — no files)
# ─────────────────────────────────────────────────────────────────────


class TestPsi4Materialize:
    """Test Psi4 input spec (no files)."""

    def test_empty_spec(self, tmp_path):
        from quantumvitas.drivers.psi4.inputspec import get_psi4_input_spec
        spec = get_psi4_input_spec()
        written = write_engine_inputs(spec, tmp_path)
        assert written == []
        assert spec.engine_family == "psi4"
        assert spec.input_files == ()


class TestPySCFMaterialize:
    """Test PySCF input spec (no files)."""

    def test_empty_spec(self, tmp_path):
        from quantumvitas.drivers.pyscf.inputspec import get_pyscf_input_spec
        spec = get_pyscf_input_spec()
        written = write_engine_inputs(spec, tmp_path)
        assert written == []
        assert spec.engine_family == "pyscf"
        assert spec.input_files == ()


# ─────────────────────────────────────────────────────────────────────
# Driver integration: verify get_input_spec on driver
# ─────────────────────────────────────────────────────────────────────


class TestDriverGetInputSpec:
    """Test that all drivers return a valid EngineInputSpec via get_input_spec."""

    DRIVERS = [
        "quantumvitas.drivers.vasp.driver:VASPDriver",
        "quantumvitas.drivers.qe.driver:QEDriver",
        "quantumvitas.drivers.abinit.driver:AbinitDriver",
        "quantumvitas.drivers.cp2k.driver:CP2KDriver",
        "quantumvitas.drivers.orca.driver:ORCADriver",
        "quantumvitas.drivers.gaussian.driver:GaussianDriver",
        "quantumvitas.drivers.lammps.driver:LAMMPSDriver",
        "quantumvitas.drivers.siesta.driver:SiestaDriver",
        "quantumvitas.drivers.w90.driver:W90Driver",
        "quantumvitas.drivers.gpaw.driver:GPAWDriver",
        "quantumvitas.drivers.psi4.driver:Psi4Driver",
        "quantumvitas.drivers.pyscf.driver:PySCFDriver",
        "quantumvitas.drivers.xtb.driver:XTBDriver",
        "quantumvitas.drivers.qmcpack.driver:QMCPACKDriver",
        "quantumvitas.drivers.yambo.driver:YamboDriver",
    ]

    @pytest.mark.parametrize("driver_path", DRIVERS)
    def test_get_input_spec_returns_spec(self, driver_path):
        """Every driver.get_input_spec() returns an EngineInputSpec."""
        from quantumvitas.inputformat.core import EngineInputSpec
        import importlib

        module_path, class_name = driver_path.rsplit(":", 1)
        module = importlib.import_module(module_path)
        driver_cls = getattr(module, class_name)
        driver = driver_cls()

        spec = driver.get_input_spec()
        assert spec is not None, f"{class_name}.get_input_spec() returned None"
        assert isinstance(spec, EngineInputSpec)
        assert spec.engine_family == driver.engine_family
