"""
Integration tests for cascade invalidation in manifest reconciliation.

Tests that when an upstream step's SHA changes, all downstream steps are
invalidated (done=False) per Constitution §5.

Uses the same fixture pattern as test_incremental_run.py.
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from quantumvitas.calculation.manifest import (
    Manifest,
    ManifestStepEntry,
    load_manifest,
    save_manifest_atomic,
    clear_manifest_from_step,
)
from quantumvitas.calculation.manifest_reconcile import reconcile_manifest
from quantumvitas.calculation.hash_utils import (
    compute_pseudo_set_sha,
    compute_structure_sha,
    compute_step_sha,
)
from quantumvitas.api import QVService


# ---------------------------------------------------------------------------
# Fixtures (same pattern as test_incremental_run.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal project structure using service API."""
    project_root = tmp_path / "project"
    project_root = QVService.init_project(target_dir=project_root, name="test_cascade")
    return project_root


@pytest.fixture
def minimal_structure(tmp_project):
    """Create a minimal structure using service API."""
    from pymatgen.core import Structure, Lattice
    import tempfile

    lattice = Lattice.cubic(2.0)
    structure = Structure(lattice, ["Si"], [[0, 0, 0]])

    with tempfile.NamedTemporaryFile(mode='w', suffix='.cif', delete=False) as f:
        cif_path = Path(f.name)

    try:
        structure.to(filename=str(cif_path), fmt="cif")
        structure_resolved = QVService(tmp_project).structure.import_file(
            source=cif_path,
            name="test_structure",
        )
        structure_ulid = structure_resolved.meta.ulid
        structure_path = tmp_project / "structures" / f"{structure_resolved.meta.slug}.json"
    finally:
        if cif_path.exists():
            cif_path.unlink()

    (tmp_project / "pseudo").mkdir(parents=True, exist_ok=True)
    (tmp_project / "pseudo" / "Si.UPF").write_text("FAKE PSEUDO FILE")

    return structure_ulid, structure_path


@pytest.fixture
def minimal_calculation(tmp_project, minimal_structure):
    """Create a minimal 3-step QE calculation (scf/nscf/bands)."""
    structure_ulid, structure_path = minimal_structure

    calc_resolved = QVService(tmp_project).project.init_calculation(
        name="test_cascade_calc",
        structure_selector=structure_ulid,
        engine_family="qe",
    )
    calc_id = calc_resolved.meta.ulid
    calc_dir = calc_resolved.absolute_path

    # Set species_map
    from quantumvitas.core.yaml_io import save_yaml_doc
    from quantumvitas.core.yamldoc import CalcDoc
    from quantumvitas.core.models import load_calculation

    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)

    if not calc_model.species_map:
        calc_model.species_map = {
            "Si": {"pseudopot": "Si.UPF", "mass": 28.0855},
        }
        calc_doc = CalcDoc(calc_model.to_dict())
        save_yaml_doc(calc_doc, calc_data_path)

    # Add 3 steps
    svc = QVService(tmp_project)
    step1_dto = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="scf")
    step2_dto = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="nscf")
    step3_dto = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="bands")

    step_ids = [step1_dto.step_ulid, step2_dto.step_ulid, step3_dto.step_ulid]

    # Fix bands step K_POINTS (same as test_incremental_run.py)
    step3_spec_path = calc_dir / "steps" / f"{step3_dto.meta.slug}.step.yaml"
    step3_data = yaml.safe_load(step3_spec_path.read_text())
    if "cards" in step3_data and "K_POINTS" in step3_data["cards"]:
        kpoints = step3_data["cards"]["K_POINTS"]
        if kpoints.get("option") == "crystal_b" and "data" not in kpoints:
            step3_data["cards"]["K_POINTS"] = {
                "option": "crystal_b",
                "data": [[0.0, 0.0, 0.0, 1]],
            }
            step3_spec_path.write_text(yaml.safe_dump(step3_data, sort_keys=False))

    return calc_id, calc_dir, step_ids


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_shas(tmp_project, calc_id, calc_dir, step_ids):
    """Compute all SHAs for manifest entries (structure, pseudo, per-step)."""
    from quantumvitas.core.models import load_calculation
    from quantumvitas.core.resolution import require_structure, require_step, build_resource_index
    from quantumvitas.core.project_utils import load_project_config
    from quantumvitas.core.yamldoc import StepDoc

    calc_data_path = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_data_path, project_root=tmp_project)
    config = load_project_config(tmp_project)
    index = build_resource_index(tmp_project)

    # Structure SHA
    structure_resolved = require_structure(
        tmp_project, calc_model.structure_ulid, config=config, index=index,
    )
    structure_path = structure_resolved.absolute_path
    structure_sha = compute_structure_sha(structure_path)

    # Pseudo SHA
    pseudo_sha = compute_pseudo_set_sha(tmp_project / "pseudo", calc_model.species_map or {})

    # Step SHAs
    step_shas = []
    for step_id in step_ids:
        step_resolved = require_step(tmp_project, calc_id, step_id, config=config, index=index)
        step_doc = StepDoc.load(step_resolved.absolute_path)
        step_shas.append(compute_step_sha(step_doc.to_dict()))

    return structure_path, structure_sha, pseudo_sha, step_shas


def _build_done_manifest(step_ids, structure_sha, pseudo_sha, step_shas):
    """Build a manifest with all steps done=True using actual SHAs."""
    kinds = ["qe_scf", "qe_nscf", "qe_bands"]
    manifest = Manifest()
    for i, step_id in enumerate(step_ids):
        manifest.steps.append(ManifestStepEntry(
            kind=kinds[i],
            step_ulid=step_id,
            pseudo_set_sha=pseudo_sha,
            structure_sha=structure_sha,
            step_sha=step_shas[i],
            run_ulid="test_run",
            done=True,
            started_at="2024-01-01T00:00:00Z",
            done_at="2024-01-01T00:01:00Z",
        ))
    return manifest


def _mutate_step_sha(tmp_project, calc_id, step_id, config=None, index=None):
    """Modify a step's YAML to change its SHA (add a harmless parameter)."""
    from quantumvitas.core.resolution import require_step, build_resource_index
    from quantumvitas.core.project_utils import load_project_config

    if config is None:
        config = load_project_config(tmp_project)
    if index is None:
        index = build_resource_index(tmp_project)

    step_resolved = require_step(tmp_project, calc_id, step_id, config=config, index=index)
    step_path = step_resolved.absolute_path
    step_data = yaml.safe_load(step_path.read_text())

    # Add/modify a parameter to change the SHA
    if "parameters" not in step_data:
        step_data["parameters"] = {}
    if "SYSTEM" not in step_data["parameters"]:
        step_data["parameters"]["SYSTEM"] = {}
    step_data["parameters"]["SYSTEM"]["ecutwfc_cascade_test"] = 99.0

    step_path.write_text(yaml.safe_dump(step_data, sort_keys=False))


# ---------------------------------------------------------------------------
# Tests: reconcile_manifest cascade
# ---------------------------------------------------------------------------


class TestReconcileCascade:
    """Tests for cascade invalidation in reconcile_manifest()."""

    def test_reconcile_cascade_step1_sha_changed(
        self, tmp_project, minimal_calculation, monkeypatch,
    ):
        """Step 1 SHA changes -> step 1 done=False AND step 2 done=False (cascade)."""
        calc_id, calc_dir, step_ids = minimal_calculation
        monkeypatch.setattr(
            "quantumvitas.calculation.manifest_reconcile.is_step_done",
            lambda *a, **kw: True,
        )

        structure_path, structure_sha, pseudo_sha, step_shas = _compute_shas(
            tmp_project, calc_id, calc_dir, step_ids,
        )

        # Build manifest with all 3 steps done
        manifest = _build_done_manifest(step_ids, structure_sha, pseudo_sha, step_shas)
        save_manifest_atomic(calc_dir, manifest)

        # Mutate step 1 to change its SHA
        _mutate_step_sha(tmp_project, calc_id, step_ids[1])

        # Reconcile
        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.project.model import Project

        project = Project.open(tmp_project)
        calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)

        reconciled, first_changed_idx = reconcile_manifest(
            calc_dir=calc_dir,
            project_root=tmp_project,
            calculation_steps=calculation.steps,
            current_pseudo_set_sha=pseudo_sha,
            structure_path=structure_path,
        )

        assert first_changed_idx == 1
        assert reconciled.steps[0].done is True   # step 0 unchanged
        assert reconciled.steps[1].done is False   # step 1 SHA changed
        assert reconciled.steps[2].done is False   # step 2 CASCADE invalidated

    def test_reconcile_cascade_step0_sha_changed(
        self, tmp_project, minimal_calculation, monkeypatch,
    ):
        """Step 0 SHA changes -> ALL 3 steps done=False (cascade from beginning)."""
        calc_id, calc_dir, step_ids = minimal_calculation
        monkeypatch.setattr(
            "quantumvitas.calculation.manifest_reconcile.is_step_done",
            lambda *a, **kw: True,
        )

        structure_path, structure_sha, pseudo_sha, step_shas = _compute_shas(
            tmp_project, calc_id, calc_dir, step_ids,
        )

        manifest = _build_done_manifest(step_ids, structure_sha, pseudo_sha, step_shas)
        save_manifest_atomic(calc_dir, manifest)

        # Mutate step 0
        _mutate_step_sha(tmp_project, calc_id, step_ids[0])

        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.project.model import Project

        project = Project.open(tmp_project)
        calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)

        reconciled, first_changed_idx = reconcile_manifest(
            calc_dir=calc_dir,
            project_root=tmp_project,
            calculation_steps=calculation.steps,
            current_pseudo_set_sha=pseudo_sha,
            structure_path=structure_path,
        )

        assert first_changed_idx == 0
        assert reconciled.steps[0].done is False
        assert reconciled.steps[1].done is False
        assert reconciled.steps[2].done is False

    def test_reconcile_no_cascade_when_unchanged(
        self, tmp_project, minimal_calculation, monkeypatch,
    ):
        """No mutations, all SHAs match -> all steps remain done=True."""
        calc_id, calc_dir, step_ids = minimal_calculation
        monkeypatch.setattr(
            "quantumvitas.calculation.manifest_reconcile.is_step_done",
            lambda *a, **kw: True,
        )

        structure_path, structure_sha, pseudo_sha, step_shas = _compute_shas(
            tmp_project, calc_id, calc_dir, step_ids,
        )

        manifest = _build_done_manifest(step_ids, structure_sha, pseudo_sha, step_shas)
        save_manifest_atomic(calc_dir, manifest)

        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.project.model import Project

        project = Project.open(tmp_project)
        calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)

        reconciled, first_changed_idx = reconcile_manifest(
            calc_dir=calc_dir,
            project_root=tmp_project,
            calculation_steps=calculation.steps,
            current_pseudo_set_sha=pseudo_sha,
            structure_path=structure_path,
        )

        assert first_changed_idx == len(step_ids)  # All done
        assert reconciled.steps[0].done is True
        assert reconciled.steps[1].done is True
        assert reconciled.steps[2].done is True

    def test_reconcile_cascade_last_step_no_upstream_effect(
        self, tmp_project, minimal_calculation, monkeypatch,
    ):
        """Modify only last step -> steps 0,1 remain done=True, step 2 done=False."""
        calc_id, calc_dir, step_ids = minimal_calculation
        monkeypatch.setattr(
            "quantumvitas.calculation.manifest_reconcile.is_step_done",
            lambda *a, **kw: True,
        )

        structure_path, structure_sha, pseudo_sha, step_shas = _compute_shas(
            tmp_project, calc_id, calc_dir, step_ids,
        )

        manifest = _build_done_manifest(step_ids, structure_sha, pseudo_sha, step_shas)
        save_manifest_atomic(calc_dir, manifest)

        # Mutate only the last step
        _mutate_step_sha(tmp_project, calc_id, step_ids[2])

        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.project.model import Project

        project = Project.open(tmp_project)
        calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)

        reconciled, first_changed_idx = reconcile_manifest(
            calc_dir=calc_dir,
            project_root=tmp_project,
            calculation_steps=calculation.steps,
            current_pseudo_set_sha=pseudo_sha,
            structure_path=structure_path,
        )

        assert first_changed_idx == 2
        assert reconciled.steps[0].done is True
        assert reconciled.steps[1].done is True
        assert reconciled.steps[2].done is False

    def test_reconcile_cascade_single_step_calc(
        self, tmp_project, minimal_structure, monkeypatch,
    ):
        """Single-step calc with SHA change -> done=False, no IndexError."""
        structure_ulid, structure_path = minimal_structure
        monkeypatch.setattr(
            "quantumvitas.calculation.manifest_reconcile.is_step_done",
            lambda *a, **kw: True,
        )

        # Create 1-step calculation
        calc_resolved = QVService(tmp_project).project.init_calculation(
            name="single_step",
            structure_selector=structure_ulid,
            engine_family="qe",
        )
        calc_id = calc_resolved.meta.ulid
        calc_dir = calc_resolved.absolute_path

        from quantumvitas.core.yaml_io import save_yaml_doc
        from quantumvitas.core.yamldoc import CalcDoc
        from quantumvitas.core.models import load_calculation

        calc_data_path = calc_dir / "calculation.yaml"
        calc_model = load_calculation(calc_data_path, project_root=tmp_project)
        if not calc_model.species_map:
            calc_model.species_map = {"Si": {"pseudopot": "Si.UPF", "mass": 28.0855}}
            calc_doc = CalcDoc(calc_model.to_dict())
            save_yaml_doc(calc_doc, calc_data_path)

        svc = QVService(tmp_project)
        step_dto = svc.calculation.add_step(calc_selector=calc_id, step_type_gen="scf")
        step_id = step_dto.step_ulid

        structure_path_r, structure_sha, pseudo_sha, step_shas = _compute_shas(
            tmp_project, calc_id, calc_dir, [step_id],
        )

        manifest = Manifest()
        manifest.steps.append(ManifestStepEntry(
            kind="qe_scf",
            step_ulid=step_id,
            pseudo_set_sha=pseudo_sha,
            structure_sha=structure_sha,
            step_sha=step_shas[0],
            run_ulid="test_run",
            done=True,
            started_at="2024-01-01T00:00:00Z",
            done_at="2024-01-01T00:01:00Z",
        ))
        save_manifest_atomic(calc_dir, manifest)

        # Mutate the single step
        _mutate_step_sha(tmp_project, calc_id, step_id)

        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.project.model import Project

        project = Project.open(tmp_project)
        calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)

        # Should not raise IndexError
        reconciled, first_changed_idx = reconcile_manifest(
            calc_dir=calc_dir,
            project_root=tmp_project,
            calculation_steps=calculation.steps,
            current_pseudo_set_sha=pseudo_sha,
            structure_path=structure_path_r,
        )

        assert first_changed_idx == 0
        assert reconciled.steps[0].done is False


class TestTargetModeInvalidation:
    """Tests for TARGET mode downstream invalidation (Fix 7.2)."""

    def test_target_mode_invalidates_downstream(
        self, tmp_project, minimal_calculation, monkeypatch,
    ):
        """Running in TARGET mode invalidates downstream steps."""
        calc_id, calc_dir, step_ids = minimal_calculation

        structure_path, structure_sha, pseudo_sha, step_shas = _compute_shas(
            tmp_project, calc_id, calc_dir, step_ids,
        )

        # Build manifest with all steps done
        manifest = _build_done_manifest(step_ids, structure_sha, pseudo_sha, step_shas)
        save_manifest_atomic(calc_dir, manifest)

        # Mock the entire runner to simulate successful target execution
        # then check that clear_manifest_from_step was called
        from quantumvitas.calculation.runner import CalculationRunner
        from quantumvitas.calculation.results import CalculationResult
        from quantumvitas.calculation.types import StepStatus
        from datetime import datetime, timezone

        def mock_run(self, calculation, *, run_ulid=None, run_mode="incremental",
                     target_step_ulid=None, compat_input_playback=False):
            # Simulate successful target execution at step 1
            # The real runner calls clear_manifest_from_step after target completes
            if target_step_ulid is not None:
                target_idx = self._find_step_index(calculation, target_step_ulid)
                if target_idx is not None:
                    clear_manifest_from_step(calculation.dir, target_idx + 1)

            return CalculationResult(
                calculation_ulid=calculation.ulid,
                mode=calculation.mode,
                steps=[],
                status=StepStatus.SUCCESS,
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )

        monkeypatch.setattr(CalculationRunner, "run", mock_run)

        # Run with target = step 1 (middle)
        from quantumvitas.calculation.calculation import Calculation
        from quantumvitas.project.model import Project
        from quantumvitas.engine.registry import create_default_registry

        project = Project.open(tmp_project)
        calculation = Calculation.from_yaml(calc_dir, project, materialize_steps=False)

        runner = CalculationRunner(create_default_registry())
        runner.run(calculation, target_step_ulid=step_ids[1])

        # Verify downstream invalidation
        manifest_after = load_manifest(calc_dir)
        assert manifest_after is not None
        assert manifest_after.steps[0].done is True   # upstream untouched
        assert manifest_after.steps[1].done is True    # target (was already done, mock didn't change it)
        assert manifest_after.steps[2].done is False   # downstream invalidated
