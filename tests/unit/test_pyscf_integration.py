"""
Unit tests for PySCF integration.

Tests cover:
- Step type registration
- Engine adapter initialization
- Molecule building
- Parameter validation
"""

import pytest
from pathlib import Path


def _pyscf_importable() -> bool:
    """Check if PySCF can be imported."""
    try:
        import pyscf
        return True
    except ImportError:
        return False


class TestPySCFStepTypeRegistration:
    """Tests for PySCF step type registration in registry."""
    
    def test_pyscf_scf_in_step_type_enum(self):
        """PYSCF_SCF exists in StepType enum."""
        from quantumvitas.calculation.types import StepType
        
        assert hasattr(StepType, "PYSCF_SCF")
        assert StepType.PYSCF_SCF.value == "pyscf_scf"
    
    def test_pyscf_scf_in_registry(self):
        """PYSCF_SCF step type is registered in StepTypeRegistry."""
        from quantumvitas.workflow.registry import get_registry
        
        registry = get_registry()
        assert registry.has("pyscf_scf")
    
    def test_pyscf_scf_spec_properties(self):
        """PYSCF_SCF StepTypeSpec has correct properties."""
        from quantumvitas.workflow.registry import get_registry
        
        spec = get_registry().get("pyscf_scf")
        
        assert spec is not None
        assert spec.id == "pyscf_scf"
        assert spec.engine == "pyscf"
        assert spec.executable == "python"
        assert spec.requires_structure is True
        assert spec.accepts_presets is False  # MVP: no presets yet
    
    def test_pyscf_scf_in_known_step_types(self):
        """PYSCF_SCF is in CLI KNOWN_STEP_TYPES."""
        from quantumvitas.cli.main import KNOWN_STEP_TYPES
        
        assert "pyscf_scf" in KNOWN_STEP_TYPES


class TestPySCFEngineAvailability:
    """Tests for PySCF engine availability detection."""
    
    def test_engine_import(self):
        """PySCFEngine can be imported."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        assert PySCFEngine is not None
    
    def test_engine_instantiation(self):
        """PySCFEngine can be instantiated."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        assert engine.name == "pyscf"
    
    def test_pyscf_availability_check(self):
        """Engine correctly detects PySCF availability."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine, _check_pyscf_available
        
        # Check function returns bool
        result = _check_pyscf_available()
        assert isinstance(result, bool)
        
        # Engine property matches
        engine = PySCFEngine()
        assert engine.pyscf_available == result
    
    def test_graceful_failure_without_pyscf(self, tmp_path, monkeypatch):
        """Engine returns error when PySCF not installed."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        # Mock PySCF as unavailable
        monkeypatch.setattr(
            "quantumvitas.engine.pyscf_engine._check_pyscf_available",
            lambda: False
        )
        
        engine = PySCFEngine()
        engine._pyscf_available = False
        
        # Create mock step
        class MockStep:
            parameters = {"atoms": []}
        
        result = engine.run_step(MockStep(), tmp_path)
        
        assert result.success is False
        assert "pip install pyscf" in result.error


@pytest.mark.skipif(
    not _pyscf_importable(),
    reason="PySCF not installed"
)
class TestPySCFMoleculeBuilding:
    """Tests for molecule building from parameters."""
    
    def test_build_water_molecule(self):
        """Build H2O molecule from parameters."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "atoms": [
                {"element": "O", "x": 0.0, "y": 0.0, "z": 0.117790},
                {"element": "H", "x": 0.0, "y": 0.755453, "z": -0.471161},
                {"element": "H", "x": 0.0, "y": -0.755453, "z": -0.471161},
            ],
            "basis": "sto-3g",
            "charge": 0,
            "spin": 0,
            "unit": "Angstrom",
        }
        
        mol = engine._build_mole(params)
        
        assert mol.nelectron == 10
        assert mol.natm == 3
        assert mol.charge == 0
        assert mol.spin == 0
    
    def test_build_molecule_with_coords_format(self):
        """Build molecule using coords list format."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "atoms": [
                {"element": "H", "coords": [0.0, 0.0, 0.0]},
                {"element": "H", "coords": [0.0, 0.0, 0.74]},
            ],
            "basis": "sto-3g",
            "charge": 0,
            "spin": 0,
        }
        
        mol = engine._build_mole(params)
        
        assert mol.nelectron == 2
        assert mol.natm == 2
    
    def test_build_charged_molecule(self):
        """Build charged molecule."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "atoms": [
                {"element": "Li", "x": 0.0, "y": 0.0, "z": 0.0},
            ],
            "basis": "sto-3g",
            "charge": 1,  # Li+
            "spin": 0,
        }
        
        mol = engine._build_mole(params)
        
        assert mol.nelectron == 2  # Li has 3 electrons, Li+ has 2
        assert mol.charge == 1
    
    def test_build_open_shell_molecule(self):
        """Build open-shell (radical) molecule."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        params = {
            "atoms": [
                {"element": "O", "x": 0.0, "y": 0.0, "z": 0.0},
            ],
            "basis": "sto-3g",
            "charge": 0,
            "spin": 2,  # Triplet oxygen
        }
        
        mol = engine._build_mole(params)
        
        assert mol.spin == 2


@pytest.mark.skipif(
    not _pyscf_importable(),
    reason="PySCF not installed"
)
class TestPySCFSCFExecution:
    """Tests for SCF execution (requires PySCF installed)."""
    
    def test_rhf_h2(self, tmp_path):
        """Run RHF on H2 molecule."""
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
            "unit": "Angstrom",
        }
        
        result = engine._run_scf(params, tmp_path)
        
        assert result.success
        assert result.parsed_output is not None
        assert result.parsed_output["converged"]
        # H2/STO-3G energy should be around -1.1 Hartree
        assert -1.2 < result.parsed_output["energy"] < -1.0
        
        # Check results.json was written
        results_file = tmp_path / "results.json"
        assert results_file.exists()
    
    def test_rks_h2o(self, tmp_path):
        """Run RKS DFT on H2O molecule."""
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
        }
        
        result = engine._run_scf(params, tmp_path)
        
        assert result.success
        assert result.parsed_output["converged"]
        # H2O energy should be negative
        assert result.parsed_output["energy"] < 0
        assert result.parsed_output["method"] == "rks"
        assert result.parsed_output["xc_functional"] == "pbe"
    
    def test_input_script_generation(self, tmp_path):
        """Input script is generated for reproducibility."""
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
        
        script_file = tmp_path / "pyscf_input.py"
        assert script_file.exists()
        
        content = script_file.read_text()
        assert "from pyscf import gto, scf, dft" in content
        assert "mol.basis" in content
        assert "mf.kernel()" in content


class TestPySCFDemoProject:
    """Tests for PySCF demo project."""
    
    def test_demo_project_exists(self):
        """Demo project YAML exists."""
        from pathlib import Path
        
        repo_root = Path(__file__).parent.parent.parent
        demo_path = repo_root / "resources" / "demo_projects" / "water_pyscf_scf.yml"
        
        assert demo_path.exists(), f"Demo not found at {demo_path}"
    
    def test_demo_project_structure(self):
        """Demo project has correct structure."""
        import yaml
        from pathlib import Path
        
        repo_root = Path(__file__).parent.parent.parent
        demo_path = repo_root / "resources" / "demo_projects" / "water_pyscf_scf.yml"
        
        with open(demo_path) as f:
            demo = yaml.safe_load(f)
        
        # Check top-level structure
        assert "project" in demo
        assert "structures" in demo
        assert "calculations" in demo
        assert "meta" in demo
        
        # Check structure is molecular (no lattice)
        structure = demo["structures"][0]
        assert "data" in structure
        data = structure["data"]
        assert "lattice" not in data, "Molecular structure should not have lattice"
        assert "atoms" in data
        
        # Check calculation has pyscf_scf step
        calc = demo["calculations"][0]
        assert len(calc["steps"]) >= 1
        step = calc["steps"][0]
        assert step["step_type"] == "pyscf_scf"
        
        # Check step parameters
        params = step["parameters"]
        assert params["method"] == "rhf"
        assert "basis" in params
        assert "atoms" in params

