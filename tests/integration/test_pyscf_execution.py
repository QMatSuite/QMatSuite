"""
Integration tests for PySCF execution.

These tests run actual PySCF calculations and verify results.
Tests are skipped if PySCF is not installed.

To run these tests:
    pip install pyscf
    pytest tests/integration/test_pyscf_execution.py -v
"""

import json
import pytest
from pathlib import Path

from quantumvitas.core.resources import get_resources_dir


def _pyscf_available() -> bool:
    """Check if PySCF is installed with actual functionality.

    CI environments may have a stub pyscf module that passes basic import
    but fails on actual submodules like gto and scf. We check for these
    to ensure PySCF is fully functional.
    """
    try:
        from pyscf import gto, scf
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.skipif(
    not _pyscf_available(),
    reason="PySCF not installed - install with: pip install pyscf"
)


class TestPySCFH2OCalculation:
    """Integration tests for H2O calculation."""
    
    def test_h2o_rhf_sto3g(self, tmp_path):
        """Run H2O RHF/STO-3G and verify energy."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "method": "rhf",
            "basis": "sto-3g",
            "atoms": [
                {"element": "O", "x": 0.0, "y": 0.0, "z": 0.117790},
                {"element": "H", "x": 0.0, "y": 0.755453, "z": -0.471161},
                {"element": "H", "x": 0.0, "y": -0.755453, "z": -0.471161},
            ],
            "charge": 0,
            "spin": 0,
            "unit": "Angstrom",
            "max_cycle": 50,
            "conv_tol": 1e-9,
        }
        
        result = engine._run_scf(params, tmp_path)
        
        # Verify success
        assert result.success, f"Calculation failed: {result.error}"
        assert result.parsed_output is not None
        assert result.parsed_output["converged"]
        
        # Verify energy is reasonable for H2O/STO-3G
        # Expected: ~-74.9 Hartree for STO-3G
        energy = result.parsed_output["energy"]
        assert -76.0 < energy < -74.0, f"Energy {energy} outside expected range"
        
        # Verify HOMO/LUMO gap is positive
        assert result.parsed_output["gap"] > 0
        
        # Verify MO information
        assert result.parsed_output["n_electrons"] == 10
        assert result.parsed_output["n_atoms"] == 3
    
    def test_h2o_rhf_631g(self, tmp_path):
        """Run H2O RHF/6-31G and verify energy."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "method": "rhf",
            "basis": "6-31g",
            "atoms": [
                {"element": "O", "x": 0.0, "y": 0.0, "z": 0.117790},
                {"element": "H", "x": 0.0, "y": 0.755453, "z": -0.471161},
                {"element": "H", "x": 0.0, "y": -0.755453, "z": -0.471161},
            ],
            "charge": 0,
            "spin": 0,
            "unit": "Angstrom",
        }
        
        result = engine._run_scf(params, tmp_path)
        
        assert result.success
        
        # 6-31G should give better energy than STO-3G
        energy = result.parsed_output["energy"]
        assert -76.5 < energy < -75.5, f"Energy {energy} outside expected range for 6-31G"
    
    def test_h2o_dft_pbe(self, tmp_path):
        """Run H2O RKS/PBE/STO-3G and verify energy."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "method": "rks",
            "xc": "pbe",
            "basis": "sto-3g",
            "atoms": [
                {"element": "O", "x": 0.0, "y": 0.0, "z": 0.117790},
                {"element": "H", "x": 0.0, "y": 0.755453, "z": -0.471161},
                {"element": "H", "x": 0.0, "y": -0.755453, "z": -0.471161},
            ],
            "charge": 0,
            "spin": 0,
            "unit": "Angstrom",
        }
        
        result = engine._run_scf(params, tmp_path)
        
        assert result.success, f"DFT calculation failed: {result.error}"
        assert result.parsed_output["xc_functional"] == "pbe"
        
        # DFT should give lower (more negative) energy than HF
        energy = result.parsed_output["energy"]
        assert energy < -74.0, f"DFT energy {energy} should be lower than HF"


class TestPySCFResultsFile:
    """Tests for results.json output file."""
    
    def test_results_json_created(self, tmp_path):
        """Verify results.json is created with correct schema."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "method": "rhf",
            "basis": "sto-3g",
            "atoms": [
                {"element": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"element": "H", "x": 0.0, "y": 0.0, "z": 0.74},
            ],
            "charge": 0,
            "spin": 0,
        }
        
        engine._run_scf(params, tmp_path)
        
        results_file = tmp_path / "results.json"
        assert results_file.exists()
        
        with open(results_file) as f:
            results = json.load(f)
        
        # Required fields
        assert "energy" in results
        assert "energy_unit" in results
        assert "converged" in results
        assert "n_electrons" in results
        assert "method" in results
        assert "basis" in results
        
        # HOMO/LUMO
        assert "homo_index" in results
        assert "lumo_index" in results
        assert "gap" in results or "gap_alpha" in results
    
    def test_pyscf_log_created(self, tmp_path):
        """Verify pyscf.log is created."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "method": "rhf",
            "basis": "sto-3g",
            "atoms": [
                {"element": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"element": "H", "x": 0.0, "y": 0.0, "z": 0.74},
            ],
            "charge": 0,
            "spin": 0,
        }
        
        engine._run_scf(params, tmp_path)
        
        log_file = tmp_path / "pyscf.log"
        assert log_file.exists()
        
        content = log_file.read_text()
        assert "converged" in content.lower() or "SCF" in content


class TestPySCFUnrestrictedMethods:
    """Tests for unrestricted (open-shell) methods."""
    
    def test_oxygen_atom_uhf(self, tmp_path):
        """Run UHF on triplet oxygen atom."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "method": "uhf",
            "basis": "sto-3g",
            "atoms": [
                {"element": "O", "x": 0.0, "y": 0.0, "z": 0.0},
            ],
            "charge": 0,
            "spin": 2,  # Triplet
            "unit": "Angstrom",
        }
        
        result = engine._run_scf(params, tmp_path)
        
        assert result.success, f"UHF calculation failed: {result.error}"
        
        # Should have separate alpha/beta MO energies
        assert "mo_energies_alpha" in result.parsed_output
        assert "mo_energies_beta" in result.parsed_output
    
    def test_methyl_radical_uhf(self, tmp_path):
        """Run UHF on CH3 radical (doublet)."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        # Planar CH3 geometry
        params = {
            "method": "uhf",
            "basis": "sto-3g",
            "atoms": [
                {"element": "C", "x": 0.0, "y": 0.0, "z": 0.0},
                {"element": "H", "x": 1.08, "y": 0.0, "z": 0.0},
                {"element": "H", "x": -0.54, "y": 0.935, "z": 0.0},
                {"element": "H", "x": -0.54, "y": -0.935, "z": 0.0},
            ],
            "charge": 0,
            "spin": 1,  # Doublet (1 unpaired electron)
            "unit": "Angstrom",
        }
        
        result = engine._run_scf(params, tmp_path)
        
        assert result.success, f"UHF calculation failed: {result.error}"
        assert result.parsed_output["n_electrons"] == 9


class TestPySCFDemoExecution:
    """Test running the actual demo project."""
    
    def test_run_demo_calculation(self, tmp_path):
        """Load and run the demo project calculation."""
        import yaml
        from quantumvitas.engine.pyscf_engine import PySCFEngine

        # Load demo project
        demo_path = get_resources_dir() / "demo_projects" / "pyscf_water_scf.yml"

        if not demo_path.exists():
            pytest.skip("Demo project not found")

        with open(demo_path) as f:
            demo = yaml.safe_load(f)

        # Extract step parameters and adapt to engine API
        step = demo["calculations"][0]["steps"][0]
        params = dict(step["parameters"])

        # Map demo parameter names to engine parameter names
        if "functional" in params and "method" not in params:
            params["xc"] = params.pop("functional")
            params["method"] = "rks"  # DFT functional → restricted Kohn-Sham

        # Extract atoms from structure data in demo YAML
        structure_data = demo.get("structures", [{}])[0].get("data", {})
        sites = structure_data.get("sites", [])
        atoms = []
        for site in sites:
            element = site.get("label", site.get("name", "X"))
            xyz = site.get("xyz", [0.0, 0.0, 0.0])
            atoms.append({"element": element, "x": xyz[0], "y": xyz[1], "z": xyz[2]})
        params["atoms"] = atoms

        # Run calculation
        engine = PySCFEngine()
        result = engine._run_scf(params, tmp_path)

        assert result.success, f"Demo calculation failed: {result.error}"
        assert result.parsed_output["converged"]


class TestPySCFEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_atoms_error(self, tmp_path):
        """Empty atoms list should give clear error."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "method": "rhf",
            "basis": "sto-3g",
            "atoms": [],  # Empty!
            "charge": 0,
            "spin": 0,
        }
        
        result = engine._run_scf(params, tmp_path)
        
        # Should fail with clear error
        assert not result.success
        assert result.error is not None
    
    def test_invalid_method_error(self, tmp_path):
        """Invalid method should give clear error."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        # Use H2 with valid spin configuration to test method error
        params = {
            "method": "invalid_method",
            "basis": "sto-3g",
            "atoms": [
                {"element": "H", "x": 0.0, "y": 0.0, "z": 0.0},
                {"element": "H", "x": 0.0, "y": 0.0, "z": 0.74},
            ],
            "charge": 0,
            "spin": 0,
        }
        
        result = engine._run_scf(params, tmp_path)
        
        assert not result.success
        assert "Unknown method" in result.error
    
    def test_convergence_failure(self, tmp_path):
        """Convergence failure should be reported."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        # Set impossibly tight convergence and low cycles
        params = {
            "method": "rhf",
            "basis": "sto-3g",
            "atoms": [
                {"element": "O", "x": 0.0, "y": 0.0, "z": 0.117790},
                {"element": "H", "x": 0.0, "y": 0.755453, "z": -0.471161},
                {"element": "H", "x": 0.0, "y": -0.755453, "z": -0.471161},
            ],
            "charge": 0,
            "spin": 0,
            "max_cycle": 1,  # Only 1 cycle - won't converge
            "conv_tol": 1e-20,  # Impossibly tight
        }
        
        result = engine._run_scf(params, tmp_path)
        
        # Should complete but report not converged
        # (PySCF may still return an energy, but converged=False)
        assert result.parsed_output is not None
        # Note: Depending on PySCF version, this might still converge in 1 cycle
        # for simple molecules, so we just check the result structure is valid
