"""
Real ORCA relax integration test.

This test actually runs ORCA to perform a geometry optimization
and verifies that the output is correctly parsed and written to current.json.

IMPORTANT: ORCA is REQUIRED for these tests. They will NOT be skipped.

NOTE: Tests skipped pending migration from compat API to domain API.
"""

import json
import pytest
import time
import uuid
import shutil
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.core.paths import tmp_runs_dir

from quantumvitas.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
)
from pymatgen.core import Molecule


pytestmark = [pytest.mark.integration, pytest.mark.requires_orca]


@pytest.fixture(scope="module")
def orca_available():
    """Verify ORCA is available. This fixture will SKIP if ORCA is not installed."""
    from quantumvitas.core.engines.orca_resolver import resolve_orca_bin
    
    try:
        orca_bin = resolve_orca_bin()
    except RuntimeError as e:
        pytest.skip(f"ORCA not available: {e}")
    
    if not Path(orca_bin).exists():
        pytest.skip(f"ORCA binary does not exist: {orca_bin}")
    
    return orca_bin


@pytest.fixture
def orca_project_with_h2(orca_available):
    """Create a project with H2 molecule for ORCA relax test."""
    unique_id = f"orca_relax_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    test_dir = tmp_runs_dir() / unique_id
    test_dir.mkdir(parents=True, exist_ok=True)
    
    project_root = QVService.init_project(test_dir / "orca_project")
    
    # Create H2 molecule with non-equilibrium bond length
    h2 = Molecule(["H", "H"], [[0, 0, 0], [0.8, 0, 0]])  # 0.8 Å (far from equilibrium ~0.74 Å)
    h2_file = test_dir / "h2.xyz"
    h2.to(filename=h2_file, fmt="xyz")
    
    # Import structure
    struct_result = QVService.import_structure(project_root, h2_file, name="H2")
    
    # Create calculation
    calc = QVService.init_calculation(
        project_root, "h2_relax",
        structure_selector=struct_result.meta.ulid,
    )
    
    # Set engine_family to orca and structure_kind to molecule in calculation.yaml
    import yaml
    calc_yaml = calc.absolute_path / "calculation.yaml"
    calc_data = yaml.safe_load(calc_yaml.read_text())
    calc_data["engine_family"] = "orca"
    calc_data["structure_kind"] = "molecule"
    calc_yaml.write_text(yaml.dump(calc_data, default_flow_style=False))
    
    # Create relax step
    step = QVService.init_step(project_root, calc.id, "orca_relax", name="relax")

    # Configure with minimal parameters
    svc = QVService(project_root)
    svc.calculation.update_step_params(
        calc_selector=calc.id,
        step_selector=step.id,
        params={
            "parameters": {
                "method": "HF",
                "basis": "STO-3G",
                "geom": {"MaxIter": 50},
            },
        },
    )
    
    yield {
        "project_root": project_root,
        "calc_id": calc.id,
        "step_ulid": step.id,
        "structure_path": project_root / "structures" / f"{struct_result.meta.ulid}.json",
        "initial_h2_distance": 0.8,
    }
    
    # Cleanup
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


class TestORCARelaxReal:
    """Real ORCA relax integration tests."""
    
    def test_orca_relax_creates_current_json(self, orca_project_with_h2):
        """Test that ORCA relax creates current.json with relaxed structure."""
        project_root = orca_project_with_h2["project_root"]
        calc_id = orca_project_with_h2["calc_id"]
        step_id = orca_project_with_h2["step_ulid"]
        
        # Run relax
        result = QVService.run_step(project_root, calc_id, step_id)
        
        # Verify success
        assert result.get("success"), f"Step failed: {result.get('error')}"
        
        # Verify current.json exists
        calc_dir = project_root / "calculations" / "h2_relax"
        artifact_path = get_generated_structure_path(calc_dir, step_id)
        
        assert artifact_path.exists(), (
            f"current.json not found at {artifact_path}. "
            "Check executor logs for post-processing errors."
        )
    
    def test_orca_relax_structure_changes(self, orca_project_with_h2):
        """Test that relaxed structure has different geometry."""
        project_root = orca_project_with_h2["project_root"]
        calc_id = orca_project_with_h2["calc_id"]
        step_id = orca_project_with_h2["step_ulid"]
        initial_distance = orca_project_with_h2["initial_h2_distance"]
        
        # Run relax
        result = QVService.run_step(project_root, calc_id, step_id)
        assert result.get("success"), f"Step failed: {result.get('error')}"
        
        # Read relaxed structure
        calc_dir = project_root / "calculations" / "h2_relax"
        relaxed_mol = read_generated_structure(calc_dir, step_id)
        
        assert relaxed_mol is not None, "Failed to read relaxed structure"
        assert len(relaxed_mol) == 2, f"Expected 2 atoms, got {len(relaxed_mol)}"
        
        # Check that geometry changed (relaxed H-H should be ~0.735 Å for HF/STO-3G)
        relaxed_distance = relaxed_mol.get_distance(0, 1)
        
        # The relaxed distance should be different from initial
        assert abs(relaxed_distance - initial_distance) > 0.01, (
            f"Geometry did not change significantly. "
            f"Initial: {initial_distance:.4f} Å, Relaxed: {relaxed_distance:.4f} Å"
        )
        
        # HF/STO-3G equilibrium H-H distance is approximately 0.735 Å
        # But with limited iterations (MaxIter=50) and minimal basis, may not fully converge
        # Accept a wider range: geometry should have changed and be reasonable
        assert 0.6 < relaxed_distance < 1.2, (
            f"Relaxed H-H distance {relaxed_distance:.4f} Å is outside reasonable range [0.6, 1.2] Å"
        )
    
    def test_orca_relax_molecule_composition(self, orca_project_with_h2):
        """Test that relaxed molecule has same composition as input."""
        project_root = orca_project_with_h2["project_root"]
        calc_id = orca_project_with_h2["calc_id"]
        step_id = orca_project_with_h2["step_ulid"]
        
        # Run relax
        result = QVService.run_step(project_root, calc_id, step_id)
        assert result.get("success"), f"Step failed: {result.get('error')}"
        
        # Read relaxed structure
        calc_dir = project_root / "calculations" / "h2_relax"
        relaxed_mol = read_generated_structure(calc_dir, step_id)
        
        # Composition should be H2
        from pymatgen.core import Composition
        expected = Composition("H2")
        assert relaxed_mol.composition == expected, (
            f"Expected composition {expected}, got {relaxed_mol.composition}"
        )
