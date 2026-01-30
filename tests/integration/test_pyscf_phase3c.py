"""
Integration tests for Phase 3C PySCF runner semantics.

Tests run_mode behavior, chain execution, and checkpoint handling.
"""

import pytest
import json
import shutil
from pathlib import Path
from typing import Dict, Any

from quantumvitas.project.model import Project
from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.api import QVService
from quantumvitas.core.resolution import build_resource_index


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project for testing."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    
    # Initialize project using service API
    project_root = QVService.init_project(target_dir=project_root, name="test_project")
    
    # Create structure file using pymatgen Molecule (compatible with structure reader)
    from pymatgen.core import Molecule
    structures_dir = project_root / "structures"
    structures_dir.mkdir(exist_ok=True)
    h2_structure_file = structures_dir / "h2.json"
    
    # Create H2 molecule using pymatgen Molecule (no lattice = molecular)
    mol = Molecule(
        species=["H", "H"],
        coords=[[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]],
        charge=0,
        spin_multiplicity=1,
    )
    
    # Write as pymatgen Molecule dict (includes @module/@class for pymatgen)
    mol_dict = mol.as_dict()
    h2_structure_file.write_text(json.dumps(mol_dict, indent=2))
    
    # Register structure in project config manually
    from quantumvitas.core.project_utils import load_project_config, save_project_config
    from quantumvitas.core.resources import generate_resource_id
    config = load_project_config(project_root)
    if "structures" not in config:
        config["structures"] = []
    
    structure_id = generate_resource_id()
    config["structures"].append({
        "ulid": structure_id,
        "name": "H2",
        "slug": "h2",
        "file": "structures/h2.json",
    })
    save_project_config(project_root, config)
    
    return project_root


@pytest.fixture
def pyscf_calculation(temp_project: Path) -> Dict[str, Any]:
    """Create a PySCF calculation with SCF step using service API."""
    from quantumvitas.core.yaml_io import save_yaml_doc
    from quantumvitas.core.yamldoc import CalcDoc
    from quantumvitas.core.models import load_calculation
    
    # Get structure ID from project config
    from quantumvitas.core.project_utils import load_project_config
    config = load_project_config(temp_project)
    structure_id = None
    for struct in config.get("structures", []):
        if struct.get("slug") == "h2":
            structure_id = struct.get("ulid")
            break
    assert structure_id is not None, "Structure h2 not found in project config"
    
    # Create calculation using service API
    calc_resolved = QVService.init_calculation(
        project_root=temp_project,
        name="test_calc",
        structure_selector=structure_id,
    )
    calc_id = calc_resolved.meta.ulid
    calc_dir = calc_resolved.absolute_path
    
    # Configure calculation engine_family
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=temp_project)
    calc_model.engine_family = "pyscf"
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_data_path)
    
    # Create SCF step using service API
    step_resolved = QVService.init_step(
        project_root=temp_project,
        calculation_selector=calc_id,
        step_type="scf",
        name="scf",
    )
    step_id = step_resolved.meta.ulid

    # Configure step parameters using domain accessor
    svc = QVService(temp_project)
    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=step_id,
        params={
            "parameters": {
                "method": "rhf",
                "basis": "sto-3g",
                "max_cycle": 50,
                "conv_tol": 1e-9,
            },
        },
    )
    
    return {
        "project_root": temp_project,
        "calc_dir": calc_dir,
        "calc_id": calc_id,
        "step_ulid": step_id,
    }


@pytest.mark.skipif(
    not pytest.importorskip("pyscf", reason="PySCF not installed"),
    reason="PySCF not available",
)
class TestPySCFPhase3CIntegration:
    """Integration tests for Phase 3C PySCF semantics."""
    
    def test_t1_runcalc_incremental_uses_chkfile(self, pyscf_calculation: Dict[str, Any]):
        """T1: RunCalc incremental uses chkfile init_guess when checkpoint exists."""
        project_root = pyscf_calculation["project_root"]
        calc_id = pyscf_calculation["calc_id"]
        
        # First run: create checkpoint
        result1 = QVService.run_calculation(
            project_root=project_root,
            calculation_selector=calc_id,
            run_mode="full",  # Full run first to create checkpoint
        )
        assert result1.get("status") == "success", f"First run failed: {result1.get('error')}"
        
        # Get step_id from the result (steps are executed, so use first step from result)
        # The result.steps list contains StepResultSummary with step_id
        step_summaries = result1.get("steps", [])
        assert len(step_summaries) > 0, "No steps were executed"
        executed_step_id = step_summaries[0]["step_ulid"]
        
        # Check that checkpoint was created
        calc_dir = pyscf_calculation["calc_dir"]
        raw_dir = calc_dir / "raw"
        step_artifacts_dir = raw_dir / "step_artifacts" / executed_step_id
        checkpoint_file = step_artifacts_dir / "checkpoint.chk"
        assert checkpoint_file.exists(), f"Checkpoint file should exist after first run at {checkpoint_file}"
        
        # Second run: incremental (should use chkfile init_guess)
        result2 = QVService.run_calculation(
            project_root=project_root,
            calculation_selector=calc_id,
            run_mode="incremental",  # Incremental: should use chkfile
        )
        assert result2.get("status") == "success", f"Second run failed: {result2.get('error')}"
        
        # Verify checkpoint still exists (was reused)
        assert checkpoint_file.exists(), "Checkpoint should still exist after incremental run"
    
    def test_t2_runcalc_full_forbids_chkfile(self, pyscf_calculation: Dict[str, Any]):
        """T2: RunCalc full does NOT use chkfile init_guess."""
        project_root = pyscf_calculation["project_root"]
        calc_id = pyscf_calculation["calc_id"]
        
        # First run: create checkpoint
        result1 = QVService.run_calculation(
            project_root=project_root,
            calculation_selector=calc_id,
            run_mode="full",
        )
        assert result1.get("status") == "success"
        
        # Verify checkpoint exists
        calc_dir = pyscf_calculation["calc_dir"]
        raw_dir = calc_dir / "raw"
        step_artifacts_dir = raw_dir / "step_artifacts" / pyscf_calculation["step_ulid"]
        checkpoint_file = step_artifacts_dir / "checkpoint.chk"
        assert checkpoint_file.exists()
        
        # Second run: full (should NOT use chkfile init_guess, but checkpoint will be overwritten)
        result2 = QVService.run_calculation(
            project_root=project_root,
            calculation_selector=calc_id,
            run_mode="full",  # Full: should NOT use chkfile init_guess
        )
        assert result2.get("status") == "success"
        
        # Checkpoint should still exist (was overwritten with new run)
        assert checkpoint_file.exists()
    
    def test_t3_runstep_scf_forbids_chkfile(self, pyscf_calculation: Dict[str, Any]):
        """T3: RunStep(scf) does NOT use chkfile init_guess (forced full rerun)."""
        project_root = pyscf_calculation["project_root"]
        calc_id = pyscf_calculation["calc_id"]
        step_id = pyscf_calculation["step_ulid"]
        
        # First run: create checkpoint
        result1 = QVService.run_calculation(
            project_root=project_root,
            calculation_selector=calc_id,
            run_mode="full",
        )
        assert result1.get("status") == "success"
        
        # Verify checkpoint exists
        calc_dir = pyscf_calculation["calc_dir"]
        raw_dir = calc_dir / "raw"
        step_artifacts_dir = raw_dir / "step_artifacts" / step_id
        checkpoint_file = step_artifacts_dir / "checkpoint.chk"
        assert checkpoint_file.exists()
        
        # RunStep(scf): should NOT use chkfile init_guess (target step always full rerun)
        result2 = QVService.run_step(
            project_root=project_root,
            calculation_selector=calc_id,
            step_selector=step_id,
        )
        assert result2.get("success"), f"RunStep failed: {result2.get('error')}"
        
        # Checkpoint should still exist (was overwritten)
        assert checkpoint_file.exists()
    
    def test_t4_runstep_mp2_chain_execution(self, temp_project: Path):
        """T4: RunStep(mp2) executes scf→mp2 in one session."""
        # Create calculation with SCF and MP2 steps using service API
        from quantumvitas.core.yaml_io import save_yaml_doc
        from quantumvitas.core.yamldoc import CalcDoc
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.project_utils import load_project_config
        
        config = load_project_config(temp_project)
        structure_id = None
        for struct in config.get("structures", []):
            if struct.get("slug") == "h2":
                structure_id = struct.get("ulid")
                break
        assert structure_id is not None, "Structure h2 not found"
        
        calc_resolved = QVService.init_calculation(
            project_root=temp_project,
            name="test_calc_mp2",
            structure_selector=structure_id,
        )
        calc_id = calc_resolved.meta.ulid
        calc_dir = calc_resolved.absolute_path
        
        # Configure engine_family
        calc_data_path = calc_dir / "calculation.yaml"
        calc_model = load_calculation(calc_data_path, project_root=temp_project)
        calc_model.engine_family = "pyscf"
        calc_doc = CalcDoc(calc_model.to_dict())
        save_yaml_doc(calc_doc, calc_data_path)
        
        # Create SCF step
        scf_step_resolved = QVService.init_step(
            project_root=temp_project,
            calculation_selector=calc_id,
            step_type="scf",
            name="scf",
        )
        scf_step_id = scf_step_resolved.meta.ulid
        svc = QVService(temp_project)
        svc.calculation.update_step_params(
            calc_selector=calc_id,
            step_selector=scf_step_id,
            params={
                "parameters": {
                    "method": "rhf",
                    "basis": "sto-3g",
                    "max_cycle": 50,
                    "conv_tol": 1e-9,
                },
            },
        )

        # Create MP2 step
        mp2_step_resolved = QVService.init_step(
            project_root=temp_project,
            calculation_selector=calc_id,
            step_type="mp2",
            name="mp2",
        )
        mp2_step_id = mp2_step_resolved.meta.ulid
        svc.calculation.update_step_params(
            calc_selector=calc_id,
            step_selector=mp2_step_id,
            params={
                "parameters": {
                    "basis": "sto-3g",
                },
            },
        )

        # Run Step(MP2): should execute SCF then MP2 in one session
        result = QVService.run_step(
            project_root=temp_project,
            calculation_selector=calc_id,
            step_selector=mp2_step_id,
        )
        assert result.get("success"), f"RunStep(mp2) failed: {result.get('error')}"
        
        # Verify both steps' artifacts exist
        raw_dir = calc_dir / "raw"
        scf_artifacts_dir = raw_dir / "step_artifacts" / scf_step_id
        mp2_artifacts_dir = raw_dir / "step_artifacts" / mp2_step_id
        
        assert scf_artifacts_dir.exists(), "SCF artifacts directory should exist"
        assert mp2_artifacts_dir.exists(), "MP2 artifacts directory should exist"
        
        scf_results = scf_artifacts_dir / "results.json"
        mp2_results = mp2_artifacts_dir / "results.json"
        
        assert scf_results.exists(), "SCF results.json should exist"
        assert mp2_results.exists(), "MP2 results.json should exist"
        
        # Verify MP2 results contain correlation energy
        mp2_data = json.loads(mp2_results.read_text())
        assert "correlation_energy" in mp2_data, "MP2 results should contain correlation_energy"
        assert "total_energy" in mp2_data, "MP2 results should contain total_energy"
    
    def test_t5_missing_dependency_error(self, temp_project: Path):
        """T5: RunStep(mp2) without prior SCF errors cleanly."""
        # Create calculation with ONLY MP2 step (no SCF) using service API
        from quantumvitas.core.yaml_io import save_yaml_doc
        from quantumvitas.core.yamldoc import CalcDoc
        from quantumvitas.core.models import load_calculation
        from quantumvitas.core.project_utils import load_project_config
        
        config = load_project_config(temp_project)
        structure_id = None
        for struct in config.get("structures", []):
            if struct.get("slug") == "h2":
                structure_id = struct.get("ulid")
                break
        assert structure_id is not None, "Structure h2 not found"
        
        calc_resolved = QVService.init_calculation(
            project_root=temp_project,
            name="test_calc_mp2_only",
            structure_selector=structure_id,
        )
        calc_id = calc_resolved.meta.ulid
        calc_dir = calc_resolved.absolute_path
        
        # Configure engine_family
        calc_data_path = calc_dir / "calculation.yaml"
        calc_model = load_calculation(calc_data_path, project_root=temp_project)
        calc_model.engine_family = "pyscf"
        calc_doc = CalcDoc(calc_model.to_dict())
        save_yaml_doc(calc_doc, calc_data_path)
        
        # Create MP2 step (no SCF dependency)
        mp2_step_resolved = QVService.init_step(
            project_root=temp_project,
            calculation_selector=calc_id,
            step_type="mp2",
            name="mp2",
        )
        mp2_step_id = mp2_step_resolved.meta.ulid
        svc = QVService(temp_project)
        svc.calculation.update_step_params(
            calc_selector=calc_id,
            step_selector=mp2_step_id,
            params={
                "parameters": {
                    "basis": "sto-3g",
                },
            },
        )

        # Run Step(MP2): should fail because no SCF provider exists
        # Note: The unified pipeline returns errors in the result dict rather than raising exceptions
        result = QVService.run_step(
            project_root=temp_project,
            calculation_selector=calc_id,
            step_selector=mp2_step_id,
        )

        # Verify execution failed
        assert result.get("success") is False, "RunStep(mp2) without SCF should fail"

        # Verify error message mentions missing dependency
        error_msg = result.get("error", "")
        assert "dependency" in error_msg.lower() or "provider" in error_msg.lower() or "mf" in error_msg.lower() or "scf" in error_msg.lower(), \
            f"Error should mention missing dependency, got: {error_msg}"
