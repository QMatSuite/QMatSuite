"""
Unit tests for snapshot ID regeneration and graph preservation.

Tests verify that materializing a snapshot:
- Regenerates all ULIDs (no intersection with snapshot IDs)
- Preserves graph structure (counts, relationships, cross-references)
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from quantumvitas.core.models import load_project, load_workflow
from quantumvitas.core.resolution import build_resource_index
from quantumvitas.project.snapshot import (
    ProjectSnapshot,
    export_project_to_snapshot,
    materialize_project_from_snapshot,
)
from quantumvitas.workflow.structure_steps import StructureStepSpec


@pytest.fixture
def temp_dir():
    """Create a temporary directory for materialized test projects."""
    import shutil
    tmp = tempfile.mkdtemp(prefix="qv_snapshot_id_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def project2_bands_path() -> Path:
    """Path to project2_bands example (bands workflows with multiple steps)."""
    return Path(__file__).parent.parent / "data" / "project_examples" / "project2_bands"


class TestSnapshotIDRegeneration:
    """Test that snapshot materialization regenerates IDs but preserves graph structure."""
    
    def test_id_regeneration_and_graph_preservation(
        self, project2_bands_path: Path, temp_dir: Path
    ):
        """
        Test that materializing a snapshot:
        1. Regenerates all ULIDs (no intersection with snapshot IDs)
        2. Preserves graph structure (counts, relationships, cross-references)
        """
        # Export original project to snapshot
        snapshot = export_project_to_snapshot(project2_bands_path)
        
        # Collect all IDs from snapshot
        snapshot_ids = set()
        
        # Project ID
        project_meta = snapshot.project.get("meta", {})
        if project_meta.get("id"):
            snapshot_ids.add(project_meta["id"])
        
        # Structure IDs
        for struct_data in snapshot.structures:
            struct_meta = struct_data.get("meta", {})
            if struct_meta.get("id"):
                snapshot_ids.add(struct_meta["id"])
        
        # Workflow IDs
        for workflow_data in snapshot.workflows:
            workflow_meta = workflow_data.get("meta", {})
            if workflow_meta.get("id"):
                snapshot_ids.add(workflow_meta["id"])
            
            # Step IDs
            for step_data in workflow_data.get("steps", []):
                step_meta = step_data.get("meta", {})
                if step_meta.get("id"):
                    snapshot_ids.add(step_meta["id"])
        
        assert len(snapshot_ids) > 0, "Snapshot should contain at least some IDs"
        
        # Materialize snapshot into new project
        new_project_root = materialize_project_from_snapshot(
            snapshot=snapshot,
            parent_dir=temp_dir,
            new_project_name="Regenerated IDs Test",
        )
        
        # Build ResourceIndex for materialized project
        materialized_index = build_resource_index(new_project_root)
        
        # Collect all IDs from materialized project
        materialized_ids = set(materialized_index.by_id.keys())
        
        # Assert: No intersection between snapshot IDs and materialized IDs
        intersection = snapshot_ids & materialized_ids
        assert len(intersection) == 0, (
            f"Materialized project should have no IDs in common with snapshot. "
            f"Found {len(intersection)} overlapping IDs: {list(intersection)[:5]}"
        )
        
        # Assert: Graph structure is preserved (counts)
        new_project = load_project(new_project_root)
        
        assert len(new_project.structures) == len(snapshot.structures), (
            f"Structure count mismatch: snapshot has {len(snapshot.structures)}, "
            f"materialized has {len(new_project.structures)}"
        )
        
        assert len(new_project.workflows) == len(snapshot.workflows), (
            f"Workflow count mismatch: snapshot has {len(snapshot.workflows)}, "
            f"materialized has {len(new_project.workflows)}"
        )
        
        # Assert: Each workflow has the same number and types of steps
        for i, workflow_data in enumerate(snapshot.workflows):
            snapshot_steps = workflow_data.get("steps", [])
            snapshot_step_types = [s.get("step_type") for s in snapshot_steps]
            
            new_workflow_entry = new_project.workflows[i]
            new_workflow = load_workflow(
                new_project_root / new_workflow_entry.meta.path / "workflow.yaml",
                new_project_root,
            )
            
            assert len(new_workflow.steps) == len(snapshot_steps), (
                f"Workflow {i} step count mismatch: snapshot has {len(snapshot_steps)}, "
                f"materialized has {len(new_workflow.steps)}"
            )
            
            # Check step types match (order may differ, so use sets)
            # Resolve step files via registry using step_id
            # (materialized_index is already built earlier in the test at line 90)
            
            new_step_types = []
            for step_entry in new_workflow.steps:
                if step_entry.step_id:
                    # Resolve step file via registry using step_id
                    step_meta = materialized_index.by_id.get(step_entry.step_id)
                    if step_meta and step_meta.kind == "step":
                        step_path = new_project_root / step_meta.path
                        if step_path.exists():
                            step_spec = StructureStepSpec.from_yaml(step_path)
                            new_step_types.append(step_spec.step_type)
            
            assert set(new_step_types) == set(snapshot_step_types), (
                f"Workflow {i} step types mismatch: snapshot has {set(snapshot_step_types)}, "
                f"materialized has {set(new_step_types)}"
            )
        
        # Assert: All cross-references are valid (no broken links)
        # Check workflow → structure references
        for workflow_entry in new_project.workflows:
            workflow = load_workflow(
                new_project_root / workflow_entry.meta.path / "workflow.yaml",
                new_project_root,
            )
            
            if workflow.structure_id:
                # Structure ID should exist in materialized project
                assert workflow.structure_id in materialized_index.by_id, (
                    f"Workflow {workflow.meta.name} references structure_id {workflow.structure_id} "
                    f"which does not exist in materialized project"
                )
                structure_meta = materialized_index.by_id[workflow.structure_id]
                assert structure_meta.kind == "structure", (
                    f"Workflow references {workflow.structure_id} but it's not a structure "
                    f"(kind: {structure_meta.kind})"
                )
            
            # Check step → workflow references
            # Use materialized_index to resolve step files via step_id
            for step_entry in workflow.steps:
                if step_entry.step_id:
                    # Resolve step file via registry using step_id
                    step_meta = materialized_index.by_id.get(step_entry.step_id)
                    if step_meta and step_meta.kind == "step":
                        step_path = new_project_root / step_meta.path
                        if step_path.exists():
                            step_spec = StructureStepSpec.from_yaml(step_path)
                        
                        # Step should reference parent workflow
                        if step_spec.parent_workflow_id:
                            assert step_spec.parent_workflow_id in materialized_index.by_id, (
                                f"Step {step_spec.meta.name} references parent_workflow_id "
                                f"{step_spec.parent_workflow_id} which does not exist"
                            )
                            parent_meta = materialized_index.by_id[step_spec.parent_workflow_id]
                            assert parent_meta.kind == "workflow", (
                                f"Step references {step_spec.parent_workflow_id} but it's not a workflow"
                            )
                            # Parent workflow ID should match the workflow containing this step
                            assert step_spec.parent_workflow_id == workflow.meta.id, (
                                f"Step {step_spec.meta.name} has parent_workflow_id "
                                f"{step_spec.parent_workflow_id} but is in workflow {workflow.meta.id}"
                            )
                        
                        # Step should reference structure (if present)
                        if step_spec.structure_id:
                            assert step_spec.structure_id in materialized_index.by_id, (
                                f"Step {step_spec.meta.name} references structure_id "
                                f"{step_spec.structure_id} which does not exist"
                            )
                            structure_meta = materialized_index.by_id[step_spec.structure_id]
                            assert structure_meta.kind == "structure", (
                                f"Step references {step_spec.structure_id} but it's not a structure"
                            )
        
        # Assert: Graph structure matches snapshot pattern
        # In snapshot, each workflow has structure_id pointing to a structure
        # In materialized project, same pattern should exist
        snapshot_workflow_structure_ids = set()
        for workflow_data in snapshot.workflows:
            structure_id = workflow_data.get("structure_id")
            if structure_id:
                snapshot_workflow_structure_ids.add(structure_id)
        
        materialized_workflow_structure_ids = set()
        for workflow_entry in new_project.workflows:
            workflow = load_workflow(
                new_project_root / workflow_entry.meta.path / "workflow.yaml",
                new_project_root,
            )
            if workflow.structure_id:
                materialized_workflow_structure_ids.add(workflow.structure_id)
        
        # Number of workflows with structure references should match
        assert len(materialized_workflow_structure_ids) == len(snapshot_workflow_structure_ids), (
            f"Number of workflows with structure references mismatch: "
            f"snapshot has {len(snapshot_workflow_structure_ids)}, "
            f"materialized has {len(materialized_workflow_structure_ids)}"
        )

