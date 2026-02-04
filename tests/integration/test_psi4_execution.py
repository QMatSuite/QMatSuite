"""
Integration tests for Psi4 execution.

These tests run actual Psi4 calculations and verify results.
Tests are skipped if Psi4 is not installed.

To run these tests:
    conda install psi4 -c conda-forge
    pytest tests/integration/test_psi4_execution.py -v
"""

import json
import pytest
from pathlib import Path


def _psi4_available() -> bool:
    """Check if Psi4 is installed and importable.

    We check for psi4.core because the project's drivers/psi4 package
    can shadow the real psi4 module during test collection.
    """
    try:
        import psi4
        return hasattr(psi4, "core")
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _psi4_available(),
    reason="Psi4 not installed - install with: conda install psi4 -c conda-forge"
)


# Water molecule coordinates (Angstrom)
H2O_ATOMS = [
    {"symbol": "O", "x": 0.0, "y": 0.0, "z": 0.117790},
    {"symbol": "H", "x": 0.0, "y": 0.755453, "z": -0.471161},
    {"symbol": "H", "x": 0.0, "y": -0.755453, "z": -0.471161},
]


class TestPsi4SCF:
    """Integration tests for Psi4 SCF calculations."""

    def test_h2o_rhf_sto3g(self, tmp_path):
        """Run H2O RHF/STO-3G and verify energy."""
        from quantumvitas.engines.psi4.runner import run_scf, build_molecule

        params = {
            "method": "hf",
            "basis": "sto-3g",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = run_scf(params, tmp_path)

        assert result["success"], f"Calculation failed: {result.get('error')}"
        assert result["converged"]

        # H2O RHF/STO-3G reference: ~-74.96 Hartree
        energy = result["energy"]
        assert -76.0 < energy < -74.0, f"Energy {energy} outside expected range"
        assert result["n_atoms"] == 3

    def test_h2o_hf_ccpvdz(self, tmp_path):
        """Run H2O HF/cc-pVDZ and verify energy."""
        from quantumvitas.engines.psi4.runner import run_scf

        params = {
            "method": "hf",
            "basis": "cc-pvdz",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = run_scf(params, tmp_path)

        assert result["success"], f"Calculation failed: {result.get('error')}"

        # H2O HF/cc-pVDZ reference: ~-76.03 Hartree
        energy = result["energy"]
        assert -76.5 < energy < -75.5, f"Energy {energy} outside expected range for cc-pVDZ"

    def test_h2o_b3lyp_sto3g(self, tmp_path):
        """Run H2O B3LYP/STO-3G DFT and verify energy."""
        from quantumvitas.engines.psi4.runner import run_scf

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

        result = run_scf(params, tmp_path)

        assert result["success"], f"Calculation failed: {result.get('error')}"

        # B3LYP/STO-3G should give different energy from HF/STO-3G
        energy = result["energy"]
        assert -76.5 < energy < -74.5, f"Energy {energy} outside expected range for B3LYP"

    def test_output_files_created(self, tmp_path):
        """Verify output files are created."""
        from quantumvitas.engines.psi4.runner import run_scf

        params = {
            "method": "hf",
            "basis": "sto-3g",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = run_scf(params, tmp_path)
        assert result["success"]

        # Check output.dat created
        assert (tmp_path / "output.dat").exists()

        # Check wavefunction saved
        assert (tmp_path / "wavefunction.npy").exists()

    def test_psi4_variables_collected(self, tmp_path):
        """Verify Psi4 variables dict is populated."""
        from quantumvitas.engines.psi4.runner import run_scf

        params = {
            "method": "hf",
            "basis": "sto-3g",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = run_scf(params, tmp_path)
        assert result["success"]

        psi4_vars = result.get("psi4_variables", {})
        assert "SCF TOTAL ENERGY" in psi4_vars
        assert "NUCLEAR REPULSION ENERGY" in psi4_vars


class TestPsi4MP2Chain:
    """Integration tests for SCF → MP2 chain."""

    def test_scf_mp2_chain(self, tmp_path):
        """Run SCF → MP2 chain and verify energies."""
        from quantumvitas.engines.psi4.chain_execution import run_chain_session

        scf_dir = tmp_path / "step_artifacts" / "scf_step"
        mp2_dir = tmp_path / "step_artifacts" / "mp2_step"

        chain_steps = [
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
        ]

        result = run_chain_session(
            chain_steps=chain_steps,
            base_working_dir=tmp_path,
            target_step_ulid="mp2_step",
        )

        assert result.get("success"), f"Chain failed: {result.get('error')}"

        # MP2 total energy should be lower than SCF (correlation is negative)
        total_energy = result["energy"]
        scf_energy = result.get("scf_energy")
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
        from quantumvitas.engines.psi4.runner import run_relax

        params = {
            "method": "hf",
            "basis": "sto-3g",
            "atoms": H2O_ATOMS,
            "charge": 0,
            "multiplicity": 1,
            "memory_mb": 500,
            "nthreads": 1,
        }

        result = run_relax(params, tmp_path)

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
        """Test chain execution via subprocess (run_job_chain)."""
        from quantumvitas.engines.psi4.runner import run_job_chain

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

        # Write job_chain.json
        job_chain_file = tmp_path / "job_chain.json"
        job_chain_file.write_text(json.dumps(job_chain, indent=2))

        # Run
        exit_code = run_job_chain(job_chain_file)

        assert exit_code == 0, f"Exit code {exit_code}, check results.json"

        # Verify results.json
        results_file = scf_dir / "results.json"
        assert results_file.exists()
        results = json.loads(results_file.read_text())
        assert results["success"]
        assert -76.0 < results["energy"] < -74.0

    def test_engine_probe(self):
        """Test Psi4Engine.probe() returns available=True."""
        from quantumvitas.engine.psi4_engine import Psi4Engine

        engine = Psi4Engine()
        probe = engine.probe()

        assert probe["available"] is True
        assert probe["version"] is not None
        assert "." in probe["version"]  # Version string like "1.10"
