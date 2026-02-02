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

from quantumvitas.core.models import load_project, load_calculation
from quantumvitas.core.resolution import build_resource_index
from quantumvitas.project.snapshot import (
    ProjectSnapshot,
    export_project_to_snapshot,
    materialize_project_from_snapshot,
)
from quantumvitas.calculation.structure_steps import StructureStepSpec


@pytest.fixture
def temp_dir():
    """Create a temporary directory for materialized test projects."""
    import shutil
    tmp = tempfile.mkdtemp(prefix="qv_snapshot_id_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def project2_bands_path() -> Path:
    """Path to project2_bands example (bands calculations with multiple steps)."""
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
        if project_meta.get("ulid"):
            snapshot_ids.add(project_meta["ulid"])
        
        # Structure IDs
        for struct_data in snapshot.structures:
            struct_meta = struct_data.get("meta", {})
            if struct_meta.get("ulid"):
                snapshot_ids.add(struct_meta["ulid"])
        
        # Calculation IDs
        for calculation_data in snapshot.calculations:
            calculation_meta = calculation_data.get("meta", {})
            if calculation_meta.get("ulid"):
                snapshot_ids.add(calculation_meta["ulid"])
            
            # Step IDs
            for step_data in calculation_data.get("steps", []):
                step_meta = step_data.get("meta", {})
                if step_meta.get("ulid"):
                    snapshot_ids.add(step_meta["ulid"])
        
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
        
        assert len(new_project.calculations) == len(snapshot.calculations), (
            f"Calculation count mismatch: snapshot has {len(snapshot.calculations)}, "
            f"materialized has {len(new_project.calculations)}"
        )
        
        # Assert: Each calculation has the same number and types of steps
        for i, calculation_data in enumerate(snapshot.calculations):
            snapshot_steps = calculation_data.get("steps", [])
            snapshot_step_types = [s.get("step_type_spec") for s in snapshot_steps]
            
            new_calculation_entry = new_project.calculations[i]
            new_calculation = load_calculation(
                new_project_root / new_calculation_entry.meta.path / "calculation.yaml",
                new_project_root,
            )
            
            assert len(new_calculation.steps) == len(snapshot_steps), (
                f"Calculation {i} step count mismatch: snapshot has {len(snapshot_steps)}, "
                f"materialized has {len(new_calculation.steps)}"
            )
            
            # Check step types match (order may differ, so use sets)
            # Resolve step files via registry using step_id
            # (materialized_index is already built earlier in the test at line 90)
            
            new_step_types = []
            for step_entry in new_calculation.steps:
                if step_entry.step_ulid:
                    # Resolve step file via registry using step_id
                    step_meta = materialized_index.by_id.get(step_entry.step_ulid)
                    if step_meta and step_meta.kind == "step":
                        step_path = new_project_root / step_meta.path
                        if step_path.exists():
                            step_spec = StructureStepSpec.from_yaml(step_path)
                            new_step_types.append(step_spec.step_type_spec)
            
            assert set(new_step_types) == set(snapshot_step_types), (
                f"Calculation {i} step types mismatch: snapshot has {set(snapshot_step_types)}, "
                f"materialized has {set(new_step_types)}"
            )
        
        # Assert: All cross-references are valid (no broken links)
        # Check calculation → structure references
        for calculation_entry in new_project.calculations:
            calculation = load_calculation(
                new_project_root / calculation_entry.meta.path / "calculation.yaml",
                new_project_root,
            )
            
            if calculation.structure_ulid:
                # Structure ID should exist in materialized project
                assert calculation.structure_ulid in materialized_index.by_id, (
                    f"Calculation {calculation.meta.name} references structure_ulid {calculation.structure_ulid} "
                    f"which does not exist in materialized project"
                )
                structure_meta = materialized_index.by_id[calculation.structure_ulid]
                assert structure_meta.kind == "structure", (
                    f"Calculation references {calculation.structure_ulid} but it's not a structure "
                    f"(kind: {structure_meta.kind})"
                )
            
            # Check step → calculation references
            # Use materialized_index to resolve step files via step_id
            for step_entry in calculation.steps:
                if step_entry.step_ulid:
                    # Resolve step file via registry using step_id
                    step_meta = materialized_index.by_id.get(step_entry.step_ulid)
                    if step_meta and step_meta.kind == "step":
                        step_path = new_project_root / step_meta.path
                        if step_path.exists():
                            # DAG model: Step YAML should NOT contain structure_ulid or parent_calculation_id
                            step_yaml_text = step_path.read_text()
                            assert "parent_calculation_id:" not in step_yaml_text, (
                                f"Step {step_meta.name} YAML should not contain parent_calculation_id (DAG model)"
                            )
                            assert "structure_ulid:" not in step_yaml_text, (
                                f"Step {step_meta.name} YAML should not contain structure_ulid (DAG model)"
                            )
                            
                            # Load spec for other validations
                            step_spec = StructureStepSpec.from_yaml(step_path)
                        
                        # Step structure is resolved via calculation.structure_ulid at runtime
                        # Verify calculation has structure_ulid set
                        assert calculation.structure_ulid is not None, (
                            f"Calculation {calculation.meta.name} should have structure_ulid set"
                        )
                        # Verify structure exists in index
                        if calculation.structure_ulid:
                            assert calculation.structure_ulid in materialized_index.by_id, (
                                f"Calculation {calculation.meta.name} references structure_ulid "
                                f"{calculation.structure_ulid} which does not exist"
                            )
                            structure_meta = materialized_index.by_id[calculation.structure_ulid]
                            assert structure_meta.kind == "structure", (
                                f"Calculation references {calculation.structure_ulid} but it's not a structure"
                            )
                            # DAG model: Step structure is resolved via calculation.structure_ulid
                            # No need to check step_spec.structure_ulid as it's not persisted in YAML
        
        # Assert: Graph structure matches snapshot pattern
        # In snapshot, each calculation has structure_ulid pointing to a structure
        # In materialized project, same pattern should exist
        snapshot_calculation_structure_ulids = set()
        for calculation_data in snapshot.calculations:
            structure_ulid = calculation_data.get("structure_ulid")
            if structure_ulid:
                snapshot_calculation_structure_ulids.add(structure_ulid)
        
        materialized_calculation_structure_ulids = set()
        for calculation_entry in new_project.calculations:
            calculation = load_calculation(
                new_project_root / calculation_entry.meta.path / "calculation.yaml",
                new_project_root,
            )
            if calculation.structure_ulid:
                materialized_calculation_structure_ulids.add(calculation.structure_ulid)
        
        # Number of calculations with structure references should match
        assert len(materialized_calculation_structure_ulids) == len(snapshot_calculation_structure_ulids), (
            f"Number of calculations with structure references mismatch: "
            f"snapshot has {len(snapshot_calculation_structure_ulids)}, "
            f"materialized has {len(materialized_calculation_structure_ulids)}"
        )

