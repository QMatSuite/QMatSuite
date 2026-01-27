"""
LAMMPS Incremental Skip Tests

Verifies that incremental skip logic correctly detects changes in:
1. Inline LJ potential dict (should affect step_sha)
2. External potential file content (should affect potential_assets_sha)

These tests ensure that potential changes trigger recalculation instead of skipping.
"""

import json
import pytest
import shutil
import yaml
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.calculation.calculation import Calculation
from quantumvitas.calculation.runner import CalculationRunner
from quantumvitas.engine.registry import create_default_registry
from quantumvitas.project.model import Project
from quantumvitas.core.yaml_io import save_yaml_doc
from quantumvitas.core.yamldoc import CalcDoc, StepDoc
from quantumvitas.core.models import load_calculation
from quantumvitas.core.pseudo_provenance import compute_sha256_file
from quantumvitas.calculation.hash_utils import compute_step_sha, compute_potential_assets_sha
from quantumvitas.calculation.manifest import load_manifest, ManifestStepEntry


def get_lammps_binary_info():
    """Get LAMMPS binary path or skip with diagnostic."""
    from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin
    
    try:
        return resolve_lammps_bin()
    except FileNotFoundError as e:
        pytest.skip(f"LAMMPS binary not found: {e}")


@pytest.fixture(scope="module")
def lammps_binary():
    """Check LAMMPS binary availability."""
    return get_lammps_binary_info()


@pytest.fixture
def inline_lj_project(tmp_path: Path, lammps_binary):
    """Create a minimal LAMMPS project with inline LJ potential."""
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "inline_lj",
        name="Inline LJ Test"
    )
    
    # Create minimal structure
    from pymatgen.core import Structure, Lattice
    lattice = Lattice.cubic(5.0)
    structure = Structure(
        lattice,
        ["Ar"] * 4,
        [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]]
    )
    
    struct_file = tmp_path / "ar_fcc.json"
    struct_file.write_text(json.dumps(structure.as_dict()))
    
    # Import structure
    struct_result = QVService.import_structure(project_root, struct_file, name="Ar FCC")
    structure_id = struct_result.meta.id
    
    # Create calculation
    calc_result = QVService.init_calculation(
        project_root=project_root,
        name="inline_lj",
        structure_selector=structure_id,
    )
    calc_id = calc_result.meta.id
    calc_dir = calc_result.absolute_path
    
    # Configure calculation
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
    calc_model.species_map = {}
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    # Create relax step with inline LJ potential using domain API
    svc = QVService(project_root)
    step = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type="relax",
    )
    step_id = step.step_id

    # Configure step with initial LJ parameters using domain API
    # Note: LAMMPS parameters go inside "parameters" dict
    svc.calculation.update_step_params(
        calc_selector=calc_id,
        step_selector=step_id,
        params={
            "parameters": {
                "potential": {
                    "style": "lj/cut",
                    "cutoff": 2.5,
                    "params": {"* *": "1.0 1.0"},  # epsilon=1.0, sigma=1.0
                },
                "units": "lj",
                "atom_style": "atomic",
                "energy_tolerance": 1e-4,
                "force_tolerance": 1e-6,
                "thermo_frequency": 100,
                "dump_frequency": 1000,
                "dump_trajectory": True,
            },
        },
    )
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "step_id": step_id,
        "calc_id": calc_id,
    }


def test_inline_lj_potential_affects_skip(inline_lj_project, lammps_binary):
    """
    Test that changing inline LJ potential dict triggers recalculation.
    
    Steps:
    1. Run calculation with initial LJ parameters (epsilon=1.0, sigma=1.0)
    2. Verify step completes and manifest records done=True
    3. Modify step.yaml to change LJ parameters (epsilon=2.0, sigma=1.0)
    4. Run incremental calculation
    5. Assert step is NOT skipped (should rerun due to step_sha change)
    """
    project_root = inline_lj_project["project_root"]
    calc_dir = inline_lj_project["calc_dir"]
    step_id = inline_lj_project["step_id"]
    calc_id = inline_lj_project["calc_id"]
    
    # First run
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result1 = runner.run(calculation, run_mode="incremental")
    assert result1.status.value == "success", "First run should succeed"
    
    # Verify step completed
    step_dir = calculation.raw_dir / step_id
    assert (step_dir / "log.lammps").exists(), "First run should produce log"
    
    # Load manifest and verify done=True
    from quantumvitas.calculation.manifest import load_manifest
    manifest = load_manifest(calc_dir)
    assert manifest is not None, "Manifest should exist"
    assert len(manifest.steps) > 0, "Manifest should have step entry"
    
    step_entry = manifest.steps[0]
    assert step_entry.done, "Step should be marked done after first run"
    first_run_id = step_entry.run_id
    first_done_at = step_entry.done_at
    first_step_sha = step_entry.step_sha
    
    # Get step file path using resolution
    from quantumvitas.core.resolution import require_step
    from quantumvitas.core.project_utils import load_project_config
    config = load_project_config(project_root)
    step_resolved = require_step(project_root, calc_id, step_id, config=config)
    step_path = step_resolved.absolute_path
    assert step_path.exists(), f"Step file should exist: {step_path}"
    
    # Modify step.yaml: change epsilon from 1.0 to 2.0
    step_doc = StepDoc.load(step_path)
    step_dict = step_doc.to_dict()
    
    # Change potential params: "* *": "1.0 1.0" -> "* *": "2.0 1.0" (epsilon changed)
    params = step_dict.get("parameters", {})
    potential = params.get("potential", {})
    potential_params = potential.get("params", {})
    assert "* *" in potential_params, "Should have * * param"
    assert potential_params["* *"] == "1.0 1.0", "Initial epsilon should be 1.0"
    
    potential_params["* *"] = "2.0 1.0"  # Change epsilon to 2.0
    potential["params"] = potential_params
    params["potential"] = potential
    step_dict["parameters"] = params
    
    # Save modified step
    step_doc_modified = StepDoc(step_dict)
    step_doc_modified.save(step_path)
    
    # Verify step_sha changed
    new_step_sha = compute_step_sha(step_path)
    assert new_step_sha != first_step_sha, "step_sha should change when potential params change"
    
    # Second run (incremental)
    calculation = Calculation.from_yaml(calc_dir, project)
    result2 = runner.run(calculation, run_mode="incremental")
    assert result2.status.value == "success", "Second run should succeed"
    
    # Verify step was NOT skipped (check run_id or done_at changed)
    manifest2 = load_manifest(calc_dir)
    assert manifest2 is not None, "Manifest should exist after second run"
    assert len(manifest2.steps) > 0, "Manifest should have step entry"
    
    step_entry2 = manifest2.steps[0]
    assert step_entry2.done, "Step should be done after second run"
    
    # Verify step was rerun (run_id or done_at should be different)
    # Note: run_id might be same if executor reuses it, but done_at should be newer
    # More reliable: check that log file was regenerated (mtime changed)
    import time
    time.sleep(0.1)  # Ensure different timestamp
    
    # Check that step actually executed (log file should be newer or run_id different)
    # If step was skipped, done_at would be same; if rerun, done_at should be newer
    assert step_entry2.done_at != first_done_at or step_entry2.run_id != first_run_id, \
        "Step should have been rerun (done_at or run_id should change)"
    
    # Verify new step_sha is recorded
    assert step_entry2.step_sha == new_step_sha, "Manifest should record new step_sha"


@pytest.fixture
def external_potential_project(tmp_path: Path, lammps_binary):
    """Create a minimal LAMMPS project with external EAM potential."""
    # Create project
    project_root = QVService.init_project(
        target_dir=tmp_path / "external_pot",
        name="External Potential Test"
    )
    
    # Create minimal Cu structure
    from pymatgen.core import Structure, Lattice
    lattice = Lattice.cubic(3.6)
    structure = Structure(
        lattice,
        ["Cu"] * 4,
        [[0, 0, 0], [0.5, 0.5, 0], [0.5, 0, 0.5], [0, 0.5, 0.5]]
    )
    
    struct_file = tmp_path / "cu_fcc.json"
    struct_file.write_text(json.dumps(structure.as_dict()))
    
    # Import structure
    struct_result = QVService.import_structure(project_root, struct_file, name="Cu FCC")
    structure_id = struct_result.meta.id
    
    # Copy potential file from resources
    repo_root = Path(__file__).parent.parent.parent
    potential_src = repo_root / "resources" / "lammps" / "potentials" / "Cu_u3.eam"
    if not potential_src.exists():
        pytest.skip(f"Potential file not found: {potential_src}")
    
    potentials_dir = project_root / "potentials"
    potentials_dir.mkdir(exist_ok=True)
    potential_dst = potentials_dir / "Cu_u3.eam"
    shutil.copy2(potential_src, potential_dst)
    initial_sha = compute_sha256_file(potential_dst)
    
    # Create calculation
    calc_result = QVService.init_calculation(
        project_root=project_root,
        name="external_pot",
        structure_selector=structure_id,
    )
    calc_id = calc_result.meta.id
    calc_dir = calc_result.absolute_path
    
    # Configure calculation with potential_map
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.engine_family = "lammps"
    calc_model.species_map = {}
    calc_model.potential_map = {
        "eam_cu": {
            "style": "eam",
            "file": "potentials/Cu_u3.eam",
            "elements": ["Cu"],
            "sha256": initial_sha,
        }
    }
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    # Create MD step using domain API
    svc = QVService(project_root)
    step = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type="md",
    )
    step_id = step.step_id

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
                "n_steps": 50,  # Short run
                "thermo_frequency": 10,
                "dump_frequency": 25,
                "dump_trajectory": True,
            },
        },
    )
    
    return {
        "project_root": project_root,
        "calc_dir": calc_dir,
        "step_id": step_id,
        "calc_id": calc_id,
        "potential_file": potential_dst,
        "initial_sha": initial_sha,
    }


def test_external_potential_file_content_affects_skip(external_potential_project, lammps_binary):
    """
    Test that changing external potential file content triggers recalculation.
    
    Steps:
    1. Run calculation with initial potential file
    2. Verify step completes and manifest records done=True with initial potential_assets_sha
    3. Modify potential file content (add a comment or change a value)
    4. Update calculation.yaml potential_map sha256
    5. Run incremental calculation
    6. Assert step is NOT skipped (should rerun due to potential_assets_sha change)
    """
    project_root = external_potential_project["project_root"]
    calc_dir = external_potential_project["calc_dir"]
    step_id = external_potential_project["step_id"]
    calc_id = external_potential_project["calc_id"]
    potential_file = external_potential_project["potential_file"]
    initial_sha = external_potential_project["initial_sha"]
    
    # First run
    project = Project.open(project_root)
    calculation = Calculation.from_yaml(calc_dir, project)
    registry = create_default_registry(include_lammps=True)
    runner = CalculationRunner(engine_registry=registry)
    
    result1 = runner.run(calculation, run_mode="incremental")
    assert result1.status.value == "success", "First run should succeed"
    
    # Verify step completed
    step_dir = calculation.raw_dir / step_id
    assert (step_dir / "log.lammps").exists(), "First run should produce log"
    
    # Load manifest and verify done=True
    manifest = load_manifest(calc_dir)
    assert manifest is not None, "Manifest should exist"
    assert len(manifest.steps) > 0, "Manifest should have step entry"
    
    step_entry = manifest.steps[0]
    assert step_entry.done, "Step should be marked done after first run"
    first_run_id = step_entry.run_id
    first_done_at = step_entry.done_at
    first_pseudo_sha = step_entry.pseudo_set_sha  # For LAMMPS, this is potential_assets_sha
    
    # Verify initial potential_assets_sha
    initial_potential_sha = compute_potential_assets_sha(calculation.potential_map)
    assert first_pseudo_sha == initial_potential_sha, "Manifest should record initial potential_assets_sha"
    
    # Modify potential file content (add a comment at the end)
    # This changes file content but keeps it valid
    original_content = potential_file.read_text()
    modified_content = original_content + "\n# Modified for test\n"
    potential_file.write_text(modified_content)
    
    # Compute new SHA256
    new_sha = compute_sha256_file(potential_file)
    assert new_sha != initial_sha, "SHA256 should change when file content changes"
    
    # Update calculation.yaml potential_map sha256
    calc_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_path, project_root=project_root)
    calc_model.potential_map["eam_cu"]["sha256"] = new_sha
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_path)
    
    # Verify new potential_assets_sha
    new_potential_sha = compute_potential_assets_sha(calc_model.potential_map)
    assert new_potential_sha != initial_potential_sha, "potential_assets_sha should change when file SHA256 changes"
    
    # Second run (incremental)
    calculation = Calculation.from_yaml(calc_dir, project)
    result2 = runner.run(calculation, run_mode="incremental")
    assert result2.status.value == "success", "Second run should succeed"
    
    # Verify step was NOT skipped
    manifest2 = load_manifest(calc_dir)
    assert manifest2 is not None, "Manifest should exist after second run"
    assert len(manifest2.steps) > 0, "Manifest should have step entry"
    
    step_entry2 = manifest2.steps[0]
    assert step_entry2.done, "Step should be done after second run"
    
    # Verify step was rerun (done_at should be newer or run_id different)
    assert step_entry2.done_at != first_done_at or step_entry2.run_id != first_run_id, \
        "Step should have been rerun (done_at or run_id should change)"
    
    # Verify new potential_assets_sha is recorded
    assert step_entry2.pseudo_set_sha == new_potential_sha, \
        "Manifest should record new potential_assets_sha"

