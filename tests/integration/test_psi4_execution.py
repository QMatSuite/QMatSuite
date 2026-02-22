"""
Integration tests for Psi4 execution.

These tests run actual Psi4 calculations and verify results.
Tests are skipped if Psi4 is not installed.

All tests use subprocess execution — pytest never imports psi4.
Only the runner subprocess (which may use conda Python) imports psi4.

To run these tests:
    conda install psi4 -c conda-forge
    pytest tests/integration/test_psi4_execution.py -v
"""

import json
import os
import subprocess
import pytest
from pathlib import Path

from qmatsuite.core.engines.discovery import discover_engine, is_engine_available

pytestmark = pytest.mark.skipif(
    not is_engine_available("psi4"),
    reason="Psi4 not installed - install with: conda install psi4 -c conda-forge"
)


# Water molecule coordinates (Angstrom)
H2O_ATOMS = [
    {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.117790},
    {"symbol": "H", "x": 0.0, "y": 0.755453, "z": -0.471161},
    {"symbol": "H", "x": 0.0, "y": -0.755453, "z": -0.471161},
]


def _get_psi4_python() -> str:
    """Get the Python executable that has Psi4."""
    result = discover_engine("psi4")
    if result.available and result.executable_path:
        return str(result.executable_path)
    return "python"


def _get_runner_env() -> dict:
    """Get environment for the runner subprocess.

    Adds the project's src/ to PYTHONPATH so the discovered Python
    (which may be conda) can import qmatsuite.
    """
    import qmatsuite
    env = os.environ.copy()
    src_dir = str(Path(qmatsuite.__file__).parent.parent)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{src_dir}:{existing}" if existing else src_dir
    return env


def _run_psi4_chain(job_chain: dict, working_dir: Path) -> dict:
    """Run a Psi4 calculation via subprocess (no psi4 import in test).

    Writes job_chain.json, runs the Psi4 runner module via subprocess
    using the discovered Psi4 Python, and returns parsed results.
    """
    job_chain_file = working_dir / "job_chain.json"
    job_chain_file.write_text(json.dumps(job_chain, indent=2))

    python = _get_psi4_python()
    cmd = [python, "-m", "qmatsuite.engines.psi4", str(job_chain_file)]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=working_dir,
        timeout=120,
        env=_get_runner_env(),
    )

    # Find and parse results.json from the target step artifacts dir
    target_ulid = job_chain["target_step_ulid"]
    for step in job_chain["chain_steps"]:
        if step["step_ulid"] == target_ulid:
            artifacts_dir = Path(step["step_artifacts_dir"])
            results_file = artifacts_dir / "results.json"
            if results_file.exists():
                return json.loads(results_file.read_text())

    # Fallback: try parsing stdout
    try:
        return json.loads(result.stdout)
    except Exception:
        return {
            "success": False,
            "error": f"Runner exited with code {result.returncode}. stderr: {result.stderr[:500]}",
        }


def _make_scf_chain(params: dict, tmp_path: Path) -> dict:
    """Build a single-step SCF chain job spec."""
    step_dir = tmp_path / "step_artifacts" / "step1"
    step_dir.mkdir(parents=True, exist_ok=True)
    return {
        "base_working_dir": str(tmp_path),
        "chain_steps": [
            {
                "step_ulid": "step1",
                "step_type_spec": "psi4_scf",
                "parameters": params,
                "step_artifacts_dir": str(step_dir),
            },
        ],
        "target_step_ulid": "step1",
        "resources": {},
    }


class TestPsi4SCF:
    """Integration tests for Psi4 SCF calculations."""

    def test_h2o_rhf_sto3g(self, tmp_path):
        """Run H2O RHF/STO-3G and verify energy."""
        params = {
            "method": "hf",
            "basis": "sto-3g",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = _run_psi4_chain(_make_scf_chain(params, tmp_path), tmp_path)

        assert result["success"], f"Calculation failed: {result.get('error')}"
        assert result["converged"]

        # H2O RHF/STO-3G reference: ~-74.96 Hartree
        energy = result["energy"]
        assert -76.0 < energy < -74.0, f"Energy {energy} outside expected range"
        assert result["n_atoms"] == 3

    def test_h2o_hf_ccpvdz(self, tmp_path):
        """Run H2O HF/cc-pVDZ and verify energy."""
        params = {
            "method": "hf",
            "basis": "cc-pvdz",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = _run_psi4_chain(_make_scf_chain(params, tmp_path), tmp_path)

        assert result["success"], f"Calculation failed: {result.get('error')}"

        # H2O HF/cc-pVDZ reference: ~-76.03 Hartree
        energy = result["energy"]
        assert -76.5 < energy < -75.5, f"Energy {energy} outside expected range for cc-pVDZ"

    def test_h2o_b3lyp_sto3g(self, tmp_path):
        """Run H2O B3LYP/STO-3G DFT and verify energy."""
        params = {
            "method": "scf",
            "xc": "b3lyp",
            "basis": "sto-3g",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = _run_psi4_chain(_make_scf_chain(params, tmp_path), tmp_path)

        assert result["success"], f"Calculation failed: {result.get('error')}"

        # B3LYP/STO-3G should give different energy from HF/STO-3G
        energy = result["energy"]
        assert -76.5 < energy < -74.5, f"Energy {energy} outside expected range for B3LYP"

    def test_output_files_created(self, tmp_path):
        """Verify output files are created in step artifacts dir."""
        params = {
            "method": "hf",
            "basis": "sto-3g",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = _run_psi4_chain(_make_scf_chain(params, tmp_path), tmp_path)
        assert result["success"]

        step_dir = tmp_path / "step_artifacts" / "step1"
        assert (step_dir / "results.json").exists()

    def test_psi4_variables_collected(self, tmp_path):
        """Verify Psi4 variables dict is populated."""
        params = {
            "method": "hf",
            "basis": "sto-3g",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = _run_psi4_chain(_make_scf_chain(params, tmp_path), tmp_path)
        assert result["success"]

        psi4_vars = result.get("psi4_variables", {})
        assert "SCF TOTAL ENERGY" in psi4_vars
        assert "NUCLEAR REPULSION ENERGY" in psi4_vars


class TestPsi4MP2Chain:
    """Integration tests for SCF → MP2 chain."""

    def test_scf_mp2_chain(self, tmp_path):
        """Run SCF → MP2 chain and verify energies."""
        scf_dir = tmp_path / "step_artifacts" / "scf_step"
        mp2_dir = tmp_path / "step_artifacts" / "mp2_step"
        scf_dir.mkdir(parents=True, exist_ok=True)
        mp2_dir.mkdir(parents=True, exist_ok=True)

        job_chain = {
            "base_working_dir": str(tmp_path),
            "chain_steps": [
                {
                    "step_ulid": "scf_step",
                    "step_type_spec": "psi4_scf",
                    "parameters": {
                        "method": "hf",
                        "basis": "cc-pvdz",
                        "atoms": H2O_ATOMS,
                        "charge": 0,
                        "multiplicity": 1,
                        "memory_mb": 500,
                        "nthreads": 1,
                    },
                    "step_artifacts_dir": str(scf_dir),
                },
                {
                    "step_ulid": "mp2_step",
                    "step_type_spec": "psi4_mp2",
                    "parameters": {
                        "basis": "cc-pvdz",
                    },
                    "step_artifacts_dir": str(mp2_dir),
                },
            ],
            "target_step_ulid": "mp2_step",
            "resources": {},
        }

        result = _run_psi4_chain(job_chain, tmp_path)

        assert result.get("success"), f"Chain failed: {result.get('error')}"

        # MP2 total energy should be lower than SCF (correlation is negative)
        total_energy = result["energy"]
        correlation = result.get("correlation_energy")

        # H2O HF/cc-pVDZ MP2 reference: ~-76.23 Hartree
        assert -76.5 < total_energy < -75.5, f"MP2 total energy {total_energy} outside range"
        assert correlation < 0, f"Correlation energy should be negative, got {correlation}"
        assert abs(correlation) < 1.0, f"Correlation energy {correlation} too large"

        # Verify both step results exist
        assert (scf_dir / "results.json").exists()
        assert (mp2_dir / "results.json").exists()


class TestPsi4Relax:
    """Integration tests for Psi4 geometry optimization."""

    def test_h2o_relax_hf_sto3g(self, tmp_path):
        """Run H2O geometry optimization at HF/STO-3G."""
        step_dir = tmp_path / "step_artifacts" / "step1"
        step_dir.mkdir(parents=True, exist_ok=True)

        job_chain = {
            "base_working_dir": str(tmp_path),
            "chain_steps": [
                {
                    "step_ulid": "step1",
                    "step_type_spec": "psi4_relax",
                    "parameters": {
                        "method": "hf",
                        "basis": "sto-3g",
                        "atoms": H2O_ATOMS,
                        "charge": 0,
                        "multiplicity": 1,
                        "memory_mb": 500,
                        "nthreads": 1,
                    },
                    "step_artifacts_dir": str(step_dir),
                },
            ],
            "target_step_ulid": "step1",
            "resources": {},
        }

        result = _run_psi4_chain(job_chain, tmp_path)

        assert result["success"], f"Optimization failed: {result.get('error')}"
        assert result["converged"]

        # Verify optimized geometry
        opt_atoms = result.get("optimized_atoms", [])
        assert len(opt_atoms) == 3, f"Expected 3 atoms, got {len(opt_atoms)}"

        # Verify symbols
        symbols = [a["symbol"] for a in opt_atoms]
        assert "O" in symbols
        assert symbols.count("H") == 2

        # Energy should be reasonable for HF/STO-3G
        energy = result["energy"]
        assert -76.0 < energy < -74.0, f"Optimized energy {energy} outside range"


class TestPsi4SubprocessExecution:
    """Test the full subprocess execution path (as the daemon would use it)."""

    def test_subprocess_chain(self, tmp_path):
        """Test chain execution via subprocess."""
        scf_dir = tmp_path / "step_artifacts" / "step1"
        scf_dir.mkdir(parents=True, exist_ok=True)

        job_chain = {
            "base_working_dir": str(tmp_path),
            "chain_steps": [
                {
                    "step_ulid": "step1",
                    "step_type_spec": "psi4_scf",
                    "parameters": {
                        "method": "hf",
                        "basis": "sto-3g",
                        "atoms": H2O_ATOMS,
                        "charge": 0,
                        "multiplicity": 1,
                        "memory_mb": 500,
                        "nthreads": 1,
                    },
                    "step_artifacts_dir": str(scf_dir),
                },
            ],
            "target_step_ulid": "step1",
            "resources": {},
        }

        result = _run_psi4_chain(job_chain, tmp_path)

        assert result["success"], f"Subprocess failed: {result.get('error')}"
        assert -76.0 < result["energy"] < -74.0

        # Verify results.json was written
        assert (scf_dir / "results.json").exists()

    def test_engine_probe(self):
        """Test Psi4Engine.probe() returns available=True."""
        from qmatsuite.engine.psi4_engine import Psi4Engine

        engine = Psi4Engine()
        probe = engine.probe()

        assert probe["available"] is True
        assert probe["version"] is not None
        assert "." in probe["version"]  # Version string like "1.10"
