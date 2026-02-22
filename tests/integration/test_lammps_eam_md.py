"""
Integration test for LAMMPS EAM MD workflow.

Workflow 2 from implementation plan: EAM MD.
"""

import json
import pytest
import yaml
import shutil
from pathlib import Path

from qmatsuite.api import QMSService
from qmatsuite.calculation.calculation import Calculation
from qmatsuite.calculation.runner import CalculationRunner
from qmatsuite.engine.registry import create_default_registry
from qmatsuite.project.model import Project
from qmatsuite.core.yaml_io import save_yaml_doc
from qmatsuite.core.yamldoc import CalcDoc
from qmatsuite.core.models import load_calculation
from qmatsuite.core.pseudo_provenance import compute_sha256_file
from qmatsuite.core.resources import get_resources_dir


@pytest.fixture
def eam_md_project(tmp_path: Path):
    """Create a LAMMPS project with EAM potential for MD."""
    from qmatsuite.core.engines.lammps_resolver import resolve_lammps_bin
    from pymatgen.core import Structure, Lattice
    
    # Check LAMMPS availability
    try:
        resolve_lammps_bin()
    except FileNotFoundError:
        pytest.skip("LAMMPS not installed")
    
    # Create project
    project_root = QMSService.init_project(
        target_dir=tmp_path / "eam_md_project",
        name="EAM MD Test"
    )
    
    # Create Cu FCC structure
    lattice = Lattice.cubic(3.6)
    structure = Structure(
        lattice,
        ["Cu"] * 4,
        [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]]
    )
    
    # Save structure to temporary file
    struct_file = tmp_path / "cu_fcc.json"
    struct_file.write_text(json.dumps(structure.as_dict()))
    
    # Import structure
    struct_result = QMSService(project_root).structure.import_file(struct_file, name="Cu FCC")
    structure_ulid = struct_result.meta.ulid
    
    # Copy potential file if available
    potential_src = Path(__file__).parent.parent / "data" / "lammps" / "eam_md" / "potentials" / "Cu_u3.eam"
    if not potential_src.exists():
        # Try resources directory
        potential_src = get_resources_dir() / "lammps" / "potentials" / "Cu_u3.eam"
    
    if potential_src.exists():
        potentials_dir = project_root / "potentials"
        potentials_dir.mkdir(exist_ok=True)
        potential_dst = potentials_dir / "Cu_u3.eam"
        shutil.copy2(potential_src, potential_dst)
        potential_sha = compute_sha256_file(potential_dst)
    else:
        pytest.skip("EAM potential file not found")
    
    # Create calculation
    calc_resolved = QMSService(project_root).project.init_calculation(
        name="eam_md",
        structure_selector=structure_ulid,
    )
    calc_id = calc_resolved.meta.ulid
    calc_dir = calc_resolved.absolute_path
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
    # LAMMPS doesn't need species_map, but set empty dict to avoid validation errors
    calc_model.species_map = {}
    calc_model.potential_map = {
        "eam_cu": {
            "style": "eam",
            "file": "potentials/Cu_u3.eam",
            "elements": ["Cu"],
            "sha256": potential_sha,
        }
    }
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    # Create MD step using domain API
    svc = QMSService(project_root)
    step_dto = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type_gen="md",
    )
    step_id = step_dto.step_ulid

    # Configure step parameters using domain API
    # Note: LAMMPS parameters go inside "parameters" dict
    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=step_id,
        params={
            "parameters": {
                "potential": "eam_cu",
                "units": "metal",
                "atom_style": "atomic",
                "ensemble": "nvt",
                "temperature": 300,
                "timestep_fs": 1.0,
                "n_steps": 1000,
                "thermo_frequency": 100,
                "dump_frequency": 100,
                "dump_trajectory": True,
            },
        },
    )
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
    }


@pytest.mark.requires_lammps
def test_eam_md_workflow(eam_md_project):
    """Test EAM MD workflow end-to-end."""
    project_root = eam_md_project["project_root"]
    calc_dir = eam_md_project["calc_dir"]
    
    # Load and run
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    assert result.status.value == "success", f"Calculation failed: {result.steps[0].message if result.steps else 'Unknown error'}"
    
    # Verify output files exist
    working_dir = calculation.raw_dir / calculation.steps[0].meta.ulid
    assert (working_dir / "log.lammps").exists(), "Log file should exist"
    assert (working_dir / "trajectory.lammpstrj").exists(), "Trajectory dump should exist"
    
    print("✓ EAM MD workflow completed successfully")
