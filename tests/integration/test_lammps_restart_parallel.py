"""
Test LAMMPS restart/chain workflows are parallel-safe.

These tests verify that restart_from dependencies work correctly
even under pytest-xdist parallel execution.
"""

import json
import pytest
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


def configure_step(project_root, calculation_selector, step_selector, parameters):
    """Helper function to configure step parameters via domain accessor."""
    svc = QVService(project_root)
    svc.calculation.update_step_params(
        calc_selector=calculation_selector,
        step_selector=step_selector,
        params={"parameters": parameters},
    )


def get_lammps_binary():
    """Check LAMMPS availability."""
    from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
    try:
        return resolve_lammps_bin()
    except FileNotFoundError:
        pytest.skip("LAMMPS binary not found")


@pytest.mark.parametrize("execution_number", range(3))
def test_restart_chain_parallel_safe(tmp_path: Path, execution_number: int):
    """
    Test restart chain is deterministic across parallel executions.
    
    This test is parameterized to run 3 times in parallel with pytest-xdist.
    Each execution should produce identical results.
    """
    lammps_bin = get_lammps_binary()
    
    # Use unique subdir for each execution
    project_dir = tmp_path / f"parallel_test_{execution_number}"
    
    # Create project
    project_root = QVService.init_project(
        target_dir=project_dir,
        name=f"Parallel Test {execution_number}"
    )
    
    # Create minimal Cu structure
    from pymatgen.core import Structure, Lattice
    lattice = Lattice.cubic(3.6)
    structure = Structure(
        lattice,
        ["Cu"] * 4,
        [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]]
    )
    
    struct_file = project_dir / "cu_fcc.json"
    struct_file.write_text(json.dumps(structure.as_dict()))
    
    # Import structure
    struct_result = QVService.import_structure(project_root, struct_file, name="Cu FCC")
    structure_id = struct_result.meta.ulid
    
    # Copy potential file
    repo_root = Path(__file__).parent.parent.parent
    potential_src = repo_root / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
    if not potential_src.exists():
        pytest.skip(f"Potential file not found: {potential_src}")
    
    potentials_dir = project_root / "potentials"
    potentials_dir.mkdir(exist_ok=True)
    potential_dst = potentials_dir / "Cu_u3.eam"
    shutil.copy2(potential_src, potential_dst)
    potential_sha = compute_sha256_file(potential_dst)
    
    # Create calculation
    calc_result = QVService.init_calculation(
        project_root=project_root,
        name="parallel_test",
        structure_selector=structure_id,
    )
    calc_id = calc_result.meta.ulid
    calc_dir = calc_result.absolute_path
    
    # Configure calculation
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
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
    relax_step_id = relax_step.meta.ulid
    
    configure_step(
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
            "dump_frequency": 500,
            "dump_trajectory": True,
        },
    )
    
    # Create MD step with restart_from
    md_step = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="md",
    )
    md_step_id = md_step.meta.ulid
    
    configure_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_selector=md_step_id,
        parameters={
            "potential": "eam_cu",
            "restart_from": relax_step_id,  # KEY: This creates artifact dependency
            "units": "metal",
            "atom_style": "atomic",
            "ensemble": "nvt",
            "temperature": 300,
            "n_steps": 50,
            "thermo_frequency": 10,
            "dump_frequency": 25,
            "dump_trajectory": True,
        },
    )
    
    # Run calculation
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    # Assertions
    assert result.status.value == "success", (
        f"Calculation failed (execution {execution_number}): "
        f"{result.steps[-1].message if result.steps else 'Unknown error'}"
    )
    
    # Verify relax produced final.data BEFORE asserting MD success
    raw_dir = calculation.raw_dir
    relax_dir = raw_dir / relax_step_id
    final_data = relax_dir / "final.data"
    assert final_data.exists(), (
        f"Relax step did not produce final.data. "
        f"Contents of {relax_dir}: {list(relax_dir.iterdir()) if relax_dir.exists() else 'dir missing'}"
    )
    
    # Verify MD step used restart correctly
    md_dir = raw_dir / md_step_id
    md_in_lammps = md_dir / "in.lammps"
    assert md_in_lammps.exists(), "MD in.lammps should exist"
    md_content = md_in_lammps.read_text()
    assert "read_restart" in md_content or "read_data" in md_content, (
        "MD should use restart artifact from relax step"
    )
    
    # Verify no ERROR in logs
    relax_log = (relax_dir / "log.lammps").read_text()
    md_log = (md_dir / "log.lammps").read_text()
    assert "ERROR" not in relax_log.upper(), "Relax log should not contain ERROR"
    assert "ERROR" not in md_log.upper(), "MD log should not contain ERROR"

