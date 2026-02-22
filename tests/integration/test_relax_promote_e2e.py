"""
End-to-end integration test for relax structure promotion.

This test verifies the complete promote workflow:
1. Create project → import structure → create calculation → create relax step
2. Run relax step (using PySCF for speed, as it's always available)
3. Call promote_relax_structure
4. Verify new structure resource created successfully
5. Verify new structure can be used to create a new calculation

NOTE: These tests are skipped because promote_relax_structure is not yet
implemented in the new domain API (QMSService).
"""

import json
import pytest
import time
import uuid
from pathlib import Path

from qmatsuite.api import QMSService
from qmatsuite.api.errors import APIError
from qmatsuite.core.paths import tmp_runs_dir
from qmatsuite.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
)
from pymatgen.core import Molecule


pytestmark = [pytest.mark.integration]


def configure_step(project_root, calculation_selector, step_selector, parameters):
    """Helper function to configure step parameters via domain accessor."""
    svc = QMSService(project_root)
    svc.calculation.update_step_params(
        calc_selector=calculation_selector,
        step_selector=step_selector,
        params={"parameters": parameters},
    )


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
def promote_test_project():
    """Create a project with H2 molecule for promote E2E test."""
    # Use .tmp/runs/ directory with unique name
    unique_id = f"promote_e2e_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    test_dir = tmp_runs_dir() / unique_id
    test_dir.mkdir(parents=True, exist_ok=True)
    
    project_root = QMSService.init_project(test_dir / "promote_e2e_project")
    
    # Create H2 molecule (simple case for quick test)
    h2_molecule = Molecule(["H", "H"], [[0, 0, 0], [0.8, 0, 0]])
    
    # Save molecule to file manually
    structures_dir = project_root / "structures"
    structures_dir.mkdir(parents=True, exist_ok=True)
    
    from qmatsuite.core.resources import generate_resource_id
    structure_ulid = generate_resource_id()
    structure_data = {
        "__qms_meta__": {
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
def promote_test_calculation_with_relax(promote_test_project):
    """Create a calculation with a relax step, configured for PySCF."""
    project_root = promote_test_project["project_root"]
    structure_ulid = promote_test_project["structure_ulid"]
    
    # Create calculation with molecule/pyscf settings
    calc_result = QMSService(project_root).project.init_calculation(
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
    relax_step_result = QMSService(project_root).calculation.add_step(
        calc_ulid,
        step_type_gen="relax",  # GEN type for UI layer
        name="relax",
    )
    relax_step_ulid = relax_step_result.ulid
    
    # Configure relax step with minimal parameters for quick test
    configure_step(
        project_root=project_root,
        calculation_selector=calc_ulid,
        step_selector=relax_step_ulid,
        parameters={
            "method": "rhf",
            "basis": "sto-3g",  # Minimal basis for speed
            "maxsteps": 50,
        },
    )
    
    return {
        "project_root": project_root,
        "calc_ulid": calc_ulid,
        "calc_dir": calc_dir,
        "relax_step_ulid": relax_step_ulid,
        "structure_ulid": structure_ulid,
    }


class TestRelaxPromoteE2E:
    """End-to-end tests for relax structure promotion."""
    
    def test_promote_creates_new_structure_resource(
        self,
        promote_test_calculation_with_relax,
    ):
        """
        Test that promoting a relax structure creates a new structure resource.
        """
        calc_ulid = promote_test_calculation_with_relax["calc_ulid"]
        relax_step_ulid = promote_test_calculation_with_relax["relax_step_ulid"]
        project_root = promote_test_calculation_with_relax["project_root"]
        initial_structure_ulid = promote_test_calculation_with_relax["structure_ulid"]
        
        # Get initial structure count via nested service method (DTO)
        svc = QMSService(project_root)
        initial_structures = svc.structure.list()
        initial_count = len(initial_structures)
        
        # Run the relax step
        result = svc.run.run_step(
            calc_selector=calc_ulid,
            step_selector=relax_step_ulid,
        )

        assert result.status == "completed", f"Step failed: {result.error.message if result.error else None}"

        # Verify current.json exists
        calc_dir = promote_test_calculation_with_relax["calc_dir"]
        artifact_path = get_generated_structure_path(calc_dir, relax_step_ulid)
        assert artifact_path.exists(), "current.json should exist after relax step"

        # Promote the relaxed structure
        promoted_result = svc.structure.promote_relax_structure(
            calculation_selector=calc_ulid,
            step_selector=relax_step_ulid,
            name="relaxed_h2",
        )

        # Verify new structure was created via nested service method (DTO)
        all_structures = svc.structure.list()
        assert len(all_structures) == initial_count + 1, "Should have one more structure"
        
        # Verify promoted structure has different ULID
        assert promoted_result.meta.ulid != initial_structure_ulid, "Promoted structure should have different ULID"
        assert promoted_result.meta.name == "relaxed_h2", "Promoted structure should have correct name"
        # StructureDTO doesn't have absolute_path, compute from slug
        structure_path = project_root / "structures" / f"{promoted_result.meta.slug}.json"
        assert structure_path.exists(), "Promoted structure file should exist"

        # Verify structure content
        from qmatsuite.io import read_structure
        promoted_structure = read_structure(structure_path)
        assert promoted_structure is not None
        assert len(promoted_structure) == 2, "Should have 2 H atoms"
        
        # Verify bond distance is reasonable (relaxed from 0.8 to ~0.74)
        bond_distance = promoted_structure.get_distance(0, 1)
        assert 0.70 < bond_distance < 0.80, f"H-H bond distance {bond_distance} should be near equilibrium"
    
    def test_promote_requires_current_json(
        self,
        promote_test_calculation_with_relax,
    ):
        """
        Test that promote fails if current.json doesn't exist.
        """
        calc_ulid = promote_test_calculation_with_relax["calc_ulid"]
        relax_step_ulid = promote_test_calculation_with_relax["relax_step_ulid"]
        project_root = promote_test_calculation_with_relax["project_root"]
        
        # Try to promote without running relax step (no current.json)
        svc = QMSService(project_root)
        with pytest.raises(APIError) as exc_info:
            svc.structure.promote_relax_structure(
                calculation_selector=calc_ulid,
                step_selector=relax_step_ulid,
            )
        
        assert "No generated structure found" in str(exc_info.value)
    
    def test_promote_requires_relax_step(
        self,
        promote_test_project,
    ):
        """
        Test that promote fails if the selected step is not a relax step.
        """
        project_root = promote_test_project["project_root"]
        structure_ulid = promote_test_project["structure_ulid"]
        
        # Create calculation
        calc_result = QMSService(project_root).project.init_calculation(
            name="h2_scf",
            structure_selector=structure_ulid,
        )
        calc_ulid = calc_result.ulid
        
        # Set engine_family to pyscf
        import yaml
        calc_dir = calc_result.absolute_path.parent if calc_result.absolute_path.name == "calculation.yaml" else calc_result.absolute_path
        calc_yaml = calc_dir / "calculation.yaml"
        calc_data = yaml.safe_load(calc_yaml.read_text())
        calc_data["engine_family"] = "pyscf"
        calc_data["structure_kind"] = "molecule"
        calc_yaml.write_text(yaml.dump(calc_data))
        
        # Create SCF step (not relax)
        scf_step_result = QMSService(project_root).calculation.add_step(
            calc_ulid,
            step_type_gen="scf",  # GEN type for UI layer
            name="scf",
        )
        scf_step_ulid = scf_step_result.ulid
        
        # Try to promote non-relax step
        svc = QMSService(project_root)
        with pytest.raises(APIError) as exc_info:
            svc.structure.promote_relax_structure(
                calculation_selector=calc_ulid,
                step_selector=scf_step_ulid,
            )

        assert "not a relax step" in str(exc_info.value)
    
    def test_promoted_structure_can_be_used_for_new_calculation(
        self,
        promote_test_calculation_with_relax,
    ):
        """
        Test that a promoted structure can be used to create a new calculation.
        """
        calc_ulid = promote_test_calculation_with_relax["calc_ulid"]
        relax_step_ulid = promote_test_calculation_with_relax["relax_step_ulid"]
        project_root = promote_test_calculation_with_relax["project_root"]
        
        # Run the relax step
        svc = QMSService(project_root)
        result = svc.run.run_step(
            calc_selector=calc_ulid,
            step_selector=relax_step_ulid,
        )

        assert result.status == "completed", f"Step failed: {result.error.message if result.error else None}"

        # Promote the relaxed structure
        promoted_result = svc.structure.promote_relax_structure(
            calculation_selector=calc_ulid,
            step_selector=relax_step_ulid,
            name="relaxed_h2",
        )

        # Create a new calculation using the promoted structure
        new_calc_result = QMSService(project_root).project.init_calculation(
            name="h2_relaxed_scf",
            structure_selector=promoted_result.meta.ulid,
        )
        
        assert new_calc_result.meta.ulid != calc_ulid, "New calculation should have different ULID"
        assert new_calc_result.absolute_path.exists(), "New calculation file should exist"
        
        # Verify the new calculation uses the promoted structure
        import yaml
        new_calc_dir = new_calc_result.absolute_path.parent if new_calc_result.absolute_path.name == "calculation.yaml" else new_calc_result.absolute_path
        new_calc_yaml = new_calc_dir / "calculation.yaml"
        new_calc_data = yaml.safe_load(new_calc_yaml.read_text())
        assert new_calc_data["structure_ulid"] == promoted_result.meta.ulid, "New calculation should use promoted structure"
