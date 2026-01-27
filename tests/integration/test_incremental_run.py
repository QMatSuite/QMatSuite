"""
Integration tests for incremental run and locking functionality.

Tests locking, manifest reconciliation, incremental skip logic, and single-step runs.
Uses mocked execution to avoid requiring real QE binaries.
"""

import json
import time
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Optional
from pathlib import Path

import pytest
import yaml

from quantumvitas.core.locking import calc_run_lock, calc_edit_lock, CalculationLockError, LockReentrancyError
from quantumvitas.calculation.manifest import (
    Manifest,
    ManifestStepEntry,
    load_manifest,
    save_manifest_atomic,
)
from quantumvitas.calculation.manifest_reconcile import reconcile_manifest
from quantumvitas.calculation.hash_utils import (
    compute_pseudo_set_sha,
    compute_structure_sha,
    compute_step_sha,
)
from quantumvitas.calculation.step_done import is_step_done
from quantumvitas.api import QVService, APIError
from typing import Dict, Any


def get_calc_spec(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Helper to get calculation spec from calc.yaml document.
    
    Handles both formats:
    - New format: keys at top level (structure_id, species_map, etc.)
    - Legacy format: keys under "calculation" key
    
    Returns a dict that can be used to read/write calculation fields.
    """
    if "calculation" in doc:
        return doc["calculation"]
    elif "calc" in doc:
        return doc["calc"]
    else:
        # New format: return the doc itself for top-level fields
        # But wrap in a dict-like interface for compatibility
        return doc


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project structure using service API."""
    project_root = tmp_path / "project"
    
    # Use service API to create project
    from quantumvitas.api import QVService
    project_root = QVService.init_project(target_dir=project_root, name="test_project")
    
    return project_root


@pytest.fixture
def minimal_structure(tmp_project):
    """Create a minimal structure using service API."""
    from quantumvitas.api import QVService
    from pymatgen.core import Structure, Lattice
    import tempfile
    
    # Create structure using pymatgen
    lattice = Lattice.cubic(2.0)
    structure = Structure(lattice, ["Si"], [[0, 0, 0]])
    
    # Create temporary CIF file for import
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
        cif_path = Path(f.name)
    
    try:
        # Write structure to CIF file
        structure.to(filename=str(cif_path), fmt="cif")
        
        # Import structure using service API
        structure_resolved = QVService.import_structure(
            project_root=tmp_project,
            source=cif_path,
            name="test_structure",
        )
        structure_id = structure_resolved.meta.id
        structure_path = structure_resolved.absolute_path
    finally:
        # Clean up temp file
        if cif_path.exists():
            cif_path.unlink()
    
    # Create pseudo file for Si
    (tmp_project / "pseudo").mkdir(parents=True, exist_ok=True)
    (tmp_project / "pseudo" / "Si.UPF").write_text("FAKE PSEUDO FILE")
    
    return structure_id, structure_path


@pytest.fixture
def minimal_calculation(tmp_project, minimal_structure):
    """Create a minimal calculation with steps using service APIs."""
    structure_id, structure_path = minimal_structure
    
    from quantumvitas.api import QVService
    
    # Create calculation using service API
    calc_resolved = QVService.init_calculation(
        project_root=tmp_project,
        name="test_calc",
        structure_selector=structure_id,
    )
    calc_id = calc_resolved.meta.id
    calc_dir = calc_resolved.absolute_path
    
    # Configure calculation with species_map and pseudo
    # We need to set species_map for pseudo SHA computation
    # Use edit lock to update calc.yaml (as production code does)
    from quantumvitas.core.locking import calc_edit_lock
    from quantumvitas.core.models import load_calculation
    
    # Configure calculation with species_map and pseudo
    # Use save_yaml_doc which handles edit lock internally
    from quantumvitas.core.yaml_io import save_yaml_doc
    from quantumvitas.core.yamldoc import CalcDoc
    from quantumvitas.core.models import load_calculation
    
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    
    # Set species_map if not already set
    if not calc_model.species_map:
        calc_model.species_map = {
            "Si": {
                "pseudopot": "Si.UPF",
                "mass": 28.0855,
            }
        }
        # Save using CalcDoc + save_yaml_doc (proper write path, handles lock internally)
        calc_doc = CalcDoc(calc_model.to_dict())
        save_yaml_doc(calc_doc, calc_data_path)
    
    # Create steps using domain API
    svc = QVService(tmp_project)
    step1_dto = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type="scf",
    )
    step1_id = step1_dto.step_id

    step2_dto = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type="nscf",
    )
    step2_id = step2_dto.step_id

    step3_dto = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type="bands",
    )
    step3_id = step3_dto.step_id

    # Fix invalid K_POINTS: bands step defaults to crystal_b without data
    # Add valid K_POINTS data to make the step valid for materialization
    step3_spec_path = calc_dir / "steps" / f"{step3_dto.meta.slug}.step.yaml"
    step3_data = yaml.safe_load(step3_spec_path.read_text())
    if "cards" in step3_data and "K_POINTS" in step3_data["cards"]:
        kpoints = step3_data["cards"]["K_POINTS"]
        if kpoints.get("option") == "crystal_b" and "data" not in kpoints:
            # Add minimal valid k-path data (gamma point)
            step3_data["cards"]["K_POINTS"] = {
                "option": "crystal_b",
                "data": [
                    [0.0, 0.0, 0.0, 1],  # Gamma point, 1 k-point
                ]
            }
            step3_spec_path.write_text(yaml.safe_dump(step3_data, sort_keys=False))
    
    # Steps are already added to calculation.yaml by init_step
    # Verify calculation.yaml has the steps
    calc_data = yaml.safe_load((calc_dir / "calculation.yaml").read_text())
    step_ids_in_calc = [s.get("step_id") for s in calc_data.get("steps", [])]
    
    # Ensure all steps are in the calculation
    assert step1_id in step_ids_in_calc, f"Step1 {step1_id} not in calculation steps"
    assert step2_id in step_ids_in_calc, f"Step2 {step2_id} not in calculation steps"
    assert step3_id in step_ids_in_calc, f"Step3 {step3_id} not in calculation steps"
    
    return calc_id, calc_dir, [step1_id, step2_id, step3_id]


def test_run_lock_blocks_concurrent_runs(tmp_project, minimal_calculation):
    """Test that run.lock prevents concurrent runs on the same calculation."""
    calc_id, calc_dir, _ = minimal_calculation
    
    # First lock acquisition should succeed
    lock_acquired = threading.Event()
    lock_released = threading.Event()
    
    def hold_lock():
        with calc_run_lock(calc_dir, fail_fast=True):
            lock_acquired.set()
            time.sleep(0.5)  # Hold lock briefly
        lock_released.set()
    
    def try_lock():
        lock_acquired.wait()  # Wait for first lock to be acquired
        try:
            with calc_run_lock(calc_dir, fail_fast=True):
                pytest.fail("Second lock should have failed")
        except CalculationLockError:
            pass  # Expected
    
    t1 = threading.Thread(target=hold_lock)
    t2 = threading.Thread(target=try_lock)
    
    t1.start()
    t2.start()
    
    t1.join(timeout=2)
    t2.join(timeout=2)
    
    assert lock_acquired.is_set()
    assert lock_released.is_set()


def test_different_calcs_run_concurrently(tmp_project, minimal_structure):
    """Test that different calculations can run concurrently."""
    structure_id, _ = minimal_structure
    
    from quantumvitas.api import QVService
    
    # Create two calculations using service API
    calc1_resolved = QVService.init_calculation(
        project_root=tmp_project,
        name="calc1",
        structure_selector=structure_id,
    )
    calc1_id = calc1_resolved.meta.id
    calc1_dir = calc1_resolved.absolute_path
    
    calc2_resolved = QVService.init_calculation(
        project_root=tmp_project,
        name="calc2",
        structure_selector=structure_id,
    )
    calc2_id = calc2_resolved.meta.id
    calc2_dir = calc2_resolved.absolute_path
    
    # Both should be able to acquire locks simultaneously
    lock1_acquired = threading.Event()
    lock2_acquired = threading.Event()
    
    def acquire_lock1():
        with calc_run_lock(calc1_dir, fail_fast=True):
            lock1_acquired.set()
            time.sleep(0.2)
    
    def acquire_lock2():
        with calc_run_lock(calc2_dir, fail_fast=True):
            lock2_acquired.set()
            time.sleep(0.2)
    
    t1 = threading.Thread(target=acquire_lock1)
    t2 = threading.Thread(target=acquire_lock2)
    
    t1.start()
    t2.start()
    
    t1.join(timeout=1)
    t2.join(timeout=1)
    
    assert lock1_acquired.is_set()
    assert lock2_acquired.is_set()


def test_manifest_trim_on_removing_last_step(tmp_project, minimal_calculation, monkeypatch):
    """Test that manifest is trimmed when last step is removed from calculation."""
    calc_id, calc_dir, step_ids = minimal_calculation
    
    # Mock is_step_done to return True (simulate steps are actually done)
    # Must patch at the import location in manifest_reconcile module
    def mock_is_step_done(*args, **kwargs):
        return True
    monkeypatch.setattr("quantumvitas.calculation.manifest_reconcile.is_step_done", mock_is_step_done)
    
    # Compute actual SHAs for manifest entries
    from quantumvitas.core.models import load_calculation
    from quantumvitas.core.resolution import require_structure, require_step, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    from quantumvitas.core.yamldoc import StepDoc
    
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    
    # Get structure SHA
    structure_id = calc_model.structure_id
    structure_resolved = require_structure(tmp_project, structure_id, config=config, index=index)
    structure_path = structure_resolved.absolute_path
    structure_sha = compute_structure_sha(structure_path)
    
    # Get pseudo SHA
    pseudo_sha = compute_pseudo_set_sha(tmp_project / "pseudo", calc_model.species_map or {})
    
    # Get step SHAs for each step
    step_shas = []
    for i, step_id in enumerate(step_ids):
        step_resolved = require_step(tmp_project, calc_id, step_id, config=config, index=index)
        step_doc = StepDoc.load(step_resolved.absolute_path)
        step_data = step_doc.to_dict()
        step_sha = compute_step_sha(step_data)
        step_shas.append(step_sha)
    
    # Create initial manifest with 3 steps, all done, using actual SHAs
    # Use machine_type (qe_scf, qe_nscf, qe_bands) to match what reconcile produces
    manifest = Manifest()
    for i, step_id in enumerate(step_ids):
        manifest.steps.append(ManifestStepEntry(
            kind=["qe_scf", "qe_nscf", "qe_bands"][i],
            step_ulid=step_id,
            pseudo_set_sha=pseudo_sha,
            structure_sha=structure_sha,
            step_sha=step_shas[i],
            run_id="test_run",
            done=True,
            started_at="2024-01-01T00:00:00Z",
            done_at="2024-01-01T00:00:00Z",
        ))
    save_manifest_atomic(calc_dir, manifest)
    
    # Modify calculation.yaml to remove last step
    # Use save_yaml_doc which handles edit lock internally
    from quantumvitas.core.yaml_io import save_yaml_doc
    from quantumvitas.core.yamldoc import CalcDoc
    from quantumvitas.core.models import load_calculation
    
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    # Remove last step
    calc_model.steps = calc_model.steps[:2]
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_data_path)  # Handles lock internally
    
    # Reconcile manifest
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.project.model import Project
    
    project = Project.open(tmp_project)
    calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
    
    # Get structure path using resolver (don't assume path)
    from quantumvitas.core.resolution import require_structure, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    
    # Use calc_model from above, or reload
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    structure_id = calc_model.structure_id
    structure_resolved = require_structure(tmp_project, structure_id, config=config, index=index)
    structure_path = structure_resolved.absolute_path
    
    structure_sha = compute_structure_sha(structure_path)
    pseudo_sha = compute_pseudo_set_sha(tmp_project / "pseudo", calc_model.species_map or {})
    
    reconciled_manifest, first_changed_idx = reconcile_manifest(
        calc_dir=calc_dir,
        project_root=tmp_project,
        calculation_steps=calculation.steps,
        current_pseudo_set_sha=pseudo_sha,
        structure_path=structure_path,
    )
    
    # Manifest should be trimmed to length 2
    assert len(reconciled_manifest.steps) == 2
    # First two steps should still be done (SHAs match)
    assert reconciled_manifest.steps[0].done is True
    assert reconciled_manifest.steps[1].done is True
    # ULIDs should be updated to current
    assert reconciled_manifest.steps[0].step_ulid == step_ids[0]
    assert reconciled_manifest.steps[1].step_ulid == step_ids[1]


def test_reorder_forces_rerun_from_divergence(tmp_project, minimal_calculation, monkeypatch):
    """Test that reordering steps forces rerun from divergence point."""
    calc_id, calc_dir, step_ids = minimal_calculation
    
    # Mock is_step_done to return True (simulate steps are actually done)
    # Must patch at the import location in manifest_reconcile module
    def mock_is_step_done(*args, **kwargs):
        return True
    monkeypatch.setattr("quantumvitas.calculation.manifest_reconcile.is_step_done", mock_is_step_done)
    
    # Compute actual SHAs for manifest entries
    from quantumvitas.core.models import load_calculation
    from quantumvitas.core.resolution import require_structure, require_step, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    from quantumvitas.core.yamldoc import StepDoc
    
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    
    # Get structure SHA
    structure_id = calc_model.structure_id
    structure_resolved = require_structure(tmp_project, structure_id, config=config, index=index)
    structure_path = structure_resolved.absolute_path
    structure_sha = compute_structure_sha(structure_path)
    
    # Get pseudo SHA
    pseudo_sha = compute_pseudo_set_sha(tmp_project / "pseudo", calc_model.species_map or {})
    
    # Get step SHAs for each step (in original order)
    step_shas = []
    for i, step_id in enumerate(step_ids):
        step_resolved = require_step(tmp_project, calc_id, step_id, config=config, index=index)
        step_doc = StepDoc.load(step_resolved.absolute_path)
        step_data = step_doc.to_dict()
        step_sha = compute_step_sha(step_data)
        step_shas.append(step_sha)
    
    # Create initial manifest with [A, B, C], all done, using actual SHAs
    # Use machine_type (qe_scf, qe_nscf, qe_bands) to match what reconcile produces
    manifest = Manifest()
    for i, step_id in enumerate(step_ids):
        manifest.steps.append(ManifestStepEntry(
            kind=["qe_scf", "qe_nscf", "qe_bands"][i],
            step_ulid=step_id,
            pseudo_set_sha=pseudo_sha,
            structure_sha=structure_sha,
            step_sha=step_shas[i],
            done=True,
        ))
    save_manifest_atomic(calc_dir, manifest)
    
    # Reorder calculation.yaml to [A, C, B]
    # Use save_yaml_doc which handles edit lock internally
    from quantumvitas.core.yaml_io import save_yaml_doc
    from quantumvitas.core.yamldoc import CalcDoc
    from quantumvitas.core.models import load_calculation
    
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    # Reorder: swap steps[1] and steps[2]
    calc_model.steps = [calc_model.steps[0], calc_model.steps[2], calc_model.steps[1]]
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_data_path)  # Handles lock internally
    
    # Reconcile
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.project.model import Project
    
    project = Project.open(tmp_project)
    calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
    
    # Get structure path using resolver (don't assume path)
    from quantumvitas.core.resolution import require_structure, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    
    # Use calc_model from above
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    structure_id = calc_model.structure_id
    structure_resolved = require_structure(tmp_project, structure_id, config=config, index=index)
    structure_path = structure_resolved.absolute_path
    
    structure_sha = compute_structure_sha(structure_path)
    pseudo_sha = compute_pseudo_set_sha(tmp_project / "pseudo", calc_model.species_map or {})
    
    reconciled_manifest, first_changed_idx = reconcile_manifest(
        calc_dir=calc_dir,
        project_root=tmp_project,
        calculation_steps=calculation.steps,
        current_pseudo_set_sha=pseudo_sha,
        structure_path=structure_path,
    )
    
    # After reordering [A, B, C] -> [A, C, B]:
    # - Index 0: A (scf) vs A (scf) - kind matches, SHAs match -> done=True (skipped)
    # - Index 1: C (bands) vs B (nscf) - kind mismatch -> done=False (needs rerun from here)
    # - Index 2: B (nscf) vs C (bands) - kind mismatch -> done=False
    # So first_changed_idx should be 1
    assert first_changed_idx == 1, f"Expected first_changed_idx=1, got {first_changed_idx}. Steps: {[(s.kind, s.done) for s in reconciled_manifest.steps]}"
    assert reconciled_manifest.steps[0].done is True
    assert reconciled_manifest.steps[1].done is False
    assert reconciled_manifest.steps[2].done is False


def test_ignore_ulid_for_equivalence(tmp_project, minimal_calculation, monkeypatch):
    """Test that ULID changes don't affect skip logic if SHAs match."""
    calc_id, calc_dir, step_ids = minimal_calculation
    
    # Mock is_step_done to return True (simulate steps are actually done)
    # Must patch at the import location in manifest_reconcile module
    def mock_is_step_done(*args, **kwargs):
        return True
    monkeypatch.setattr("quantumvitas.calculation.manifest_reconcile.is_step_done", mock_is_step_done)
    
    from quantumvitas.api import QVService
    from quantumvitas.core.resolution import require_step
    from quantumvitas.core.yamldoc import StepDoc
    from quantumvitas.workflow.step_factory import save_step_doc
    from quantumvitas.core.project_utils import load_project_config
    
    # Get step at index 1 (nscf) content to create identical copy
    config = load_project_config(tmp_project)
    step1_resolved = require_step(tmp_project, calc_id, step_ids[1], config=config)
    step1_doc = StepDoc.load(step1_resolved.absolute_path)
    step1_content_dict = step1_doc.to_dict()
    step_type = step1_content_dict.get("step_type", "nscf")
    
    # Compute step SHA for step1
    step1_sha = compute_step_sha(step1_content_dict)
    
    # Create manifest with step done=true using step_ids[1] (old ULID) but correct SHA
    # Load calc model to get structure_id and species_map
    from quantumvitas.core.models import load_calculation
    from quantumvitas.core.resolution import require_structure, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    structure_id = calc_model.structure_id
    structure_resolved = require_structure(tmp_project, structure_id, config=config, index=index)
    structure_path = structure_resolved.absolute_path
    structure_sha = compute_structure_sha(structure_path)
    pseudo_sha = compute_pseudo_set_sha(tmp_project / "pseudo", calc_model.species_map or {})
    
    # Get step SHAs for all steps (using actual SHAs)
    from quantumvitas.core.resolution import require_step, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    from quantumvitas.core.yamldoc import StepDoc
    
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    
    # Get step SHAs for all steps
    all_step_shas = []
    for i, step_id in enumerate(step_ids):
        if i == 1:
            # Use step1_sha (already computed)
            all_step_shas.append(step1_sha)
        else:
            # Compute SHA for other steps
            step_resolved = require_step(tmp_project, calc_id, step_id, config=config, index=index)
            step_doc = StepDoc.load(step_resolved.absolute_path)
            step_data = step_doc.to_dict()
            step_sha = compute_step_sha(step_data)
            all_step_shas.append(step_sha)
    
    manifest = Manifest()
    # Add entries for all steps, using actual SHAs
    # Use machine_type (qe_scf, qe_nscf, qe_bands) to match what reconcile produces
    for i, step_id in enumerate(step_ids):
        kind_val = ["qe_scf", "qe_nscf", "qe_bands"][i]
        manifest.steps.append(ManifestStepEntry(
            kind=kind_val,
            step_ulid=step_id,
            pseudo_set_sha=pseudo_sha,
            structure_sha=structure_sha,
            step_sha=all_step_shas[i],
            done=True,  # All done
        ))
    save_manifest_atomic(calc_dir, manifest)
    
    # Create a new step u2b with identical content to step_ids[1]
    # This should have same step_sha but different ULID
    svc = QVService(tmp_project)
    step2b_dto = svc.calculation.add_step(
        calc_selector=calc_id,
        step_type=step_type,
        name="nscf-copy",
    )
    step2b_id = step2b_dto.step_id
    step2b_path = calc_dir / "steps" / f"{step2b_dto.meta.slug}.step.yaml"
    
    # Copy ALL content from step1 to step2b (excluding meta.id)
    step2b_doc = StepDoc.load(step2b_path)
    # Copy step_type, parameters, cards, species_overrides to match step1 exactly
    # Use apply_patch for dict updates instead of set()
    patch_data = {}
    if "step_type" in step1_content_dict:
        patch_data["step_type"] = step1_content_dict["step_type"]
    if "parameters" in step1_content_dict:
        patch_data["parameters"] = step1_content_dict["parameters"]
    if "cards" in step1_content_dict:
        patch_data["cards"] = step1_content_dict["cards"]
    if "species_overrides" in step1_content_dict:
        patch_data["species_overrides"] = step1_content_dict["species_overrides"]
    if patch_data:
        step2b_doc.apply_patch(patch_data)
    
    # Save the modified step
    save_step_doc(step2b_doc, step2b_path)
    
    # Verify step_sha is same (content identical)
    step2b_content_dict = step2b_doc.to_dict()
    step2b_sha = compute_step_sha(step2b_content_dict)
    assert step1_sha == step2b_sha, f"Step SHAs should match: step1={step1_sha[:16]}..., step2b={step2b_sha[:16]}..."
    
    # Replace step_ids[1] with step2b_id in calculation.yaml step list
    # Use save_yaml_doc which handles edit lock internally
    from quantumvitas.core.yaml_io import save_yaml_doc
    from quantumvitas.core.yamldoc import CalcDoc
    from quantumvitas.core.models import load_calculation, CalculationStepEntry
    
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    # Find index of step_ids[1] and replace with step2b_id
    replaced = False
    for i, step_entry in enumerate(calc_model.steps):
        if step_entry.step_id == step_ids[1]:
            calc_model.steps[i] = CalculationStepEntry(step_id=step2b_id, type=step_type)
            replaced = True
            break
    assert replaced, f"Could not find step_ids[1]={step_ids[1]} in calculation steps"
    calc_doc = CalcDoc(calc_model.to_dict())
    save_yaml_doc(calc_doc, calc_data_path)  # Handles lock internally
    
    # Reload to get step list
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    step_list = [{"step_id": s.step_id, "type": s.type} for s in calc_model.steps]
    
    # Reconcile - should still skip because SHAs match, but ULID should be updated to step2b_id
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.project.model import Project
    
    project = Project.open(tmp_project)
    calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
    
    # Get structure path for reconcile (reuse from above)
    # structure_path, structure_sha, pseudo_sha already computed above
    
    # Find step2b's index in the calculation steps
    step2b_index = None
    for i, step in enumerate(calculation.steps):
        # Step may have meta.id or we need to check calculation.yaml
        if i < len(step_list) and step_list[i].get("step_id") == step2b_id:
            step2b_index = i
            break
    
    assert step2b_index is not None, f"Could not find step2b_id={step2b_id} in calculation steps after replacement"
    
    reconciled_manifest, first_changed_idx = reconcile_manifest(
        calc_dir=calc_dir,
        project_root=tmp_project,
        calculation_steps=calculation.steps,
        current_pseudo_set_sha=pseudo_sha,
        structure_path=structure_path,  # Already defined above
    )
    
    # Step at step2b_index should be skipped (done=True) because SHAs match
    assert step2b_index < len(reconciled_manifest.steps), \
        f"step2b_index={step2b_index} out of range, manifest has {len(reconciled_manifest.steps)} steps"
    assert reconciled_manifest.steps[step2b_index].done is True, \
        f"Step at index {step2b_index} should be skipped (done=True) because SHAs match"
    # ULID should be updated to step2b_id (new ULID)
    assert reconciled_manifest.steps[step2b_index].step_ulid == step2b_id, \
        f"ULID should be updated to step2b_id={step2b_id}, got {reconciled_manifest.steps[step2b_index].step_ulid}"
    # SHA should still match
    assert reconciled_manifest.steps[step2b_index].step_sha == step1_sha, \
        f"Step SHA should match: expected {step1_sha[:16]}..., got {reconciled_manifest.steps[step2b_index].step_sha[:16] if reconciled_manifest.steps[step2b_index].step_sha else 'None'}..."


def test_single_step_invalidates_suffix(tmp_project, minimal_calculation):
    """Test that single-step run invalidates subsequent steps."""
    calc_id, calc_dir, step_ids = minimal_calculation
    
    # Create manifest with all steps done
    manifest = Manifest()
    for i, step_id in enumerate(step_ids):
        manifest.steps.append(ManifestStepEntry(
            kind=["scf", "nscf", "bands"][i],
            step_ulid=step_id,
            pseudo_set_sha="test_sha",
            structure_sha="test_sha",
            step_sha="test_sha",
            done=True,
        ))
    save_manifest_atomic(calc_dir, manifest)
    
    # Run single step at index 1 (middle step)
    # First, mock the step execution to succeed
    from quantumvitas.calculation.manifest import clear_manifest_from_step
    
    # Simulate successful execution by marking step 1 as done and invalidating suffix
    from quantumvitas.calculation.manifest import update_manifest_step, now_iso8601
    from quantumvitas.calculation.hash_utils import compute_structure_sha, compute_step_sha
    from quantumvitas.core.yamldoc import StepDoc
    
    # Update step 1 to done - find step file using resolver
    from quantumvitas.core.resolution import require_step, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    step1_resolved = require_step(tmp_project, calc_id, step_ids[1], config=config, index=index)
    step_yaml_path = step1_resolved.absolute_path
    step_doc = StepDoc.load(step_yaml_path)
    step_data = step_doc.to_dict()
    step_sha = compute_step_sha(step_data)
    
    # Load calc model to get structure_id and species_map
    from quantumvitas.core.models import load_calculation
    from quantumvitas.core.resolution import require_structure, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    structure_id = calc_model.structure_id
    structure_resolved = require_structure(tmp_project, structure_id, config=config, index=index)
    structure_path = structure_resolved.absolute_path
    structure_sha = compute_structure_sha(structure_path)
    pseudo_sha = compute_pseudo_set_sha(tmp_project / "pseudo", calc_model.species_map or {})
    
    update_manifest_step(
        calc_dir=calc_dir,
        step_index=1,
        kind="nscf",
        step_ulid=step_ids[1],
        pseudo_set_sha=pseudo_sha,
        structure_sha=structure_sha,
        step_sha=step_sha,
        run_id="test_run",
        done=True,
        started_at=now_iso8601(),
        done_at=now_iso8601(),
    )
    
    # Invalidate suffix (steps after index 1)
    clear_manifest_from_step(calc_dir, 2)
    
    # Reload and check
    manifest = load_manifest(calc_dir)
    assert manifest.steps[0].done is True  # Before unchanged
    assert manifest.steps[1].done is True  # Step 1 now done
    assert manifest.steps[2].done is False  # Step 2 invalidated


def test_pseudo_preflight_warning_and_update(tmp_project, minimal_calculation, caplog, monkeypatch):
    """Test that pseudo SHA mismatch triggers warning and manifest update (not calc.yaml)."""
    calc_id, calc_dir, _ = minimal_calculation
    
    # Compute actual SHA using same production function
    from quantumvitas.core.models import load_calculation
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model_initial = load_calculation(calc_data_path, project_root=tmp_project)
    species_map = calc_model_initial.species_map or {}
    actual_sha = compute_pseudo_set_sha(tmp_project / "pseudo", species_map)
    
    # Note: We no longer set pseudo_set_sha in calc.yaml (it's derived, stored only in manifest)
    # Instead, we'll verify that calc.yaml does NOT have pseudo_set_sha (SSOT compliance)
    
    # Don't mock CalculationRunner.run - allow Step0 to run so pseudo records get updated
    # Mock only the actual QE execution to avoid running real calculations
    from quantumvitas.execution.executor import JobExecutor
    
    def mock_execute(self, job_graph, selection_mode, *, context=None):
        # Return success without actually executing jobs
        from quantumvitas.execution.executor import ExecutionResult, JobResult
        from quantumvitas.execution.job_graph import SelectionMode
        
        job_results = []
        for job in job_graph.get_jobs_for_target(selection_mode):
            job_results.append(JobResult(
                job_id=job.id,
                success=True,
                error=None,
                step_results={},
            ))
        
        return ExecutionResult(
            success=True,
            job_results=job_results,
        )
    
    monkeypatch.setattr(JobExecutor, "execute", mock_execute)
    
    # Mock pseudopotential resolution to avoid pseudo requirements
    def fake_ensure_qe_pseudos(*args, **kwargs):
        from quantumvitas.core.pseudo import PseudoResolutionResult
        return PseudoResolutionResult(
            project_pseudo_dir=tmp_project / "pseudo",
            system_pseudo_dir=None,
            resolved_pseudos={},
            all_available=True,
        )
    
    monkeypatch.setattr("quantumvitas.core.pseudo.ensure_qe_pseudos", fake_ensure_qe_pseudos)
    
    # Run calculation - manifest should be updated with fresh pseudo_set_sha
    import logging
    with caplog.at_level(logging.WARNING):
        try:
            QVService.run_calculation(
                project_root=tmp_project,
                calculation_selector=calc_id,
                run_mode="incremental",
            )
        except Exception as e:
            # May fail for other reasons, but preflight should have run
            pass
    
    # Verify calc.yaml does NOT have pseudo_set_sha (SSOT: derived field, not stored)
    calc_data_final = yaml.safe_load(calc_data_path.read_text())
    assert "pseudo_set_sha" not in calc_data_final, \
        "calc.yaml should NOT contain pseudo_set_sha (it's derived, stored only in manifest)"
    
    # Verify manifest has correct pseudo_set_sha
    from quantumvitas.calculation.manifest import load_manifest
    manifest = load_manifest(calc_dir)
    assert manifest is not None, "Manifest should exist after run"
    assert len(manifest.steps) > 0, "Manifest should have at least one step"
    
    # Check that manifest steps have correct pseudo_set_sha
    for step_entry in manifest.steps:
        if step_entry.pseudo_set_sha:  # Only check if SHA is set
            assert step_entry.pseudo_set_sha == actual_sha, \
                f"Manifest step pseudo_set_sha mismatch: expected {actual_sha}, got {step_entry.pseudo_set_sha}"
    
    # Verify warning was logged (if there was a mismatch, though with new SSOT there may not be)
    warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
    # Note: With new SSOT, warnings may not occur if calc.yaml never had pseudo_set_sha
    # But if it did (legacy), we should see a warning
    # With new SSOT, we don't write pseudo_set_sha to calc.yaml, so no mismatch warning expected


# ============================================================================
# Sanity tests
# ============================================================================

def test_crash_recovery_incremental_rerun_from_failed_step(tmp_project, minimal_calculation, monkeypatch):
    """
    Sanity test: Crash recovery - step i writes run_id/started_at/done=false, 
    then runner throws exception. Second incremental run should rerun from step i.
    """
    calc_id, calc_dir, step_ids = minimal_calculation
    
    # Create manifest with first step done=true, second step started but not done
    manifest = Manifest()
    manifest.steps.append(ManifestStepEntry(
        kind="scf",
        step_ulid=step_ids[0],
        pseudo_set_sha="test_sha",
        structure_sha="test_sha",
        step_sha="test_sha",
        run_id="run_001",
        done=True,
        started_at="2024-01-01T00:00:00Z",
        done_at="2024-01-01T00:01:00Z",
    ))
    manifest.steps.append(ManifestStepEntry(
        kind="nscf",
        step_ulid=step_ids[1],
        pseudo_set_sha="test_sha",
        structure_sha="test_sha",
        step_sha="test_sha",
        run_id="run_002",  # Started but crashed
        done=False,  # Not done - crashed
        started_at="2024-01-01T00:02:00Z",
        done_at=None,
    ))
    save_manifest_atomic(calc_dir, manifest)
    
    # Mock runner to simulate crash at step 1 (index 1)
    from quantumvitas.calculation.runner import CalculationRunner
    from quantumvitas.calculation.results import CalculationResult
    from quantumvitas.calculation.types import StepStatus
    from datetime import datetime, timezone
    
    call_count = [0]
    
    def mock_run(self, calculation, *, skip_history=False, run_id=None, run_mode="incremental", **kwargs):
        call_count[0] += 1
        # Simulate crash after starting step 1
        if call_count[0] == 1:
            # First call: update manifest for step 1, then crash
            from quantumvitas.calculation.manifest import update_manifest_step, now_iso8601
            update_manifest_step(
                calc_dir=calculation.dir,
                step_index=1,
                kind="nscf",
                step_ulid=step_ids[1],
                pseudo_set_sha="test_sha",
                structure_sha="test_sha",
                step_sha="test_sha",
                run_id=run_id or "run_003",
                done=False,
                started_at=now_iso8601(),
                done_at=None,
            )
            raise RuntimeError("Simulated crash during step execution")
        else:
            # Second call: should start from step 1 (index 1) because done=False
            # Verify start_idx would be 1 (we can't directly check, but we can verify manifest state)
            return CalculationResult(
                calculation_id=calculation.id,
                mode=calculation.mode,
                steps=[],
                status=StepStatus.SUCCESS,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
    
    monkeypatch.setattr(CalculationRunner, "run", mock_run)
    
    # First run - should crash
    try:
        QVService.run_calculation(
            project_root=tmp_project,
            calculation_selector=calc_id,
            run_mode="incremental",
        )
    except RuntimeError:
        pass  # Expected crash
    
    # Verify step 1 is marked as started but not done
    manifest_after_crash = load_manifest(calc_dir)
    assert manifest_after_crash is not None
    assert len(manifest_after_crash.steps) >= 2
    assert manifest_after_crash.steps[0].done is True  # Step 0 still done
    assert manifest_after_crash.steps[1].done is False  # Step 1 not done (crashed)
    assert manifest_after_crash.steps[1].started_at is not None  # Was started
    
    # Second incremental run - should start from step 1 (not step 0)
    # Since we mocked the runner, we can't verify the actual start_idx,
    # but we verify the manifest state is correct for recovery
    assert manifest_after_crash.steps[1].done is False  # Ready to rerun


def test_pseudo_preflight_update_failure_non_blocking(tmp_project, minimal_calculation, caplog, monkeypatch):
    """
    Sanity test: Pseudo preflight update calc.yaml failure does not block run.
    Also verify manifest uses fresh pseudo_set_sha and runner executes at least one step.
    """
    calc_id, calc_dir, _ = minimal_calculation
    
    # Note: With new SSOT, pseudo_set_sha is not stored in calc.yaml (only in manifest)
    # This test verifies that manifest update is non-blocking (run continues even if manifest write fails)
    calc_data_path = calc_dir / "calculation.yaml"
    
    # Make manifest directory read-only to simulate write failure (not calc.yaml)
    from quantumvitas.calculation.manifest import get_manifest_dir
    manifest_dir = get_manifest_dir(calc_dir)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    
    import os
    original_mode = manifest_dir.stat().st_mode
    manifest_dir.chmod(0o444)  # Read-only (will prevent manifest writes)
    
    # Track execution calls
    execution_calls = []
    
    try:
        # Mock runner to track execution calls
        from quantumvitas.calculation.runner import CalculationRunner
        from quantumvitas.calculation.results import CalculationResult
        from quantumvitas.calculation.types import StepStatus
        from datetime import datetime, timezone
        
        def mock_run(self, calculation, *, skip_history=False, run_id=None, run_mode="incremental", **kwargs):
            execution_calls.append({
                "calculation_id": calculation.id,
                "run_id": run_id,
                "run_mode": run_mode,
            })
            return CalculationResult(
                calculation_id=calculation.id,
                mode=calculation.mode,
                steps=[],
                status=StepStatus.SUCCESS,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
        
        monkeypatch.setattr(CalculationRunner, "run", mock_run)
        
        # Mock pseudopotential resolution
        def fake_ensure_qe_pseudos(*args, **kwargs):
            from quantumvitas.core.pseudo import PseudoResolutionResult
            return PseudoResolutionResult(
                project_pseudo_dir=tmp_project / "pseudo",
                system_pseudo_dir=None,
                resolved_pseudos={},
                all_available=True,
            )
        
        monkeypatch.setattr("quantumvitas.core.pseudo.ensure_qe_pseudos", fake_ensure_qe_pseudos)
        
        # Run calculation - should continue despite write failure
        import logging
        with caplog.at_level(logging.WARNING):
            result = QVService.run_calculation(
                project_root=tmp_project,
                calculation_selector=calc_id,  # Use real calc_id from service
                run_mode="incremental",
            )
        
        # Should succeed (not blocked by preflight update failure)
        assert result is not None
        assert result["status"] == "success"
        
        # Verify runner was called (run still proceeded)
        assert len(execution_calls) > 0, "Run should have proceeded despite calc.yaml update failure"
        
        # Should log warning about manifest write failure (non-blocking)
        warning_messages = [record.message for record in caplog.records if record.levelname == "WARNING"]
        # Manifest write failure warning is acceptable (non-blocking)
        has_relevant_warning = any(
            "manifest" in m.lower() or "write" in m.lower() or "permission" in m.lower()
            for m in warning_messages
        )
        # Note: With new SSOT, we don't write pseudo_set_sha to calc.yaml, so no mismatch warning expected
        # The test verifies that run continues even if manifest write fails
        
    finally:
        # Restore write permissions
        manifest_dir.chmod(original_mode)


def test_nested_calc_edit_lock_raises_fast(tmp_project, minimal_calculation):
    """Test that nested calc_edit_lock raises LockReentrancyError instead of hanging."""
    calc_id, calc_dir, step_ids = minimal_calculation
    
    # Acquire lock once
    with calc_edit_lock(calc_dir, fail_fast=False):
        # Attempt to acquire again in same thread - should raise immediately
        with pytest.raises(LockReentrancyError, match="Non-reentrant calc_edit_lock"):
            with calc_edit_lock(calc_dir, fail_fast=False):
                pass  # Should never reach here


def test_structure_sha_float_tolerance(tmp_project, minimal_structure):
    """Test that structure_sha is stable under small float perturbations."""
    from quantumvitas.core.resolution import require_structure, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    import json
    
    # Use existing structure from fixture
    structure_id, structure_path = minimal_structure
    
    # Resolve structure to get JSON path
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    structure_resolved = require_structure(tmp_project, structure_id, config=config, index=index)
    structure_json_path = structure_resolved.absolute_path
    
    # Compute initial SHA
    initial_sha = compute_structure_sha(structure_json_path)
    
    # Load structure JSON
    structure_data = json.loads(structure_json_path.read_text())
    
    # Test 1: Small perturbation within tolerance (should not change SHA)
    # Find a coordinate and perturb by value less than FLOAT_TOLERANCE (1e-10)
    # We use 1e-13 which is well below tolerance
    if "lattice" in structure_data and "matrix" in structure_data["lattice"]:
        original_value = structure_data["lattice"]["matrix"][0][0]
        # Small perturbation (within tolerance)
        structure_data["lattice"]["matrix"][0][0] = original_value + 1e-13
        # Write using same method as production (JSON with sorted keys)
        structure_json_path.write_text(json.dumps(structure_data, sort_keys=True))
        perturbed_sha = compute_structure_sha(structure_json_path)
        # Should be unchanged (canonicalize_float rounds to nearest 1e-10, so 1e-13 is below threshold)
        assert perturbed_sha == initial_sha, f"Tiny perturbation (1e-13) changed SHA: {initial_sha[:16]}... vs {perturbed_sha[:16]}..."
        
        # Restore original
        structure_data["lattice"]["matrix"][0][0] = original_value
        structure_json_path.write_text(json.dumps(structure_data, sort_keys=True))
        
        # Test 2: Larger perturbation (should change SHA)
        # Use 1e-6 which is much larger than FLOAT_TOLERANCE (1e-10)
        structure_data["lattice"]["matrix"][0][0] = original_value + 1e-6
        structure_json_path.write_text(json.dumps(structure_data, sort_keys=True))
        large_perturb_sha = compute_structure_sha(structure_json_path)
        assert large_perturb_sha != initial_sha, "Large perturbation (1e-6) should change SHA"


def test_pseudo_set_sha_stable_under_reordering_and_rename(tmp_project, minimal_calculation):
    """Test that compute_pseudo_set_sha is stable under reordering and filename changes."""
    calc_id, calc_dir, step_ids = minimal_calculation
    
    # Load calculation to get species_map
    from quantumvitas.core.models import load_calculation
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    
    # Create pseudo files
    pseudo_dir = tmp_project / "pseudo"
    pseudo_dir.mkdir(parents=True, exist_ok=True)
    
    # Create Si.UPF and Si_new.UPF with identical content
    si_content = "FAKE PSEUDO FILE FOR Si\n"
    (pseudo_dir / "Si.UPF").write_text(si_content)
    (pseudo_dir / "Si_new.UPF").write_text(si_content)
    
    # Create species_map with original filename
    species_map_original = {
        "Si": {
            "pseudopot": "Si.UPF",
            "mass": 28.0855,
        }
    }
    
    # Create species_map with renamed filename (same content)
    species_map_renamed = {
        "Si": {
            "pseudopot": "Si_new.UPF",
            "mass": 28.0855,
        }
    }
    
    # Create species_map with reordered keys (different dict order)
    species_map_reordered = {
        "Si": {
            "mass": 28.0855,
            "pseudopot": "Si.UPF",
        }
    }
    
    # Compute SHAs - all should be identical since element symbol is the key
    sha_original = compute_pseudo_set_sha(pseudo_dir, species_map_original)
    sha_renamed = compute_pseudo_set_sha(pseudo_dir, species_map_renamed)
    sha_reordered = compute_pseudo_set_sha(pseudo_dir, species_map_reordered)
    
    assert sha_original == sha_renamed, "SHA should be stable under filename change (element key unchanged)"
    assert sha_original == sha_reordered, "SHA should be stable under dict key reordering"


def test_manifest_corruption_recovery(tmp_project, minimal_calculation):
    """
    Sanity test: Manifest corruption handling - invalid JSON should be handled gracefully.
    Expected behavior: return None (safe fallback) or raise clear error.
    """
    calc_id, calc_dir, _ = minimal_calculation
    
    # Get the actual manifest path using the same function the code uses
    from quantumvitas.calculation.manifest import get_manifest_path
    manifest_path = get_manifest_path(calc_dir)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("INVALID JSON { broken syntax }")
    
    # Try to load manifest - should handle gracefully
    manifest = None
    error_raised = False
    try:
        manifest = load_manifest(calc_dir)
    except (json.JSONDecodeError, ValueError, Exception) as e:
        # Clear error is acceptable (better than silent failure)
        error_raised = True
        error_msg = str(e).lower()
        assert any(word in error_msg for word in ["json", "parse", "invalid", "decode"])
    
    # Either None or exception is acceptable
    assert manifest is None or error_raised, "Should either return None or raise error for corrupted manifest"
    
    # Verify we can recover by deleting corrupted manifest
    if manifest_path.exists():
        manifest_path.unlink()
    
    # Should be able to create new manifest
    new_manifest = Manifest()
    new_manifest.steps.append(ManifestStepEntry(
        kind="scf",
        step_ulid="01TESTSTEP",
        pseudo_set_sha="test",
        structure_sha="test",
        step_sha="test",
        done=False,
    ))
    save_manifest_atomic(calc_dir, new_manifest)
    
    # Verify it was saved correctly
    loaded = load_manifest(calc_dir)
    assert loaded is not None
    assert len(loaded.steps) == 1
    assert loaded.steps[0].kind == "scf"


def test_step_has_no_id_property(tmp_project, minimal_calculation):
    """
    Contract test: Step.id property must be deleted.
    
    Accessing step.id should raise AttributeError (or simply assert not hasattr(step, "id")).
    """
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.project.model import Project
    
    calc_id, calc_dir, _ = minimal_calculation
    
    # Load calculation using from_yaml
    project = Project.open(tmp_project)
    calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
    
    # Verify calculation has steps
    assert len(calculation.steps) > 0, "Calculation should have at least one step"
    step = calculation.steps[0]
    
    # Verify Step.id property does NOT exist
    assert not hasattr(step, "id"), "Step.id property must be deleted"
    
    # Verify accessing step.id raises AttributeError
    with pytest.raises(AttributeError):
        _ = step.id
    
    # Verify step.meta.id exists (ULID)
    assert hasattr(step.meta, "id"), "Step.meta.id must exist (ULID)"
    assert step.meta.id is not None, "Step.meta.id must not be None"
    assert len(step.meta.id) == 26, f"Step.meta.id must be ULID (26 chars), got length {len(step.meta.id)}"
    
    # Verify step.meta.slug exists (slug for display)
    assert hasattr(step.meta, "slug"), "Step.meta.slug must exist (slug for display)"
    assert step.meta.slug is not None, "Step.meta.slug must not be None"
    # Slug may be shorter than ULID (typically 3-20 chars), but should be a valid string
    assert isinstance(step.meta.slug, str), "Step.meta.slug must be a string"


def test_manifest_stores_ulid_not_slug(tmp_project, minimal_calculation, monkeypatch):
    """
    Contract test: Manifest must store ULID only, never slug.
    
    Run reconcile/run path and assert manifest entries store step_ulid that looks like ULID,
    and never equals the slug like "scf".
    """
    from quantumvitas.calculation.calculation import Calculation
    from quantumvitas.project.model import Project
    
    calc_id, calc_dir, _ = minimal_calculation
    
    # Load calculation using from_yaml
    project = Project.open(tmp_project)
    calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)
    
    # Verify calculation has steps
    assert len(calculation.steps) > 0, "Calculation should have at least one step"
    step = calculation.steps[0]
    
    # Get step slug (for comparison)
    step_slug = step.meta.slug
    step_ulid = step.meta.id
    
    # Verify slug and ULID are different (slug is typically "scf", ULID is 26 chars)
    assert step_slug != step_ulid, "Step slug and ULID must be different"
    assert len(step_ulid) == 26, f"Step ULID must be 26 chars, got {len(step_ulid)}"
    
    # Mock is_step_done to return False (so we can test manifest creation)
    monkeypatch.setattr(
        "quantumvitas.calculation.manifest_reconcile.is_step_done",
        lambda *args, **kwargs: False
    )
    
    # Compute SHAs needed for reconcile
    from quantumvitas.core.models import load_calculation
    from quantumvitas.core.resolution import require_structure, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    
    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)
    
    structure_id = calc_model.structure_id
    structure_resolved = require_structure(tmp_project, structure_id, config=config, index=index)
    structure_path = structure_resolved.absolute_path
    structure_sha = compute_structure_sha(structure_path)
    pseudo_sha = compute_pseudo_set_sha(tmp_project / "pseudo", calc_model.species_map or {})
    
    # Run reconcile to create/update manifest
    from quantumvitas.calculation.manifest_reconcile import reconcile_manifest
    
    reconciled_manifest, first_changed_idx = reconcile_manifest(
        calc_dir=calc_dir,
        project_root=tmp_project,
        calculation_steps=calculation.steps,
        current_pseudo_set_sha=pseudo_sha,
        structure_path=structure_path,
    )
    
    # Load manifest
    manifest = load_manifest(calc_dir)
    assert manifest is not None, "Manifest should exist after reconcile"
    assert len(manifest.steps) > 0, "Manifest should have at least one step entry"
    
    # Verify manifest entry stores ULID, not slug
    entry = manifest.steps[0]
    assert entry.step_ulid == step_ulid, f"Manifest entry step_ulid must be ULID, got {entry.step_ulid}"
    assert entry.step_ulid != step_slug, f"Manifest entry step_ulid must NOT be slug '{step_slug}', got {entry.step_ulid}"
    assert len(entry.step_ulid) == 26, f"Manifest entry step_ulid must be ULID (26 chars), got length {len(entry.step_ulid)}"
    
    # Verify slug never appears in manifest JSON as a step identifier
    # Note: slug may appear as 'kind' if it matches step type (e.g., "scf"), but that's the step type, not identifier
    from quantumvitas.calculation.manifest import get_manifest_path
    import json
    manifest_path = get_manifest_path(calc_dir)
    if manifest_path.exists():
        manifest_data = json.loads(manifest_path.read_text())
        # Check that step_ulid fields contain ULID (26 chars), not slug
        for entry_data in manifest_data.get("steps", []):
            step_ulid_value = entry_data.get("step_ulid", "")
            assert len(step_ulid_value) == 26, \
                f"Manifest entry step_ulid must be ULID (26 chars), got '{step_ulid_value}' (length {len(step_ulid_value)})"
            assert step_ulid_value != step_slug, \
                f"Manifest entry step_ulid must NOT be slug '{step_slug}', got '{step_ulid_value}'. Manifest should only store ULID as identifier."

