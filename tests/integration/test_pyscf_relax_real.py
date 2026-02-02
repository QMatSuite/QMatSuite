"""
Real PySCF relax integration test.

This test actually runs PySCF to perform a geometry optimization
and verifies that the output is correctly parsed and written to current.json.
"""

import json
import pytest
import time
import uuid
from pathlib import Path

from quantumvitas.api import QVService
# Removed compat import - use domain API
from quantumvitas.core.paths import tmp_runs_dir
from quantumvitas.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
)
from pymatgen.core import Molecule


pytestmark = [pytest.mark.integration]


def is_pyscf_available() -> bool:
    """Check if PySCF and an optimizer (geometric or berny) can be imported."""
    try:
        import pyscf
        # Also check for optimizer availability
        try:
            from pyscf.geomopt.geometric_solver import optimize
            return True
        except ImportError:
            pass
        try:
            from pyscf.geomopt.berny_solver import optimize
            return True
        except ImportError:
            pass
        # PySCF available but no optimizer
        return False
    except ImportError:
        return False


@pytest.fixture(scope="module", autouse=True)
def skip_if_pyscf_unavailable():
    """Skip all tests in this module if PySCF or optimizer is not available."""
    if not is_pyscf_available():
        pytest.skip("PySCF or optimizer not available. Install with: pip install pyscf geometric (or pyberny)")


@pytest.fixture
def pyscf_project_with_h2():
    """Create a project with H2 molecule for PySCF relax test."""
    # Use .tmp/runs/ directory with unique name
    unique_id = f"pyscf_relax_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    test_dir = tmp_runs_dir() / unique_id
    test_dir.mkdir(parents=True, exist_ok=True)
    
    project_root = QVService.init_project(test_dir / "pyscf_relax_project")
    
    # Create H2 molecule (simple case for quick test)
    h2_molecule = Molecule(["H", "H"], [[0, 0, 0], [0.8, 0, 0]])
    
    # Save molecule to file manually
    structures_dir = project_root / "structures"
    structures_dir.mkdir(parents=True, exist_ok=True)
    
    from quantumvitas.core.resources import generate_resource_id
    structure_ulid = generate_resource_id()
    structure_data = {
        "__qv_meta__": {
            "ulid": structure_ulid,
            "name": "H2",
            "slug": "h2",
            "path": "structures/h2.json",
            "kind": "structure",
        },
        "structure": h2_molecule.as_dict(),
    }
    (structures_dir / "h2.json").write_text(json.dumps(structure_data))
    
    return {
        "project_root": project_root,
        "structure_ulid": structure_ulid,
        "structure_path": structures_dir / "h2.json",
        "test_dir": test_dir,
    }


@pytest.fixture
def pyscf_calculation_with_relax(pyscf_project_with_h2):
    """Create a calculation with a relax step, configured for PySCF."""
    project_root = pyscf_project_with_h2["project_root"]
    structure_ulid = pyscf_project_with_h2["structure_ulid"]
    
    # Create calculation with molecule/pyscf settings
    calc_result = QVService(project_root).project.init_calculation(
        name="h2_relax",
        structure_selector=structure_ulid,
    )
    calc_ulid = calc_result.ulid
    if calc_result.absolute_path.is_dir():
        calc_dir = calc_result.absolute_path
    else:
        calc_dir = calc_result.absolute_path.parent
    
    # Set engine_family to pyscf in calculation.yaml
    import yaml
    calc_yaml = calc_dir / "calculation.yaml"
    calc_data = yaml.safe_load(calc_yaml.read_text())
    calc_data["engine_family"] = "pyscf"
    calc_data["structure_kind"] = "molecule"
    calc_yaml.write_text(yaml.dump(calc_data))
    
    # Create relax step
    relax_step_dto = QVService(project_root).calculation.add_step(
        calc_ulid,
        step_type_gen="relax",  # GEN type for UI layer
        name="relax",
    )
    relax_step_ulid = relax_step_dto.ulid

    # Configure relax step with minimal parameters for quick test
    svc = QVService(project_root)
    svc.calculation.update_step_params(
        calc_selector=calc_ulid,
        step_selector=relax_step_ulid,
        params={
            "parameters": {
                "method": "rhf",
                "basis": "sto-3g",  # Minimal basis for speed
                "maxsteps": 50,
            },
        },
    )
    
    return {
        "project_root": project_root,
        "calc_ulid": calc_ulid,
        "calc_dir": calc_dir,
        "relax_step_ulid": relax_step_ulid,
        "structure_ulid": structure_ulid,
    }


class TestPySCFRelaxReal:
    """Real PySCF relax integration tests."""
    
    def test_pyscf_relax_execution_creates_current_json(
        self,
        pyscf_calculation_with_relax,
    ):
        """
        Test that running a PySCF relax step actually executes PySCF,
        and the output is parsed and written to current.json.
        """
        
        calc_ulid = pyscf_calculation_with_relax["calc_ulid"]
        relax_step_ulid = pyscf_calculation_with_relax["relax_step_ulid"]
        calc_dir = pyscf_calculation_with_relax["calc_dir"]
        project_root = pyscf_calculation_with_relax["project_root"]
        
        # Run the relax step
        svc = QVService(project_root)
        result = svc.run.run_step(
            calc_selector=calc_ulid,
            step_selector=relax_step_ulid,
        )

        # Verify step completed
        assert result.status == "completed", f"Step failed: {result.error.message if result.error else None}"

        # Verify current.json was created
        artifact_path = get_generated_structure_path(calc_dir, relax_step_ulid)
        assert artifact_path.exists(), (
            f"current.json not found at {artifact_path}. "
            "Check executor logs for post-processing errors."
        )
        
        # Verify structure can be read
        relaxed_structure = read_generated_structure(calc_dir, relax_step_ulid)
        assert relaxed_structure is not None, "Failed to read generated structure"
        assert len(relaxed_structure) == 2, "Expected 2 H atoms"
        
        # Verify H-H bond distance is reasonable (around 0.74 Angstrom for RHF/STO-3G)
        bond_distance = relaxed_structure.get_distance(0, 1)
        assert 0.6 < bond_distance < 1.0, f"H-H bond distance {bond_distance} seems wrong"
        
        # Verify metadata
        data = json.loads(artifact_path.read_text())
        assert "__qv_meta__" in data
        assert data["__qv_meta__"]["source_step_ulid"] == relax_step_ulid
        assert data["__qv_meta__"]["provenance"]["method"] == "pyscf_relax"
    
    def test_pyscf_relax_structure_changes(
        self,
        pyscf_calculation_with_relax,
        pyscf_project_with_h2,
    ):
        """
        Test that the relaxed structure has a reasonable H-H bond distance.
        """
        
        calc_ulid = pyscf_calculation_with_relax["calc_ulid"]
        relax_step_ulid = pyscf_calculation_with_relax["relax_step_ulid"]
        calc_dir = pyscf_calculation_with_relax["calc_dir"]
        project_root = pyscf_calculation_with_relax["project_root"]
        
        # Load initial structure
        from quantumvitas.io import read_structure
        initial_structure = read_structure(pyscf_project_with_h2["structure_path"])
        initial_distance = initial_structure.get_distance(0, 1)
        
        # Run the relax step
        svc = QVService(project_root)
        result = svc.run.run_step(
            calc_selector=calc_ulid,
            step_selector=relax_step_ulid,
        )

        assert result.status == "completed", f"Step failed: {result.error.message if result.error else None}"

        # Load relaxed structure
        relaxed_structure = read_generated_structure(calc_dir, relax_step_ulid)
        assert relaxed_structure is not None
        
        relaxed_distance = relaxed_structure.get_distance(0, 1)
        
        # Verify structure changed
        assert relaxed_distance != pytest.approx(initial_distance, abs=0.01), (
            f"Structure should have changed. "
            f"Initial: {initial_distance:.4f}, Relaxed: {relaxed_distance:.4f}"
        )
        
        # Verify relaxed distance is closer to equilibrium (~0.74 A for H2)
        assert 0.70 < relaxed_distance < 0.80, (
            f"H-H bond distance {relaxed_distance:.4f} A is not near equilibrium (~0.74 A)"
        )

