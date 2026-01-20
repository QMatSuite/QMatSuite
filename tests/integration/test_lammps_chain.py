"""
Integration test for LAMMPS chain workflow (relax → MD → restart).

Workflow 3 from implementation plan: Relax → MD → Restart.
"""

import json
import pytest
import yaml
import shutil
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.core.yaml_io import save_yaml_doc
from quantumvitas.core.yamldoc import CalcDoc
from quantumvitas.core.models import load_calculation
from quantumvitas.core.pseudo_provenance import compute_sha256_file


@pytest.fixture
def chain_project(tmp_path: Path):
    """Create a LAMMPS project with chain workflow (relax → MD → restart)."""
    from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
    from pymatgen.core import Structure, Lattice
    
    # Check LAMMPS availability
    try:
        resolve_lammps_bin()
    except FileNotFoundError:
        pytest.skip("LAMMPS not installed")
    
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "chain_project",
        name="Chain Workflow Test"
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
    struct_result = QVService.import_structure(project_root, struct_file, name="Cu FCC")
    structure_id = struct_result.meta.id
    
    # Copy potential file if available
    potential_src = Path(__file__).parent.parent / "data" / "lammps" / "chain_workflow" / "potentials" / "Cu_u3.eam"
    if not potential_src.exists():
        # Try resources directory
        potential_src = Path(__file__).parent.parent.parent.parent / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
    
    if potential_src.exists():
        potentials_dir = project_root / "potentials"
        potentials_dir.mkdir(exist_ok=True)
        potential_dst = potentials_dir / "Cu_u3.eam"
        shutil.copy2(potential_src, potential_dst)
        potential_sha = compute_sha256_file(potential_dst)
    else:
        pytest.skip("EAM potential file not found")
    
    # Create calculation
    calc_resolved = QVService.init_calculation(
        project_root=project_root,
        name="chain_workflow",
        structure_selector=structure_id,
    )
    calc_id = calc_resolved.meta.id
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
    
    # Create relax step
    relax_step = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="relax",
    )
    relax_step_id = relax_step.meta.id
    
    QVService.configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=relax_step_id,
        parameters={
            "potential": "eam_cu",
            "units": "metal",
            "atom_style": "atomic",
            "energy_tolerance": 1e-4,
            "force_tolerance": 1e-6,
            "thermo_frequency": 100,
            "dump_frequency": 1000,
            "dump_trajectory": True,
        },
    )
    
    # Create first MD step (restart_from relax)
    md_step = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="md",
    )
    md_step_id = md_step.meta.id
    
    QVService.configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=md_step_id,
        parameters={
            "potential": "eam_cu",
            "restart_from": relax_step_id,  # Use final.data from relax
            "units": "metal",
            "atom_style": "atomic",
            "ensemble": "nvt",
            "temperature": 300,
            "n_steps": 1000,
            "thermo_frequency": 100,
            "dump_frequency": 100,
            "dump_trajectory": True,
        },
    )
    
    # Create second MD step (restart_from first MD)
    continue_md = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="md",
    )
    continue_md_id = continue_md.meta.id
    
    QVService.configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=continue_md_id,
        parameters={
            "potential": "eam_cu",
            "restart_from": md_step_id,  # Use restart.bin from first MD
            "units": "metal",
            "atom_style": "atomic",
            "ensemble": "nvt",
            "temperature": 300,
            "n_steps": 1000,
            "thermo_frequency": 100,
            "dump_frequency": 100,
            "dump_trajectory": True,
        },
    )
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
    }


@pytest.mark.requires_lammps
def test_chain_workflow(chain_project):
    """Test chain workflow (relax → MD → restart) end-to-end."""
    project_root = chain_project["project_root"]
    calc_dir = chain_project["calc_dir"]
    
    # Load and run
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    assert result.status.value == "success", f"Calculation failed: {result.steps[-1].message if result.steps else 'Unknown error'}"
    
    # Verify all steps completed
    assert len(result.steps) == 3, "Should have 3 steps"
    
    # Verify restart artifacts exist
    relax_dir = calculation.raw_dir / calculation.steps[0].meta.id
    md_dir = calculation.raw_dir / calculation.steps[1].meta.id
    
    assert (relax_dir / "final.data").exists(), "Relax should produce final.data"
    assert (md_dir / "restart.bin").exists() or (md_dir / "restart.final.bin").exists(), "MD should produce restart file"
    
    print("✓ Chain workflow completed successfully")
