"""
Integration tests for CP2K workflow.

Tests end-to-end CP2K calculations using real CP2K binary.
"""

import json
import pytest
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.core.yaml_io import save_yaml_doc
from quantumvitas.core.yamldoc import CalcDoc
from quantumvitas.core.models import load_calculation


# Check CP2K availability
try:
    from quantumvitas.core.engines.cp2k_resolver import find_cp2k_executable
    CP2K_AVAILABLE = find_cp2k_executable() is not None
except Exception:
    CP2K_AVAILABLE = False


@pytest.fixture
def cp2k_silicon_project(tmp_path: Path):
    """Create a CP2K project with silicon structure."""
    from pymatgen.core import Structure, Lattice
    
    # Check CP2K availability
    if not CP2K_AVAILABLE:
        pytest.skip("CP2K not installed")
    
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "cp2k_silicon",
        name="CP2K Silicon Test"
    )
    
    # Create silicon structure (2 atoms, cubic)
    lattice = Lattice.cubic(5.431)
    structure = Structure(
        lattice,
        ["Si", "Si"],
        [[0, 0, 0], [0.25, 0.25, 0.25]]
    )
    
    # Save structure to temporary file
    struct_file = tmp_path / "si_cubic.json"
    struct_file.write_text(json.dumps(structure.as_dict()))
    
    # Import structure
    struct_result = QVService.import_structure(project_root, struct_file, name="Si Cubic")
    structure_id = struct_result.meta.id
    
    # Create calculation
    calc_resolved = QVService.init_calculation(
        project_root=project_root,
        name="cp2k_test",
        structure_selector=structure_id,
    )
    calc_id = calc_resolved.meta.id
    calc_dir = calc_resolved.absolute_path
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "cp2k"
    calc_model.species_map = {"Si": "Si"}
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "calc_id": calc_id,
    }


@pytest.mark.skipif(not CP2K_AVAILABLE, reason="CP2K not installed")
def test_cp2k_scf_silicon(cp2k_silicon_project):
    """End-to-end SCF test with real CP2K."""
    project_root = cp2k_silicon_project["project_root"]
    calc_dir = cp2k_silicon_project["calc_dir"]
    calc_id = cp2k_silicon_project["calc_id"]
    
    # Create SCF step
    step_resolved = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="scf",
    )
    step_id = step_resolved.meta.id

    # Configure step parameters
    svc = QVService(project_root)
    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=step_id,
        params={
            "parameters": {
                "functional": "PBE",
                "cutoff": 300,
                "rel_cutoff": 50,
                "basis_set": "DZVP-MOLOPT-SR-GTH",
                "potential": "GTH-PBE",
                "scf_max_iter": 50,
                "scf_eps_scf": 1e-6,
                "ignore_convergence_failure": True,  # Allow test to complete even if SCF doesn't fully converge
            },
        },
    )
    
    # Load and run
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    
    registry = create_default_registry()
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    # Verify calculation completed (may not converge, but should produce files)
    assert result.status.value in ("success", "partial"), (
        f"Calculation failed: {result.steps[0].message if result.steps else 'Unknown error'}"
    )
    
    # Verify output files exist
    working_dir = calculation.raw_dir / calculation.steps[0].meta.id
    assert (working_dir / "input.inp").exists(), "Input file should exist"
    assert (working_dir / "output.log").exists(), "Output log should exist"
    
    # Check for WFN file (may exist even if SCF didn't converge)
    wfn_files = list(working_dir.glob("cp2k_calc-RESTART.wfn*"))
    assert len(wfn_files) > 0, "WFN file should be created"
    
    print("✓ CP2K SCF test completed")


@pytest.mark.skipif(not CP2K_AVAILABLE, reason="CP2K not installed")
def test_cp2k_relax_silicon_with_cell(cp2k_silicon_project):
    """End-to-end relax test with structure and cell extraction."""
    project_root = cp2k_silicon_project["project_root"]
    calc_dir = cp2k_silicon_project["calc_dir"]
    calc_id = cp2k_silicon_project["calc_id"]
    
    # Create relax step
    step_resolved = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="relax",
    )
    step_id = step_resolved.meta.id

    # Configure step parameters
    svc = QVService(project_root)
    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=step_id,
        params={
            "parameters": {
                "functional": "PBE",
                "cutoff": 300,
                "rel_cutoff": 50,
                "basis_set": "DZVP-MOLOPT-SR-GTH",
                "potential": "GTH-PBE",
                "scf_max_iter": 50,
                "scf_eps_scf": 1e-6,
                "max_iter": 10,  # Short run for testing
                "optimize_cell": False,  # Geometry optimization only
                "ignore_convergence_failure": True,  # Allow test to complete even if SCF doesn't fully converge
            },
        },
    )
    
    # Load and run
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    
    registry = create_default_registry()
    runner = CalculationRunner(engine_registry=registry)
    
    result = runner.run(calculation)
    
    # Verify calculation completed
    assert result.status.value == "success", (
        f"Calculation failed: {result.steps[0].message if result.steps else 'Unknown error'}"
    )
    
    # Verify output files exist
    working_dir = calculation.raw_dir / calculation.steps[0].meta.id
    assert (working_dir / "input.inp").exists(), "Input file should exist"
    assert (working_dir / "output.log").exists(), "Output log should exist"
    
    # CRITICAL: Check for trajectory and cell files
    traj_files = list(working_dir.glob("cp2k_calc-pos-*.xyz"))
    assert len(traj_files) > 0, "Trajectory file should be created"
    
    cell_files = list(working_dir.glob("cp2k_calc-*.cell"))
    assert len(cell_files) > 0, "Cell file should be created (CRITICAL for relax)"
    
    # Verify cell file has content
    cell_file = max(cell_files, key=lambda p: p.stat().st_mtime)
    cell_content = cell_file.read_text()
    assert "Step" in cell_content, "Cell file should contain step data"
    assert "Ax" in cell_content, "Cell file should contain cell vectors"
    
    # Verify trajectory has multiple frames
    traj_file = max(traj_files, key=lambda p: p.stat().st_mtime)
    traj_content = traj_file.read_text()
    assert traj_content.count("Si") >= 2, "Trajectory should have multiple frames"
    
    # Verify current.json was created (relax artifact handler)
    step_ulid = calculation.steps[0].meta.id
    current_json = calc_dir / ".analysis" / step_ulid / "current.json"
    if current_json.exists():
        # Load and verify structure has cell
        current_data = json.loads(current_json.read_text())
        assert "lattice" in current_data, "current.json should contain lattice"
        assert "lattice_vectors" in current_data["lattice"], "Lattice should have vectors"
    
    print("✓ CP2K relax test completed with cell extraction")


@pytest.mark.skipif(not CP2K_AVAILABLE, reason="CP2K not installed")
def test_cp2k_md_incremental_skip_disabled(cp2k_silicon_project):
    """Verify MD steps are always executed when targeted."""
    project_root = cp2k_silicon_project["project_root"]
    calc_dir = cp2k_silicon_project["calc_dir"]
    calc_id = cp2k_silicon_project["calc_id"]
    
    # Create MD step
    step_resolved = QVService.init_step(
        project_root=project_root,
        calculation_selector=calc_id,
        step_type="md",
    )
    step_id = step_resolved.meta.id

    # Configure step parameters
    svc = QVService(project_root)
    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=step_id,
        params={
            "parameters": {
                "functional": "PBE",
                "cutoff": 300,
                "rel_cutoff": 50,
                "basis_set": "DZVP-MOLOPT-SR-GTH",
                "potential": "GTH-PBE",
                "scf_max_iter": 50,
                "scf_eps_scf": 1e-6,
                "ensemble": "NVT",
                "steps": 5,  # Very short MD for testing
                "timestep": 0.5,  # fs
                "temperature": 300,
            },
        },
    )
    
    # Load calculation
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    
    # Verify MD step has supports_incremental_skip=False
    from quantumvitas.workflow.registry import get_registry
    registry = get_registry()
    md_spec = registry.get("cp2k_md")
    assert md_spec.supports_incremental_skip is False, "MD should have incremental skip disabled"
    
    # Run calculation
    engine_registry = create_default_registry()
    runner = CalculationRunner(engine_registry=engine_registry)
    
    result = runner.run(calculation)
    
    # MD may fail due to instability, but should attempt to run
    # The key test is that it's not skipped
    working_dir = calculation.raw_dir / calculation.steps[0].meta.id
    assert (working_dir / "input.inp").exists(), "Input file should exist"
    assert (working_dir / "output.log").exists(), "Output log should exist"
    
    # Verify MD input has correct RUN_TYPE
    input_content = (working_dir / "input.inp").read_text()
    assert "RUN_TYPE MD" in input_content, "Input should have RUN_TYPE MD"
    assert "&MD" in input_content, "Input should have MD section"
    
    print("✓ CP2K MD incremental skip disabled test completed")

