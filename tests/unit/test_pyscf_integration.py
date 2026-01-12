"""
Unit tests for PySCF integration.

Tests cover:
- Step type registration
- Engine adapter initialization
- Subprocess-based execution
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
        assert spec.id == "scf"  # Public type (Phase 3C: pyscf_scf uses public type "scf")
        assert spec.machine_type == "pyscf_scf"
        assert spec.engine == "pyscf"
        assert spec.executable == "python"
        assert spec.requires_structure is True
        assert spec.accepts_presets is False  # MVP: no presets yet
    
    def test_pyscf_scf_in_known_step_types(self):
        """PYSCF_SCF is in CLI KNOWN_STEP_TYPES."""
        from quantumvitas.cli.main import KNOWN_STEP_TYPES
        
        assert "pyscf_scf" in KNOWN_STEP_TYPES
    
    def test_pyscf_mp2_in_registry(self):
        """PYSCF_MP2 step type is registered in StepTypeRegistry (Phase 3C)."""
        from quantumvitas.workflow.registry import get_registry
        
        registry = get_registry()
        assert registry.has("pyscf_mp2")
    
    def test_pyscf_mp2_spec_properties(self):
        """PYSCF_MP2 StepTypeSpec has correct properties (Phase 3C)."""
        from quantumvitas.workflow.registry import get_registry
        
        spec = get_registry().get("pyscf_mp2")
        
        assert spec is not None
        assert spec.id == "mp2"  # Public type
        assert spec.machine_type == "pyscf_mp2"
        assert spec.engine == "pyscf"
        assert spec.executable == "python"
        assert spec.requires_structure is True
        assert spec.requires_charge_density is True  # MP2 requires SCF charge density
        assert spec.produces_charge_density is False  # MP2 does not produce new charge density
        assert spec.supports_incremental_skip is False  # MP2 is always rerun in v0
    
    def test_pyscf_scf_supports_incremental_skip(self):
        """PYSCF_SCF supports incremental skip (Phase 3C)."""
        from quantumvitas.workflow.registry import get_registry
        
        spec = get_registry().get("pyscf_scf")
        assert spec.supports_incremental_skip is True
    
    def test_pyscf_td_in_registry(self):
        """PYSCF_TD step type is registered in StepTypeRegistry (Phase 3C)."""
        from quantumvitas.workflow.registry import get_registry
        
        registry = get_registry()
        assert registry.has("pyscf_td")
    
    def test_pyscf_td_spec_properties(self):
        """PYSCF_TD StepTypeSpec has correct properties (Phase 3C)."""
        from quantumvitas.workflow.registry import get_registry
        
        spec = get_registry().get("pyscf_td")
        
        assert spec is not None
        assert spec.id == "td"  # Public type (generalized "td" key)
        assert spec.machine_type == "pyscf_td"
        assert spec.public_type == "td"
        assert spec.engine == "pyscf"
        assert spec.executable == "python"
        assert spec.supports_incremental_skip is False  # Always rerun
        assert spec.consumes_state == "mf"  # Phase 3C: Consumes mean-field state
        assert spec.produces_state is None  # Phase 3C: No state production
    
    def test_pyscf_scf_state_fields(self):
        """PYSCF_SCF has correct state dependency fields (Phase 3C)."""
        from quantumvitas.workflow.registry import get_registry
        
        spec = get_registry().get("pyscf_scf")
        assert spec.consumes_state is None  # No dependency
        assert spec.produces_state == "mf"  # Produces mean-field state
    
    def test_pyscf_mp2_state_fields(self):
        """PYSCF_MP2 has correct state dependency fields (Phase 3C)."""
        from quantumvitas.workflow.registry import get_registry
        
        spec = get_registry().get("pyscf_mp2")
        assert spec.consumes_state == "mf"  # Consumes mean-field state
        assert spec.produces_state is None  # No state production
    
    def test_qe_steps_have_none_state_fields(self):
        """QE steps have None defaults for state fields (Phase 3C backward compat)."""
        from quantumvitas.workflow.registry import get_registry
        
        registry = get_registry()
        qe_spec = registry.get("qe_scf")
        assert qe_spec is not None
        assert qe_spec.consumes_state is None  # Default None
        assert qe_spec.produces_state is None  # Default None


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
    
    def test_engine_in_default_registry(self):
        """PySCFEngine is registered in default registry."""
        from quantumvitas.engine.registry import create_default_registry
        
        registry = create_default_registry()
        assert registry.has("pyscf")
        
        engine = registry.get("pyscf")
        assert engine.name == "pyscf"
    
    def test_probe_returns_dict(self):
        """Engine probe() returns a dict with expected keys."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        import sys
        
        engine = PySCFEngine()
        result = engine.probe()
        
        assert isinstance(result, dict)
        assert "available" in result
        assert isinstance(result["available"], bool)
        
        # On non-Windows, should have version or reason
        if sys.platform != "win32":
            if result["available"]:
                assert "version" in result
            else:
                assert "reason" in result
    
    @pytest.mark.skipif(
        not _pyscf_importable(),
        reason="PySCF not installed"
    )
    def test_pyscf_available_when_installed(self):
        """Engine detects PySCF when installed."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        import sys
        
        if sys.platform == "win32":
            pytest.skip("PySCF not supported on Windows")
        
        engine = PySCFEngine()
        probe_result = engine.probe()
        
        assert probe_result["available"] is True
        assert probe_result.get("version") is not None
        assert engine.pyscf_available is True
    
    def test_graceful_failure_without_pyscf(self, tmp_path, monkeypatch):
        """Engine returns error when PySCF not available."""
        from quantumvitas.engine.pyscf_engine import PySCFEngine
        
        engine = PySCFEngine()
        
        # Mock probe to return unavailable
        engine._probe_cache = {
            "available": False,
            "version": None,
            "reason": "PySCF not installed. Install with: pip install pyscf",
        }
        
        # Create mock step
        class MockStep:
            step_type = "pyscf_scf"
            parameters = {"atoms": []}
            options = {}
        
        result = engine.run_step(MockStep(), tmp_path)
        
        assert result.success is False
        assert "pip install pyscf" in result.error


@pytest.mark.skipif(
    not _pyscf_importable(),
    reason="PySCF not installed"
)
class TestPySCFSubprocessRunner:
    """Tests for PySCF subprocess runner module."""
    
    def test_runner_import(self):
        """Runner module can be imported."""
        from quantumvitas.engines.pyscf import runner
        
        assert runner is not None
        assert hasattr(runner, "run_job")
        assert hasattr(runner, "build_mole")
        assert hasattr(runner, "run_scf")
    
    def test_build_water_molecule(self):
        """Build H2O molecule from parameters."""
        from quantumvitas.engines.pyscf.runner import build_mole
        
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
        
        mol = build_mole(params)
        
        assert mol.nelectron == 10
        assert mol.natm == 3
        assert mol.charge == 0
        assert mol.spin == 0
    
    def test_build_molecule_with_coords_format(self):
        """Build molecule using coords list format."""
        from quantumvitas.engines.pyscf.runner import build_mole
        
        params = {
            "atoms": [
                {"element": "H", "coords": [0.0, 0.0, 0.0]},
                {"element": "H", "coords": [0.0, 0.0, 0.74]},
            ],
            "basis": "sto-3g",
            "charge": 0,
            "spin": 0,
        }
        
        mol = build_mole(params)
        
        assert mol.nelectron == 2
        assert mol.natm == 2
    
    def test_build_charged_molecule(self):
        """Build charged molecule."""
        from quantumvitas.engines.pyscf.runner import build_mole
        
        params = {
            "atoms": [
                {"element": "Li", "x": 0.0, "y": 0.0, "z": 0.0},
            ],
            "basis": "sto-3g",
            "charge": 1,  # Li+
            "spin": 0,
        }
        
        mol = build_mole(params)
        
        assert mol.nelectron == 2  # Li has 3 electrons, Li+ has 2
        assert mol.charge == 1
    
    def test_build_open_shell_molecule(self):
        """Build open-shell (radical) molecule."""
        from quantumvitas.engines.pyscf.runner import build_mole
        
        params = {
            "atoms": [
                {"element": "O", "x": 0.0, "y": 0.0, "z": 0.0},
            ],
            "basis": "sto-3g",
            "charge": 0,
            "spin": 2,  # Triplet oxygen
        }
        
        mol = build_mole(params)
        
        assert mol.spin == 2
    
    def test_detect_molecular_system(self):
        """Detect molecular (no cell) system."""
        from quantumvitas.engines.pyscf.runner import detect_system_type
        
        params = {
            "atoms": [{"element": "H", "x": 0, "y": 0, "z": 0}],
        }
        
        assert detect_system_type(params) == "molecular"
    
    def test_detect_periodic_system(self):
        """Detect periodic (with cell) system."""
        from quantumvitas.engines.pyscf.runner import detect_system_type
        
        params = {
            "atoms": [{"element": "H", "x": 0, "y": 0, "z": 0}],
            "cell": [[5, 0, 0], [0, 5, 0], [0, 0, 5]],
        }
        
        assert detect_system_type(params) == "periodic"


@pytest.mark.skipif(
    not _pyscf_importable(),
    reason="PySCF not installed"
)
class TestPySCFSCFExecution:
    """Tests for SCF execution via subprocess (requires PySCF installed)."""
    
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


class TestPySCFPhase3CMaterialization:
    """Tests for Phase 3C: PySCF workflow materialization."""
    
    def test_scf_materializes_to_pyscf_scf(self):
        """PUBLIC key 'scf' materializes to 'pyscf_scf' for PySCF family (Phase 3C)."""
        from quantumvitas.workflow.generalized_steps import materialize_public_step_key
        
        result = materialize_public_step_key("scf", "pyscf")
        assert result == "pyscf_scf"
    
    def test_mp2_materializes_to_pyscf_mp2(self):
        """PUBLIC key 'mp2' materializes to 'pyscf_mp2' for PySCF family (Phase 3C)."""
        from quantumvitas.workflow.generalized_steps import materialize_public_step_key
        
        result = materialize_public_step_key("mp2", "pyscf")
        assert result == "pyscf_mp2"
    
    def test_scf_mp2_workflow_materializes(self):
        """Workflow template 'scf_mp2' materializes correctly for PySCF family (Phase 3C)."""
        from quantumvitas.workflow.generalized_steps import materialize_workflow
        
        result = materialize_workflow(["scf", "mp2"], "pyscf")
        assert result == ["pyscf_scf", "pyscf_mp2"]
    
    def test_scf_mp2_template_exists(self):
        """Workflow template 'scf_mp2' exists (Phase 3C)."""
        from quantumvitas.workflow.templates import get_workflow_service
        
        service = get_workflow_service()
        template = service.get_template("scf_mp2")
        
        assert template is not None
        assert template.id == "scf_mp2"
        assert template.step_sequence == ("scf", "mp2")
    
    def test_mp2_not_supported_by_qe_family(self):
        """PUBLIC key 'mp2' does not materialize for QE family (Phase 3C)."""
        from quantumvitas.workflow.generalized_steps import materialize_public_step_key
        
        result = materialize_public_step_key("mp2", "qe")
        assert result is None
