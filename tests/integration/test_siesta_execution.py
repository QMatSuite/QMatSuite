"""
Integration tests for Siesta execution.

These tests run actual Siesta calculations and verify results.
Tests are skipped if Siesta is not installed.

To run these tests:
    conda install -c conda-forge siesta
    pytest tests/integration/test_siesta_execution.py -v
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from quantumvitas.core.engines.discovery import is_engine_available

# Repo root for .tmp directory
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PP_DIR = _REPO_ROOT / "engine_explorations" / "siesta" / "pseudopotentials"

pytestmark = pytest.mark.skipif(
    not is_engine_available("siesta"),
    reason="Siesta not installed - install with: conda install -c conda-forge siesta",
)


@pytest.fixture
def siesta_workdir(tmp_path_factory):
    """Create a working directory for Siesta tests under .tmp/siesta/."""
    base = _REPO_ROOT / ".tmp" / "siesta"
    base.mkdir(parents=True, exist_ok=True)
    workdir = tmp_path_factory.mktemp("siesta", numbered=True)
    return workdir


def _stage_pseudopotentials(workdir: Path, elements: list[str]) -> None:
    """Copy PSML pseudopotential files into the working directory."""
    for elem in elements:
        src = _PP_DIR / f"{elem}.psml"
        if src.exists():
            shutil.copy2(src, workdir / f"{elem}.psml")
        else:
            pytest.skip(
                f"Pseudopotential {elem}.psml not found at {_PP_DIR}. "
                f"Download from http://www.pseudo-dojo.org"
            )


def _find_siesta() -> str:
    """Find the siesta binary."""
    found = shutil.which("siesta")
    assert found is not None, "siesta binary not found in PATH"
    return found


def _run_siesta(workdir: Path, fdf_name: str, out_name: str, timeout: int = 300) -> str:
    """Run siesta and return stdout content."""
    siesta_bin = _find_siesta()
    fdf_path = workdir / fdf_name
    out_path = workdir / out_name

    with open(fdf_path) as stdin_f, open(out_path, "w") as stdout_f:
        result = subprocess.run(
            [siesta_bin],
            stdin=stdin_f,
            stdout=stdout_f,
            stderr=subprocess.PIPE,
            cwd=str(workdir),
            timeout=timeout,
        )

    stderr = result.stderr.decode("utf-8", errors="replace")
    assert result.returncode == 0, (
        f"Siesta failed (exit {result.returncode}):\n{stderr[:1000]}"
    )

    return out_path.read_text()


class TestSiestaSCF:
    """Integration tests for Siesta SCF calculations."""

    def test_h2o_scf_molecular(self, siesta_workdir):
        """Run H2O molecule SCF and verify energy and convergence."""
        workdir = siesta_workdir
        _stage_pseudopotentials(workdir, ["H", "O"])

        # Write FDF input
        from quantumvitas.drivers.siesta.writer import write_fdf

        write_fdf(
            output_path=workdir / "h2o.fdf",
            system_name="Water molecule",
            system_label="h2o",
            species=[
                {"index": 1, "atomic_number": 8, "label": "O"},
                {"index": 2, "atomic_number": 1, "label": "H"},
            ],
            lattice_constant=10.0,
            lattice_vectors=[
                [1.0, 0.0, 0.0],
                [0.0, 1.0, 0.0],
                [0.0, 0.0, 1.0],
            ],
            atoms=[
                {"x": 0.0, "y": 0.0, "z": 0.0, "species_index": 1},
                {"x": 0.757, "y": 0.586, "z": 0.0, "species_index": 2},
                {"x": -0.757, "y": 0.586, "z": 0.0, "species_index": 2},
            ],
            params={
                "PAO.BasisSize": "SZ",
                "MeshCutoff": "100.0 Ry",
            },
        )

        output = _run_siesta(workdir, "h2o.fdf", "h2o.out")

        # ── Assert success strings in output ──
        assert "SCF Convergence" in output, "SCF did not converge"
        assert "E_KS(eV)" in output, "No total energy in output"
        assert "Job completed" in output, "Job did not complete normally"

        # ── Assert crucial artifacts exist ──
        assert (workdir / "0_NORMAL_EXIT").exists(), "0_NORMAL_EXIT marker missing"
        assert (workdir / "h2o.EIG").exists(), "Eigenvalue file missing"
        assert (workdir / "h2o.FA").exists(), "Forces file missing"
        assert (workdir / "h2o.XV").exists(), "Positions file missing"
        assert (workdir / "h2o.STRUCT_OUT").exists(), "Structure output missing"
        assert (workdir / "h2o.DM").exists(), "Density matrix file missing"
        assert (workdir / "FORCE_STRESS").exists(), "FORCE_STRESS missing"
        assert (workdir / "OUTVARS.yml").exists(), "OUTVARS.yml missing"

        # ── Parse and validate energy ──
        from quantumvitas.drivers.siesta.parser import parse_main_output

        parsed = parse_main_output(workdir / "h2o.out")
        assert parsed["scf_converged"] is True
        assert parsed["n_scf_iterations"] > 0
        assert parsed["n_atoms"] == 3

        energy = parsed["total_energy_eV"]
        assert energy is not None
        # Golden ref: -474.1735 eV (SZ basis, MeshCutoff=100 Ry)
        assert -500.0 < energy < -400.0, f"Energy {energy} eV outside expected range"

    def test_si_scf_periodic(self, siesta_workdir):
        """Run Si bulk SCF with k-points and verify energy."""
        workdir = siesta_workdir
        _stage_pseudopotentials(workdir, ["Si"])

        from quantumvitas.drivers.siesta.writer import write_fdf

        write_fdf(
            output_path=workdir / "si_scf.fdf",
            system_name="Silicon bulk",
            system_label="si_scf",
            species=[
                {"index": 1, "atomic_number": 14, "label": "Si"},
            ],
            lattice_constant=5.43,
            lattice_vectors=[
                [0.5, 0.5, 0.0],
                [0.0, 0.5, 0.5],
                [0.5, 0.0, 0.5],
            ],
            atoms=[
                {"x": 0.0, "y": 0.0, "z": 0.0, "species_index": 1},
                {"x": 0.25, "y": 0.25, "z": 0.25, "species_index": 1},
            ],
            coord_format="ScaledCartesian",
            params={
                "kgrid": [
                    [4, 0, 0, 0.5],
                    [0, 4, 0, 0.5],
                    [0, 0, 4, 0.5],
                ],
                "MeshCutoff": "200.0 Ry",
            },
        )

        output = _run_siesta(workdir, "si_scf.fdf", "si_scf.out")

        # ── Assert success strings ──
        assert "SCF Convergence" in output
        assert "E_KS(eV)" in output
        assert "Job completed" in output

        # ── Assert artifacts ──
        assert (workdir / "0_NORMAL_EXIT").exists()
        assert (workdir / "si_scf.EIG").exists()
        assert (workdir / "si_scf.DM").exists()
        assert (workdir / "FORCE_STRESS").exists()

        # ── Parse and validate ──
        from quantumvitas.drivers.siesta.parser import parse_main_output, parse_eig_file

        parsed = parse_main_output(workdir / "si_scf.out")
        assert parsed["scf_converged"] is True
        assert parsed["n_atoms"] == 2

        energy = parsed["total_energy_eV"]
        # Golden ref: -230.0361 eV (DZP, MeshCutoff=200 Ry, 4x4x4)
        assert -250.0 < energy < -200.0, f"Energy {energy} eV outside expected range"

        # Verify eigenvalues file
        eig = parse_eig_file(workdir / "si_scf.EIG")
        assert eig["n_kpoints"] > 1, "Should have multiple k-points"
        assert eig["n_bands"] > 0, "Should have bands"


class TestSiestaRelax:
    """Integration tests for Siesta relaxation."""

    def test_si_cg_relaxation(self, siesta_workdir):
        """Run Si CG variable-cell relaxation and verify trajectory."""
        workdir = siesta_workdir
        _stage_pseudopotentials(workdir, ["Si"])

        from quantumvitas.drivers.siesta.writer import write_fdf

        write_fdf(
            output_path=workdir / "si_relax.fdf",
            system_name="Silicon relaxation",
            system_label="si_relax",
            species=[
                {"index": 1, "atomic_number": 14, "label": "Si"},
            ],
            lattice_constant=5.50,
            lattice_vectors=[
                [0.5, 0.5, 0.0],
                [0.0, 0.5, 0.5],
                [0.5, 0.0, 0.5],
            ],
            atoms=[
                {"x": 0.0, "y": 0.0, "z": 0.0, "species_index": 1},
                {"x": 0.25, "y": 0.25, "z": 0.25, "species_index": 1},
            ],
            coord_format="ScaledCartesian",
            params={
                "kgrid": [
                    [4, 0, 0, 0.5],
                    [0, 4, 0, 0.5],
                    [0, 0, 4, 0.5],
                ],
                "MeshCutoff": "200.0 Ry",
                "MD.TypeOfRun": "CG",
                "MD.NumCGsteps": 10,
                "MD.MaxForceTol": "0.04 eV/Ang",
                "MD.VariableCell": True,
                "MD.MaxStressTol": "1.0 GPa",
            },
        )

        output = _run_siesta(workdir, "si_relax.fdf", "si_relax.out", timeout=600)

        # ── Assert success strings ──
        assert "Job completed" in output
        assert "E_KS(eV)" in output

        # ── Assert relaxation artifacts ──
        assert (workdir / "0_NORMAL_EXIT").exists()
        assert (workdir / "si_relax.STRUCT_OUT").exists(), "Final structure missing"
        assert (workdir / "si_relax.EIG").exists(), "Eigenvalue file missing"
        assert (workdir / "si_relax.DM").exists(), "Density matrix missing"
        assert (workdir / "FORCE_STRESS").exists(), "FORCE_STRESS missing"

        # ── Parse output ──
        from quantumvitas.drivers.siesta.parser import (
            parse_main_output,
            parse_struct_out,
        )

        parsed = parse_main_output(workdir / "si_relax.out")
        assert parsed["normal_exit"] is True
        assert parsed["scf_converged"] is True

        energy = parsed["total_energy_eV"]
        assert energy is not None
        # Si bulk energy should be in reasonable range
        assert -250.0 < energy < -200.0, f"Energy {energy} eV outside expected range"

        # Final structure should exist
        struct = parse_struct_out(workdir / "si_relax.STRUCT_OUT")
        assert struct["n_atoms"] == 2

        # CG trajectory (MDE) may or may not be produced depending on convergence
        mde_path = workdir / "si_relax.MDE"
        if mde_path.exists():
            from quantumvitas.drivers.siesta.parser import parse_mde_file
            mde = parse_mde_file(mde_path)
            assert mde["n_steps"] >= 1


class TestSiestaEngineDiscovery:
    """Test engine discovery and driver registry integration."""

    def test_engine_available(self):
        """Siesta should be discoverable via is_engine_available."""
        assert is_engine_available("siesta") is True

    def test_driver_registry_lookup(self):
        """Verify Siesta driver is accessible via DriverRegistry."""
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        driver = DriverRegistry.get_driver("siesta")
        assert driver is not None
        assert driver.PREFIX == "siesta"
        assert driver.engine_family == "siesta"

    def test_step_type_resolution(self):
        """Verify step types resolve correctly through the registry."""
        import quantumvitas.drivers.siesta  # noqa: F401
        from quantumvitas.core.driver_registry import DriverRegistry

        for gen_type in ["scf", "relax", "md", "bands", "dos"]:
            spec_type = DriverRegistry.materialize_step_type("siesta", gen_type)
            assert spec_type == f"siesta_{gen_type}"

            handler = DriverRegistry.get_handler(spec_type)
            assert handler is not None
            assert callable(handler)

    def test_workflow_registry_has_siesta_types(self):
        """Verify Siesta step types are in the workflow StepTypeRegistry."""
        from quantumvitas.workflow.registry import get_registry

        registry = get_registry()
        siesta_specs = registry.list_by_engine_machine("siesta")
        assert "siesta_scf" in siesta_specs
        assert "siesta_relax" in siesta_specs
        assert "siesta_md" in siesta_specs
        assert "siesta_bands" in siesta_specs
        assert "siesta_dos" in siesta_specs


class TestSiestaParser:
    """Test parser against real Siesta output from artifacts."""

    def test_parse_h2o_artifacts(self):
        """Parse H2O SCF golden artifacts."""
        from quantumvitas.drivers.siesta.parser import parse_siesta_workdir

        artifact_dir = _REPO_ROOT / "engine_explorations" / "siesta" / "artifacts" / "h2o_scf"
        if not artifact_dir.exists():
            pytest.skip("H2O artifacts not found")

        data = parse_siesta_workdir(artifact_dir, "h2o")

        assert data["normal_exit"] is True
        assert "main_output" in data
        assert data["main_output"]["scf_converged"] is True
        assert data["main_output"]["total_energy_eV"] is not None
        assert data["main_output"]["n_atoms"] == 3

    def test_parse_si_scf_artifacts(self):
        """Parse Si SCF golden artifacts."""
        from quantumvitas.drivers.siesta.parser import parse_siesta_workdir

        artifact_dir = _REPO_ROOT / "engine_explorations" / "siesta" / "artifacts" / "si_scf"
        if not artifact_dir.exists():
            pytest.skip("Si SCF artifacts not found")

        data = parse_siesta_workdir(artifact_dir, "si_scf")

        assert data["normal_exit"] is True
        assert data["main_output"]["scf_converged"] is True
        assert data["main_output"]["n_atoms"] == 2

        # Should have eigenvalues
        assert "eigenvalues" in data
        assert data["eigenvalues"]["n_kpoints"] > 1

    def test_parse_si_relax_artifacts(self):
        """Parse Si relaxation golden artifacts."""
        from quantumvitas.drivers.siesta.parser import parse_siesta_workdir

        artifact_dir = _REPO_ROOT / "engine_explorations" / "siesta" / "artifacts" / "si_relax"
        if not artifact_dir.exists():
            pytest.skip("Si relax artifacts not found")

        data = parse_siesta_workdir(artifact_dir, "si_relax")

        assert data["normal_exit"] is True
        assert "trajectory" in data
        assert data["trajectory"]["n_steps"] > 1
