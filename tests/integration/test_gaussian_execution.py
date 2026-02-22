"""
Integration tests for Gaussian execution.

These tests run actual Gaussian calculations and verify results.
Tests are skipped if Gaussian is not installed.

To run these tests:
    pytest tests/integration/test_gaussian_execution.py -v
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import yaml
from pymatgen.core import Molecule

from qmatsuite.core.engines.discovery import is_engine_available

# Repo root for .tmp directory
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Set environment variable for engine discovery if bundled Gaussian exists
_BUNDLED_GAUSSIAN = _REPO_ROOT / ".qmatsuite" / "engines" / "gaussian" / "gaussian09"
if _BUNDLED_GAUSSIAN.exists() and "g09root" not in os.environ:
    os.environ["g09root"] = str(_BUNDLED_GAUSSIAN)

pytestmark = pytest.mark.skipif(
    not is_engine_available("gaussian", project_root=_REPO_ROOT),
    reason="Gaussian not installed - needs g09 or g16 in PATH or g09root/g16root set",
)


@pytest.fixture
def gaussian_workdir(tmp_path_factory):
    """Create a working directory for Gaussian tests under .tmp/gaussian/."""
    base = _REPO_ROOT / ".tmp" / "gaussian"
    base.mkdir(parents=True, exist_ok=True)
    workdir = tmp_path_factory.mktemp("gaussian", numbered=True)
    return workdir


def _find_gaussian() -> str:
    """Find the Gaussian binary (g09 or g16)."""
    from qmatsuite.core.engines.discovery import discover_engine

    # Use centralized discovery
    result = discover_engine("gaussian", project_root=_REPO_ROOT)
    if result.available and result.executable_path:
        return str(result.executable_path)

    # Fallback: Check PATH
    for binary in ["g16", "g09"]:
        found = shutil.which(binary)
        if found:
            return found

    # Check environment variables
    for root_var in ["g16root", "g09root"]:
        root_val = os.environ.get(root_var)
        if root_val:
            root_path = Path(root_val)
            for binary in ["g16", "g09"]:
                candidate = root_path / binary / binary
                if candidate.is_file():
                    return str(candidate)

    # Check GAUSS_EXEDIR
    gauss_exedir = os.environ.get("GAUSS_EXEDIR")
    if gauss_exedir:
        gauss_path = Path(gauss_exedir)
        for binary in ["g16", "g09"]:
            candidate = gauss_path / binary
            if candidate.is_file():
                return str(candidate)

    pytest.skip("Gaussian binary not found")


def _setup_gaussian_env(binary_path: str) -> dict:
    """Setup environment variables for Gaussian execution."""
    env = os.environ.copy()
    binary_dir = Path(binary_path).parent

    env["GAUSS_EXEDIR"] = str(binary_dir)
    if "GAUSS_SCRDIR" not in env:
        env["GAUSS_SCRDIR"] = "/tmp"

    path = env.get("PATH", "")
    env["PATH"] = f"{binary_dir}:{path}"

    return env


# =====================================================================
# Test 1: Raw Gaussian binary — H2O single point
# =====================================================================


class TestGaussianRawExecution:
    """Tests that call the Gaussian binary directly (no driver framework)."""

    def test_h2o_hf_sp_raw(self, gaussian_workdir):
        """Run H2O HF/STO-3G single point via raw subprocess and verify outputs."""
        workdir = gaussian_workdir

        # Write input .gjf file
        gjf_content = """\
%mem=500MB
%nproc=1
%chk=water.chk
#p HF/STO-3G

Water single point energy

0 1
 O   0.0000000000   0.0000000000   0.1174000000
 H   0.0000000000   0.7572000000  -0.4696000000
 H   0.0000000000  -0.7572000000  -0.4696000000

"""
        (workdir / "input.gjf").write_text(gjf_content)

        # Find Gaussian binary and setup environment
        gaussian_bin = _find_gaussian()
        env = _setup_gaussian_env(gaussian_bin)

        # Run Gaussian (reads from stdin)
        with open(workdir / "input.gjf", "r") as stdin_file:
            result = subprocess.run(
                [gaussian_bin],
                stdin=stdin_file,
                capture_output=True,
                text=True,
                cwd=str(workdir),
                env=env,
                timeout=300,
            )

        # Save stdout as output.log
        output_log = workdir / "output.log"
        output_log.write_text(result.stdout + result.stderr)

        # ── Assert exit code ──
        assert result.returncode == 0, (
            f"Gaussian failed (exit {result.returncode}):\n"
            f"{result.stderr[:1000]}"
        )

        # ── Assert output file exists ──
        assert output_log.exists(), "output.log not created"

        # ── Assert success strings in output ──
        output_text = output_log.read_text()
        assert "Normal termination of Gaussian" in output_text, (
            "Missing 'Normal termination of Gaussian' in output"
        )
        assert "SCF Done:" in output_text, (
            "Missing 'SCF Done:' energy in output"
        )

        # ── Parse and verify energy ──
        from qmatsuite.drivers.gaussian.parser import parse_log_file

        parsed = parse_log_file(output_log)
        assert parsed["normal_termination"] is True
        assert "scf_energy" in parsed
        # Water HF/STO-3G energy should be around -74.96 Hartree
        energy = parsed["scf_energy"]["energy_hartree"]
        assert -76.0 < energy < -73.0, (
            f"Energy {energy} Hartree outside expected range for water"
        )

    def test_h2o_opt_raw(self, gaussian_workdir):
        """Run H2O B3LYP/STO-3G optimization via raw subprocess."""
        workdir = gaussian_workdir

        gjf_content = """\
%mem=500MB
%nproc=1
%chk=water_opt.chk
#p B3LYP/STO-3G Opt

Water geometry optimization

0 1
 O   0.0000000000   0.0000000000   0.1200000000
 H   0.0000000000   0.8000000000  -0.4800000000
 H   0.0000000000  -0.8000000000  -0.4800000000

"""
        (workdir / "input.gjf").write_text(gjf_content)

        gaussian_bin = _find_gaussian()
        env = _setup_gaussian_env(gaussian_bin)

        with open(workdir / "input.gjf", "r") as stdin_file:
            result = subprocess.run(
                [gaussian_bin],
                stdin=stdin_file,
                capture_output=True,
                text=True,
                cwd=str(workdir),
                env=env,
                timeout=600,
            )

        output_log = workdir / "output.log"
        output_log.write_text(result.stdout + result.stderr)

        assert result.returncode == 0, f"Gaussian failed:\n{result.stderr[:500]}"

        output_text = output_log.read_text()
        assert "Normal termination of Gaussian" in output_text
        assert "Optimization completed" in output_text or "Stationary point found" in output_text

        from qmatsuite.drivers.gaussian.parser import parse_log_file

        parsed = parse_log_file(output_log)
        assert parsed["normal_termination"] is True
        assert "optimization" in parsed
        assert parsed["optimization"]["converged"] is True
        assert parsed["optimization"]["n_steps"] > 0

    def test_ethylene_mp2_raw(self, gaussian_workdir):
        """Run ethylene MP2/STO-3G calculation and verify MP2 energy is lower than HF."""
        workdir = gaussian_workdir

        gjf_content = """\
%mem=500MB
%nproc=1
%chk=ethylene_mp2.chk
#p MP2/STO-3G

Ethylene MP2 single point

0 1
 C   0.0000000000   0.0000000000   0.6695000000
 C   0.0000000000   0.0000000000  -0.6695000000
 H   0.0000000000   0.9289000000   1.2321000000
 H   0.0000000000  -0.9289000000   1.2321000000
 H   0.0000000000   0.9289000000  -1.2321000000
 H   0.0000000000  -0.9289000000  -1.2321000000

"""
        (workdir / "input.gjf").write_text(gjf_content)

        gaussian_bin = _find_gaussian()
        env = _setup_gaussian_env(gaussian_bin)

        with open(workdir / "input.gjf", "r") as stdin_file:
            result = subprocess.run(
                [gaussian_bin],
                stdin=stdin_file,
                capture_output=True,
                text=True,
                cwd=str(workdir),
                env=env,
                timeout=600,
            )

        output_log = workdir / "output.log"
        output_log.write_text(result.stdout + result.stderr)

        assert result.returncode == 0, f"Gaussian failed:\n{result.stderr[:500]}"

        from qmatsuite.drivers.gaussian.parser import parse_log_file

        parsed = parse_log_file(output_log)
        assert parsed["normal_termination"] is True
        assert "mp2" in parsed

        # MP2 energy should be lower (more negative) than HF energy
        # because correlation energy is negative
        hf_energy = parsed["mp2"]["hf_energy_hartree"]
        mp2_energy = parsed["mp2"]["mp2_energy_hartree"]
        assert mp2_energy < hf_energy, (
            f"MP2 energy ({mp2_energy}) should be lower than HF ({hf_energy})"
        )


# =====================================================================
# Test 2: Driver registration & discovery
# =====================================================================


class TestGaussianDriverRegistration:
    """Tests that the Gaussian driver is registered and discoverable."""

    def test_driver_registry_lookup(self):
        """Verify Gaussian driver is accessible via DriverRegistry."""
        import qmatsuite.drivers.gaussian  # noqa: F401 — triggers registration
        from qmatsuite.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("gaussian")
        assert driver is not None
        assert driver.PREFIX == "gaussian"
        assert driver.engine_family == "gaussian"
        assert driver.display_name == "Gaussian"
        assert driver.driver_api_version == "1.0.0"
        assert "scf" in driver.SUPPORTED_GEN_STEPS
        assert "relax" in driver.SUPPORTED_GEN_STEPS

    def test_step_type_lookup(self):
        """Verify gaussian_scf step type resolves through registry."""
        import qmatsuite.drivers.gaussian  # noqa: F401
        from qmatsuite.core.driver_registry import DriverRegistry

        handler = DriverRegistry.get_handler("gaussian_scf")
        assert handler is not None
        assert callable(handler)

    def test_materialization_map(self):
        """Verify scf -> gaussian_scf materialization."""
        import qmatsuite.drivers.gaussian  # noqa: F401
        from qmatsuite.core.driver_registry import DriverRegistry

        spec = DriverRegistry.materialize_step_type("gaussian", "scf")
        assert spec == "gaussian_scf"

    def test_engine_discovery(self):
        """Verify Gaussian is discovered via centralized engine discovery."""
        assert is_engine_available("gaussian", project_root=_REPO_ROOT), "Gaussian should be discovered"


# =====================================================================
# Test 3: Full project-level calculation workflow
# =====================================================================


class TestGaussianProjectLevel:
    """End-to-end test: project -> calc -> step -> run."""

    def test_gaussian_scf_project_workflow(self, tmp_path):
        """
        Full workflow:
        1. Create project
        2. Import H2O molecule via API
        3. Create calculation with engine=gaussian
        4. Add SCF step
        5. Run the step (real Gaussian binary)
        6. Assert artifacts exist and output is correct
        """
        # Ensure g09root is set for this test
        if "g09root" not in os.environ and _BUNDLED_GAUSSIAN.exists():
            os.environ["g09root"] = str(_BUNDLED_GAUSSIAN)

        from qmatsuite.api import QMSService

        # ── Setup: project in .tmp/gaussian/ ──
        unique_id = f"gaussian_e2e_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        test_dir = _REPO_ROOT / ".tmp" / "gaussian" / unique_id
        test_dir.mkdir(parents=True, exist_ok=True)

        project_root = QMSService.init_project(test_dir / "gaussian_scf_project")

        # ── Import H2O molecule via API ──
        h2o = Molecule(
            ["O", "H", "H"],
            [
                [0.0, 0.0, 0.12],
                [0.0, 0.78, -0.47],
                [0.0, -0.78, -0.47],
            ],
        )
        h2o_xyz = tmp_path / "h2o.xyz"
        h2o.to(str(h2o_xyz), fmt="xyz")

        svc = QMSService(project_root)
        imported = svc.structure.import_file(h2o_xyz, name="H2O")
        structure_ulid = imported.meta.ulid

        # ── Create calculation with engine=gaussian ──
        calc_result = svc.project.init_calculation(
            name="h2o_gaussian_scf",
            structure_selector=structure_ulid,
        )
        calc_ulid = calc_result.ulid
        if calc_result.absolute_path.is_dir():
            calc_dir = calc_result.absolute_path
        else:
            calc_dir = calc_result.absolute_path.parent

        # Set engine_family to gaussian
        calc_yaml = calc_dir / "calculation.yaml"
        calc_data = yaml.safe_load(calc_yaml.read_text())
        calc_data["engine_family"] = "gaussian"
        calc_data["structure_kind"] = "molecule"
        calc_yaml.write_text(yaml.dump(calc_data))

        # ── Add SCF step with parameters ──
        scf_step_result = svc.calculation.add_step(
            calc_ulid,
            step_type_gen="scf",
            name="hf_sp",
            params={
                "method": "HF",
                "basis": "STO-3G",
            },
        )
        scf_step_ulid = scf_step_result.ulid

        # ── Run the SCF step (calls real Gaussian) ──
        run_result = svc.run.run_step(
            calc_selector=calc_ulid,
            step_selector=scf_step_ulid,
        )

        assert run_result.status == "completed", (
            f"Gaussian SCF step failed: "
            f"{run_result.error.message if run_result.error else 'unknown'}"
        )

        # ── Assert working directory artifacts ──
        raw_dir = calc_dir / "calc" / "raw"
        step_work_dir = raw_dir / scf_step_ulid

        if step_work_dir.exists():
            # Check for Gaussian output files
            assert (step_work_dir / "output.log").exists(), "output.log missing"
            assert (step_work_dir / "input.gjf").exists(), "input.gjf missing"

            # Check for success strings in output.log
            output_text = (step_work_dir / "output.log").read_text()
            assert "Normal termination of Gaussian" in output_text, (
                "Missing normal termination in output"
            )
            assert "SCF Done:" in output_text, (
                "Missing SCF Done in output"
            )

    def test_gaussian_relax_project_workflow(self, tmp_path):
        """
        Full workflow for geometry optimization:
        1. Create project
        2. Import H2O molecule
        3. Create calculation with engine=gaussian
        4. Add relax step
        5. Run the step
        6. Assert optimization converged
        """
        # Ensure g09root is set for this test
        if "g09root" not in os.environ and _BUNDLED_GAUSSIAN.exists():
            os.environ["g09root"] = str(_BUNDLED_GAUSSIAN)

        from qmatsuite.api import QMSService

        # ── Setup ──
        unique_id = f"gaussian_relax_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        test_dir = _REPO_ROOT / ".tmp" / "gaussian" / unique_id
        test_dir.mkdir(parents=True, exist_ok=True)

        project_root = QMSService.init_project(test_dir / "gaussian_relax_project")

        # ── Import molecule ──
        h2o = Molecule(
            ["O", "H", "H"],
            [
                [0.0, 0.0, 0.12],
                [0.0, 0.80, -0.48],  # Slightly distorted
                [0.0, -0.80, -0.48],
            ],
        )
        h2o_xyz = tmp_path / "h2o_distorted.xyz"
        h2o.to(str(h2o_xyz), fmt="xyz")

        svc = QMSService(project_root)
        imported = svc.structure.import_file(h2o_xyz, name="H2O_distorted")
        structure_ulid = imported.meta.ulid

        # ── Create calculation ──
        calc_result = svc.project.init_calculation(
            name="h2o_gaussian_relax",
            structure_selector=structure_ulid,
        )
        calc_ulid = calc_result.ulid
        calc_dir = (
            calc_result.absolute_path
            if calc_result.absolute_path.is_dir()
            else calc_result.absolute_path.parent
        )

        # Set engine_family to gaussian
        calc_yaml = calc_dir / "calculation.yaml"
        calc_data = yaml.safe_load(calc_yaml.read_text())
        calc_data["engine_family"] = "gaussian"
        calc_data["structure_kind"] = "molecule"
        calc_yaml.write_text(yaml.dump(calc_data))

        # ── Add relax step ──
        relax_step_result = svc.calculation.add_step(
            calc_ulid,
            step_type_gen="relax",
            name="optimize",
            params={
                "method": "HF",
                "basis": "STO-3G",
            },
        )
        relax_step_ulid = relax_step_result.ulid

        # ── Run the relax step ──
        run_result = svc.run.run_step(
            calc_selector=calc_ulid,
            step_selector=relax_step_ulid,
        )

        assert run_result.status == "completed", (
            f"Gaussian relax step failed: "
            f"{run_result.error.message if run_result.error else 'unknown'}"
        )

        # ── Assert output ──
        raw_dir = calc_dir / "calc" / "raw"
        step_work_dir = raw_dir / relax_step_ulid

        if step_work_dir.exists():
            output_log = step_work_dir / "output.log"
            assert output_log.exists(), "output.log missing"

            output_text = output_log.read_text()
            assert "Normal termination of Gaussian" in output_text
            assert (
                "Optimization completed" in output_text
                or "Stationary point found" in output_text
            ), "Optimization did not converge"


# =====================================================================
# Test 4: Parser tests against exploration artifacts
# =====================================================================


class TestGaussianParser:
    """Parser tests against reference output files."""

    def test_parse_scf_energy(self):
        """Test parsing SCF energy from output."""
        from qmatsuite.drivers.gaussian.parser import parse_scf_energy

        # Sample output text
        text = """
         SCF Done:  E(RHF) =  -74.9631155184     A.U. after    7 cycles
        """
        result = parse_scf_energy(text)
        assert result is not None
        assert result.method == "RHF"
        assert result.energy_hartree == pytest.approx(-74.963, abs=0.001)
        assert result.scf_cycles == 7

    def test_parse_mp2_energy(self):
        """Test parsing MP2 energy from output."""
        from qmatsuite.drivers.gaussian.parser import parse_mp2_energy

        text = """
         SCF Done:  E(RHF) =  -77.0728565000     A.U. after   10 cycles
         E2 =    -0.1218324231D+00 EUMP2 =    -0.77194688921108D+02
        """
        result = parse_mp2_energy(text)
        assert result is not None
        assert result.hf_energy_hartree == pytest.approx(-77.073, abs=0.001)
        assert result.mp2_energy_hartree == pytest.approx(-77.195, abs=0.001)
        assert result.e2_correlation_hartree < 0  # Correlation is negative

    def test_parse_optimization(self):
        """Test parsing optimization results."""
        from qmatsuite.drivers.gaussian.parser import parse_optimization

        text = """
         SCF Done:  E(RB3LYP) =  -76.4000000000     A.U. after    5 cycles
         SCF Done:  E(RB3LYP) =  -76.4100000000     A.U. after    4 cycles
         SCF Done:  E(RB3LYP) =  -76.4200000000     A.U. after    3 cycles
         Optimization completed.
        """
        result = parse_optimization(text)
        assert result is not None
        assert result.converged is True
        assert result.n_steps == 3

    def test_parse_termination_status(self):
        """Test parsing termination status."""
        from qmatsuite.drivers.gaussian.parser import parse_termination_status

        # Normal termination
        success, msg = parse_termination_status("Normal termination of Gaussian 09")
        assert success is True
        assert "Normal termination" in msg

        # Error termination
        success, msg = parse_termination_status("Error termination via Lnk1e")
        assert success is False
        assert "Error termination" in msg
