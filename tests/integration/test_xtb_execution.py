"""
Integration tests for xTB execution.

These tests run actual xTB calculations and verify results.
Tests are skipped if xTB is not installed.

To run these tests:
    conda install -c conda-forge xtb
    pytest tests/integration/test_xtb_execution.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest
import yaml
from pymatgen.core import Molecule

from quantumvitas.core.engines.discovery import is_engine_available

# Repo root for .tmp directory
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

pytestmark = pytest.mark.skipif(
    not is_engine_available("xtb"),
    reason="xTB not installed - install with: conda install -c conda-forge xtb",
)


@pytest.fixture
def xtb_workdir(tmp_path_factory):
    """Create a working directory for xTB tests under .tmp/xtb/."""
    base = _REPO_ROOT / ".tmp" / "xtb"
    base.mkdir(parents=True, exist_ok=True)
    workdir = tmp_path_factory.mktemp("xtb", numbered=True)
    return workdir


def _find_xtb() -> str:
    """Find the xtb binary."""
    found = shutil.which("xtb")
    assert found is not None, "xtb binary not found in PATH"
    return found


# =====================================================================
# Test 1: Raw xTB binary — H2O optimization
# =====================================================================


class TestXTBRawExecution:
    """Tests that call the xTB binary directly (no driver framework)."""

    def test_h2o_relax_raw(self, xtb_workdir):
        """Run H2O optimization via raw subprocess and verify all outputs."""
        workdir = xtb_workdir

        # Write input XYZ
        xyz_content = """\
3
water molecule
 O   0.0000000000   0.0000000000   0.1173000000
 H   0.0000000000   0.7572000000  -0.4692000000
 H   0.0000000000  -0.7572000000  -0.4692000000
"""
        (workdir / "input.xyz").write_text(xyz_content)

        # Run xTB optimization
        xtb_bin = _find_xtb()
        result = subprocess.run(
            [xtb_bin, "input.xyz", "--gfn", "2", "--opt"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Save stdout for inspection
        stdout_path = workdir / "xtb.out"
        stdout_path.write_text(result.stdout + result.stderr)

        # ── Assert exit code ──
        assert result.returncode == 0, (
            f"xTB failed (exit {result.returncode}):\n"
            f"{result.stderr[:1000]}"
        )

        # ── Assert crucial output files exist ──
        assert (workdir / "xtbopt.xyz").exists(), "xtbopt.xyz missing"
        assert (workdir / ".xtboptok").exists(), ".xtboptok marker missing"
        assert (workdir / "charges").exists(), "charges file missing"
        assert (workdir / "wbo").exists(), "wbo file missing"
        assert (workdir / "xtbopt.log").exists(), "xtbopt.log trajectory missing"
        assert stdout_path.exists(), "xtb.out not saved"

        # ── Assert success strings in output ──
        # xTB writes main output to stdout but "normal termination" to stderr
        combined_output = result.stdout + result.stderr
        assert "normal termination of xtb" in combined_output, (
            "Missing 'normal termination of xtb' in output"
        )
        assert "GEOMETRY OPTIMIZATION CONVERGED" in result.stdout, (
            "Missing convergence message in stdout"
        )
        assert "TOTAL ENERGY" in result.stdout, (
            "Missing 'TOTAL ENERGY' in stdout"
        )

        # ── Parse and verify xtbopt.xyz ──
        from quantumvitas.drivers.xtb.parser import parse_xtbopt_xyz

        geo = parse_xtbopt_xyz(workdir / "xtbopt.xyz")
        assert geo["n_atoms"] == 3
        # Water energy should be around -5.070 Eh
        assert -6.0 < geo["energy_Eh"] < -4.0, (
            f"Energy {geo['energy_Eh']} Eh outside expected range"
        )

        # ── Parse and verify combined output ──
        from quantumvitas.drivers.xtb.parser import parse_xtb_stdout

        parsed = parse_xtb_stdout(combined_output)
        assert parsed["converged"] is True
        assert parsed["opt_cycles"] > 0
        assert parsed["normal_termination"] is True
        assert "total_energy_Eh" in parsed
        assert "gradient_norm" in parsed

    def test_ethanol_relax_tight(self, xtb_workdir):
        """Run ethanol optimization with tight convergence."""
        workdir = xtb_workdir

        xyz_content = """\
9
ethanol
 C  -0.7480000000   0.0150000000   0.0240000000
 C   0.7480000000  -0.0150000000  -0.0240000000
 O   1.1680000000   0.7540000000   1.1010000000
 H  -1.1480000000   1.0250000000  -0.0940000000
 H  -1.0980000000  -0.5840000000  -0.8220000000
 H  -1.1380000000  -0.4200000000   0.9560000000
 H   1.1030000000  -1.0450000000   0.0630000000
 H   1.1260000000   0.4580000000  -0.9440000000
 H   0.8150000000   0.2680000000   1.9400000000
"""
        (workdir / "input.xyz").write_text(xyz_content)

        xtb_bin = _find_xtb()
        result = subprocess.run(
            [xtb_bin, "input.xyz", "--gfn", "2", "--opt", "tight"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, f"xTB failed:\n{result.stderr[:500]}"
        assert "GEOMETRY OPTIMIZATION CONVERGED" in result.stdout
        assert "normal termination of xtb" in (result.stdout + result.stderr)
        assert (workdir / "xtbopt.xyz").exists()
        assert (workdir / ".xtboptok").exists()

        from quantumvitas.drivers.xtb.parser import parse_xtbopt_xyz

        geo = parse_xtbopt_xyz(workdir / "xtbopt.xyz")
        assert geo["n_atoms"] == 9
        # Ethanol energy should be around -11.394 Eh
        assert -13.0 < geo["energy_Eh"] < -10.0


# =====================================================================
# Test 2: Driver registration & discovery
# =====================================================================


class TestXTBDriverRegistration:
    """Tests that the xTB driver is registered and discoverable."""

    def test_driver_registry_lookup(self):
        """Verify xTB driver is accessible via DriverRegistry."""
        import quantumvitas.drivers.xtb  # noqa: F401 — triggers registration
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("xtb")
        assert driver is not None
        assert driver.PREFIX == "xtb"
        assert driver.engine_family == "xtb"
        assert driver.display_name == "xTB"
        assert driver.driver_api_version == "1.0.0"
        assert "relax" in driver.SUPPORTED_GEN_STEPS

    def test_step_type_lookup(self):
        """Verify xtb_relax step type resolves through registry."""
        import quantumvitas.drivers.xtb  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        handler = DriverRegistry.get_handler("xtb_relax")
        assert handler is not None
        assert callable(handler)

    def test_materialization_map(self):
        """Verify relax -> xtb_relax materialization."""
        import quantumvitas.drivers.xtb  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        spec = DriverRegistry.materialize_step_type("xtb", "relax")
        assert spec == "xtb_relax"

    def test_engine_discovery(self):
        """Verify xTB is discovered via centralized engine discovery."""
        assert is_engine_available("xtb"), "xTB should be discovered"


# =====================================================================
# Test 3: Full project-level relax + promote workflow
# =====================================================================


class TestXTBRelaxPromote:
    """End-to-end test: project -> calc -> relax step -> run -> promote."""

    def test_xtb_relax_and_promote(self, tmp_path):
        """
        Full workflow:
        1. Create project
        2. Import H2O structure via API
        3. Create calculation with engine=xtb
        4. Add relax step
        5. Run the step (real xTB binary)
        6. Assert artifacts exist
        7. Promote relaxed structure
        8. Verify promoted structure differs from original
        """
        from quantumvitas.api import QVService
        from quantumvitas.execution.relax_artifacts import (
            get_generated_structure_path,
            read_generated_structure,
        )

        # ── Setup: project in .tmp/xtb/ ──
        unique_id = f"xtb_e2e_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        test_dir = _REPO_ROOT / ".tmp" / "xtb" / unique_id
        test_dir.mkdir(parents=True, exist_ok=True)

        project_root = QVService.init_project(test_dir / "xtb_relax_project")

        # ── Import H2O molecule via API ──
        # Write a temp XYZ file, then import through the proper API
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

        svc = QVService(project_root)
        imported = svc.structure.import_file(h2o_xyz, name="H2O")
        structure_ulid = imported.meta.ulid

        # ── Create calculation with engine=xtb ──
        calc_result = svc.project.init_calculation(
            name="h2o_xtb_relax",
            structure_selector=structure_ulid,
        )
        calc_ulid = calc_result.ulid
        if calc_result.absolute_path.is_dir():
            calc_dir = calc_result.absolute_path
        else:
            calc_dir = calc_result.absolute_path.parent

        # Set engine_family to xtb
        calc_yaml = calc_dir / "calculation.yaml"
        calc_data = yaml.safe_load(calc_yaml.read_text())
        calc_data["engine_family"] = "xtb"
        calc_data["structure_kind"] = "molecule"
        calc_yaml.write_text(yaml.dump(calc_data))

        # ── Add relax step ──
        relax_step_result = svc.calculation.add_step(
            calc_ulid,
            step_type_gen="relax",
            name="relax",
        )
        relax_step_ulid = relax_step_result.ulid

        # ── Run the relax step (calls real xTB) ──
        run_result = svc.run.run_step(
            calc_selector=calc_ulid,
            step_selector=relax_step_ulid,
        )

        assert run_result.status == "completed", (
            f"xTB relax step failed: "
            f"{run_result.error.message if run_result.error else 'unknown'}"
        )

        # ── Assert working directory artifacts ──
        # Find the actual working directory (calc/raw/{step_ulid}/)
        raw_dir = calc_dir / "calc" / "raw"
        step_work_dirs = list(raw_dir.glob(f"*{relax_step_ulid}*"))
        if not step_work_dirs:
            # May be directly under raw_dir with the ULID name
            step_work_dir = raw_dir / relax_step_ulid
        else:
            step_work_dir = step_work_dirs[0]

        if step_work_dir.exists():
            # Check for xTB output files
            assert (step_work_dir / "xtb.out").exists(), "xtb.out missing"
            assert (step_work_dir / "xtbopt.xyz").exists(), "xtbopt.xyz missing"

            # Check for success strings in xtb.out
            xtb_output = (step_work_dir / "xtb.out").read_text()
            assert "TOTAL ENERGY" in xtb_output, "Missing TOTAL ENERGY in output"
            assert "normal termination of xtb" in xtb_output, (
                "Missing normal termination in output"
            )

        # ── Assert generated structure (current.json) exists ──
        artifact_path = get_generated_structure_path(calc_dir, relax_step_ulid)
        assert artifact_path.exists(), (
            f"current.json should exist after relax. Path: {artifact_path}"
        )

        # ── Read and verify relaxed structure ──
        relaxed_structure = read_generated_structure(calc_dir, relax_step_ulid)
        assert relaxed_structure is not None
        assert len(relaxed_structure) == 3, "Should have 3 atoms (O, H, H)"

        # Verify the structure changed (optimizer moved atoms)
        original_o_pos = h2o[0].coords
        relaxed_o_pos = relaxed_structure[0].coords
        pos_changed = any(
            abs(a - b) > 1e-6
            for a, b in zip(original_o_pos, relaxed_o_pos)
        )
        assert pos_changed, "Relaxed positions should differ from original"

        # ── Promote relaxed structure to project resource ──
        promoted = svc.structure.promote_relax_structure(
            calculation_selector=calc_ulid,
            step_selector=relax_step_ulid,
            name="h2o_relaxed",
        )

        assert promoted.meta.ulid != structure_ulid, (
            "Promoted structure should have different ULID"
        )
        assert promoted.meta.name == "h2o_relaxed"

        # Verify promoted structure file exists
        structure_path = project_root / "structures" / f"{promoted.meta.slug}.json"
        assert structure_path.exists(), "Promoted structure file should exist"

        # ── Verify promoted structure can be used for a new calculation ──
        new_calc = svc.project.init_calculation(
            name="h2o_followup",
            structure_selector=promoted.meta.ulid,
        )
        assert new_calc.ulid != calc_ulid
        new_calc_dir = (
            new_calc.absolute_path
            if new_calc.absolute_path.is_dir()
            else new_calc.absolute_path.parent
        )
        new_calc_yaml = new_calc_dir / "calculation.yaml"
        new_calc_data = yaml.safe_load(new_calc_yaml.read_text())
        assert new_calc_data["structure_ulid"] == promoted.meta.ulid, (
            "New calculation should reference promoted structure"
        )

        # ── List structures and verify count ──
        all_structures = svc.structure.list()
        assert len(all_structures) >= 2, (
            "Should have at least original + promoted structure"
        )
