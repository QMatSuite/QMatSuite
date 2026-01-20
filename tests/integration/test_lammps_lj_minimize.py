"""
Integration test for LAMMPS LJ minimize workflow.

Workflow 1 from implementation plan: LJ minimize (simplest).
"""

import json
import pytest
import yaml
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.core.yaml_io import save_yaml_doc
from quantumvitas.core.yamldoc import CalcDoc
from quantumvitas.core.models import load_calculation


@pytest.fixture
def lj_project(tmp_path: Path):
    """Create a LAMMPS project using Service API."""
    from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
    from pymatgen.core import Structure, Lattice
    
    # Check LAMMPS availability
    try:
        resolve_lammps_bin()
    except FileNotFoundError:
        pytest.skip("LAMMPS not installed")
    
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "lj_project",
        name="LJ Minimize Test"
    )
    
    # Create LJ structure (simple FCC for Ar)
    lattice = Lattice.cubic(5.0)
    structure = Structure(
        lattice,
        ["Ar"] * 4,
        [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]]
    )
    
    # Save structure to temporary file
    struct_file = tmp_path / "ar_fcc.json"
    struct_file.write_text(json.dumps(structure.as_dict()))
    
    # Import structure
    struct_result = QVService.import_structure(project_root, struct_file, name="Ar FCC")
    structure_id = struct_result.meta.id
    
    # Create calculation
    calc_resolved = QVService.init_calculation(
        project_root=project_root,
        name="lj_minimize",
        structure_selector=structure_id,
    )
    calc_id = calc_resolved.meta.id
    calc_dir = calc_resolved.absolute_path
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
    # LAMMPS doesn't need species_map, but set empty dict to avoid validation errors
    calc_model.species_map = {}
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    # Create relax step
    step_resolved = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="relax",
    )
    step_id = step_resolved.meta.id
    
    # Configure step parameters
    QVService.configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=step_id,
        parameters={
            "units": "lj",
            "atom_style": "atomic",
            "lj_system": {
                "masses": {1: 1.0},
                "type_labels": {1: "Ar"},
            },
            "potential": {
                "style": "lj/cut",
                "cutoff": 2.5,
                "params": {"1 1": "1.0 1.0"},
            },
            "energy_tolerance": 1e-6,
            "force_tolerance": 1e-8,
            "max_iterations": 1000,
            "max_evaluations": 10000,
            "thermo_frequency": 100,
            "dump_frequency": 1000,
            "dump_trajectory": True,
        },
    )
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
    }


@pytest.mark.requires_lammps
def test_lj_minimize_workflow(lj_project):
    """Test LJ minimize workflow end-to-end."""
    project_root = lj_project["project_root"]
    calc_dir = lj_project["calc_dir"]
    
    # Load and run
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    assert result.status.value == "success", f"Calculation failed: {result.steps[0].message if result.steps else 'Unknown error'}"
    
    # Verify output files exist
    working_dir = calculation.raw_dir / calculation.steps[0].meta.id
    assert (working_dir / "log.lammps").exists(), "Log file should exist"
    assert (working_dir / "final.data").exists(), "Final structure should exist"
    
    print("✓ LJ minimize workflow completed successfully")
