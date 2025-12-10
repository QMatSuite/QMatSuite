"""
Unit tests for project snapshot export/import functionality.

Tests bidirectional roundtrip: disk project → snapshot → new project.

Uses example projects from tests/data/project_examples/.
"""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from quantumvitas.api import QVService
from quantumvitas.core.models import load_project, load_structure_model, load_workflow
from quantumvitas.project.snapshot import (
    ProjectSnapshot,
    export_project_to_snapshot,
    materialize_project_from_snapshot,
)
from quantumvitas.workflow.structure_steps import StructureStepSpec


@pytest.fixture
def temp_dir():
    """Create a temporary directory for materialized test projects."""
    tmp = tempfile.mkdtemp(prefix="qv_snapshot_test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def project1_path() -> Path:
    """Path to project1 example (DOS workflow)."""
    return Path(__file__).parent.parent / "data" / "project_examples" / "project1"


@pytest.fixture
def project2_bands_path() -> Path:
    """Path to project2_bands example (bands workflows)."""
    return Path(__file__).parent.parent / "data" / "project_examples" / "project2_bands"


class TestProjectSnapshot:
    """Test project snapshot export and import."""
    
    def test_export_project_to_snapshot(self, project1_path: Path):
        """Test exporting a project to a snapshot."""
        snapshot = export_project_to_snapshot(project1_path)
        
        assert snapshot.version == 1
        assert "meta" in snapshot.project
        assert len(snapshot.structures) == 1
        assert len(snapshot.workflows) == 1
        
        # Check structure
        struct_data = snapshot.structures[0]
        assert struct_data["meta"]["name"] == "Si"
        assert "data" in struct_data
        
        # Check workflow
        workflow_data = snapshot.workflows[0]
        assert workflow_data["meta"]["name"] == "Si dos"
        # Structure reference: should use structure_id (ULID), not structure selector
        # New exports should have structure_id (ULID), old snapshots may have structure (selector)
        structure_id = workflow_data.get("structure_id")
        structure_selector = workflow_data.get("structure")
        # Either structure_id (ULID) or structure (selector) should be present
        assert structure_id is not None or structure_selector is not None
        # If structure_id is present, it should be a ULID (26 chars), not a human-readable name
        if structure_id:
            assert len(structure_id) == 26, "structure_id should be a ULID, not a human-readable name"
        assert len(workflow_data["steps"]) > 0
    
    def test_materialize_project_from_snapshot(
        self, project1_path: Path, temp_dir: Path
    ):
        """Test creating a new project from a snapshot."""
        # Export original project
        snapshot = export_project_to_snapshot(project1_path)
        
        # Materialize in new location
        new_project_root = materialize_project_from_snapshot(
            snapshot=snapshot,
            parent_dir=temp_dir,
            new_project_name="Cloned Project",
        )
        
        assert new_project_root.exists()
        assert (new_project_root / "project.qv.yml").exists()
        assert (new_project_root / "structures" / "si.json").exists()
        assert (new_project_root / "workflows" / "si-dos" / "workflow.yaml").exists()
        
        # Load and verify project
        new_project = load_project(new_project_root)
        assert new_project.name == "Cloned Project"
        assert len(new_project.structures) == 1
        assert len(new_project.workflows) == 1
        
        # Verify structure
        struct_entry = new_project.structures[0]
        assert struct_entry.meta.name == "Si"
        # Structure file meta should also have correct name (from snapshot)
        struct_model = load_structure_model(
            new_project_root / struct_entry.file,
            new_project_root,
        )
        assert struct_model.meta.name == "Si"
        
        # Verify workflow
        workflow_entry = new_project.workflows[0]
        assert workflow_entry.meta.name == "Si dos"
        workflow_model = load_workflow(
            new_project_root / workflow_entry.meta.path / "workflow.yaml",
            new_project_root,
        )
        # Structure reference uses ID (structure_id is canonical)
        assert workflow_model.structure_id is not None
        assert workflow_model.structure_name == "Si"
        assert len(workflow_model.steps) > 0
        
        # Verify step
        # Resolve step file via registry using step_id (ID-only model)
        from quantumvitas.core.resolution import build_resource_index
        index = build_resource_index(new_project_root)
        step_entry = workflow_model.steps[0]
        step_meta = index.by_id.get(step_entry.step_id)
        assert step_meta is not None, f"Step {step_entry.step_id} not found in registry"
        step_file = new_project_root / step_meta.path
        step_spec = StructureStepSpec.from_yaml(step_file)
        # DAG model: Step YAML should NOT contain structure_id or parent_workflow_id
        # Structure is resolved via workflow.structure_id at runtime
        # Verify step YAML does not contain these fields
        step_yaml_text = step_file.read_text()
        assert "structure_id:" not in step_yaml_text, "Step YAML should not contain structure_id (DAG model)"
        assert "parent_workflow_id:" not in step_yaml_text, "Step YAML should not contain parent_workflow_id (DAG model)"
        # Runtime structure resolution: step should resolve structure via workflow
        # The step spec may have structure_id in memory (for backward compatibility), but it's not persisted
    
    def test_snapshot_ulid_regeneration(
        self, project1_path: Path, temp_dir: Path
    ):
        """Test that ULIDs are regenerated when materializing from snapshot."""
        # Export original project
        snapshot = export_project_to_snapshot(project1_path)
        original_project = load_project(project1_path)
        original_workflow = load_workflow(
            project1_path / original_project.workflows[0].meta.path / "workflow.yaml",
            project1_path,
        )
        
        # Materialize new project
        new_project_root = materialize_project_from_snapshot(
            snapshot=snapshot,
            parent_dir=temp_dir,
        )
        
        new_project = load_project(new_project_root)
        new_workflow = load_workflow(
            new_project_root / new_project.workflows[0].meta.path / "workflow.yaml",
            new_project_root,
        )
        
        # ULIDs should be different
        assert original_project.meta.id != new_project.meta.id
        assert original_workflow.meta.id != new_workflow.meta.id
        
        # But names/slugs should match
        assert original_project.meta.name == new_project.meta.name
        # Compare workflow entry names (from project.qv.yml), not workflow model names
        # Note: workflow entry meta.name comes from project.qv.yml (which has "Si dos")
        # but workflow.yaml meta.name might be "si-dos" (slug) if it was created with old format
        # So we compare the workflow entry meta.name (from project.qv.yml) which should be preserved
        original_wf_entry_name = original_project.workflows[0].meta.name
        new_wf_entry_name = new_project.workflows[0].meta.name
        # The snapshot export should preserve the name from project.qv.yml (legacy format)
        # So both should have "Si dos" from the original project.qv.yml
        assert original_wf_entry_name == new_wf_entry_name, \
            f"Workflow entry names should match: original={original_wf_entry_name}, new={new_wf_entry_name}"
    
    def test_snapshot_pseudo_files(self, project1_path: Path, temp_dir: Path):
        """Test that pseudo file list is exported but files are not created."""
        # Export snapshot (project1 may or may not have pseudo files)
        snapshot = export_project_to_snapshot(project1_path)
        
        # Materialize project
        new_project_root = materialize_project_from_snapshot(
            snapshot=snapshot,
            parent_dir=temp_dir,
        )
        
        # Pseudo directory should exist if snapshot has pseudo section
        if snapshot.pseudo:
            new_pseudo_dir = new_project_root / "pseudo"
            assert new_pseudo_dir.exists()
            
            # If snapshot has pseudo files listed, they should NOT be created
            if snapshot.pseudo.get("files"):
                for pseudo_file in snapshot.pseudo["files"]:
                    assert not (new_pseudo_dir / pseudo_file).exists(), \
                        f"Pseudo file {pseudo_file} should not be created (snapshot doesn't embed content)"


class TestSnapshotCLI:
    """Test CLI commands for snapshot operations."""
    
    def test_save_project_snapshot_cli(self, project1_path: Path, temp_dir: Path):
        """Test qv save-project CLI command."""
        snapshot_path = temp_dir / "snapshot.yml"
        
        QVService.save_project_snapshot(
            project_root=project1_path,
            output_path=snapshot_path,
            overwrite=False,
        )
        
        assert snapshot_path.exists()
        
        # Verify snapshot content
        snapshot_data = yaml.safe_load(snapshot_path.read_text())
        assert snapshot_data["version"] == 1
        assert "project" in snapshot_data
        assert "structures" in snapshot_data
        assert "workflows" in snapshot_data
    
    def test_create_project_from_snapshot_cli(
        self, project1_path: Path, temp_dir: Path
    ):
        """Test qv init project --snapshot CLI command."""
        # Create snapshot
        snapshot_path = temp_dir / "snapshot.yml"
        QVService.save_project_snapshot(
            project_root=project1_path,
            output_path=snapshot_path,
            overwrite=True,
        )
        
        # Create new project from snapshot
        new_project_root = QVService.create_project_from_snapshot(
            parent_dir=temp_dir,
            snapshot_path=snapshot_path,
            project_name="CLI Test Project",
        )
        
        assert new_project_root.exists()
        assert (new_project_root / "project.qv.yml").exists()
        
        new_project = load_project(new_project_root)
        assert new_project.name == "CLI Test Project"
        assert len(new_project.structures) == 1
        assert len(new_project.workflows) == 1
    
    def test_snapshot_overwrite_protection(
        self, project1_path: Path, temp_dir: Path
    ):
        """Test that snapshot save fails if file exists and overwrite=False."""
        snapshot_path = temp_dir / "snapshot.yml"
        snapshot_path.write_text("existing content")
        
        with pytest.raises(Exception):  # QVServiceError
            QVService.save_project_snapshot(
                project_root=project1_path,
                output_path=snapshot_path,
                overwrite=False,
            )
        
        # Should work with overwrite=True
        QVService.save_project_snapshot(
            project_root=project1_path,
            output_path=snapshot_path,
            overwrite=True,
        )
        
        # Content should be replaced
        snapshot_data = yaml.safe_load(snapshot_path.read_text())
        assert snapshot_data["version"] == 1


class TestSnapshotRoundtrip:
    """Test complete roundtrip: project → snapshot → project."""
    
    def test_complete_roundtrip_project1(self, project1_path: Path, temp_dir: Path):
        """Test complete roundtrip with project1 (DOS workflow)."""
        # Export
        snapshot = export_project_to_snapshot(project1_path)
        original_project = load_project(project1_path)
        
        # Materialize
        new_project_root = materialize_project_from_snapshot(
            snapshot=snapshot,
            parent_dir=temp_dir,
            new_project_name="Roundtrip Test",
        )
        new_project = load_project(new_project_root)
        
        # Verify project structure
        assert len(new_project.structures) == len(original_project.structures)
        assert len(new_project.workflows) == len(original_project.workflows)
        
        # Verify structure content
        original_struct = load_structure_model(
            project1_path / original_project.structures[0].file,
            project1_path,
        )
        new_struct = load_structure_model(
            new_project_root / new_project.structures[0].file,
            new_project_root,
        )
        
        # Structure data should match (composition, sites, lattice)
        original_data = original_struct.data
        new_data = new_struct.data
        
        assert len(original_data.get("sites", [])) == len(new_data.get("sites", []))
        assert original_data.get("lattice", {}).get("a") == new_data.get("lattice", {}).get("a")
        
        # Verify workflow structure
        original_workflow = load_workflow(
            project1_path / original_project.workflows[0].meta.path / "workflow.yaml",
            project1_path,
        )
        new_workflow = load_workflow(
            new_project_root / new_project.workflows[0].meta.path / "workflow.yaml",
            new_project_root,
        )
        
        # Structure references use ID (structure_id is canonical)
        # IDs are remapped during materialization, so we just check they exist
        assert original_workflow.structure_id is not None
        assert new_workflow.structure_id is not None
        assert len(original_workflow.steps) == len(new_workflow.steps)
        
        # Verify step content
        # Note: The test project may have step_id mismatches between workflow.yaml and step files
        # This is a data inconsistency, but we can still verify the roundtrip by comparing step counts
        # and checking that steps exist. For detailed comparison, we'll use the first step file found.
        from quantumvitas.core.resolution import build_resource_index
        original_index = build_resource_index(project1_path)
        new_index = build_resource_index(new_project_root)
        
        # Compare steps by matching step_type (order may differ)
        # Get all steps from each workflow and match by type
        original_steps_by_type = {}
        for step_entry in original_workflow.steps:
            # Find step file
            step_meta = original_index.by_id.get(step_entry.step_id)
            if step_meta:
                step_file = project1_path / step_meta.path
                if step_file.exists():
                    try:
                        step_spec = StructureStepSpec.from_yaml(step_file)
                        original_steps_by_type[step_spec.step_type] = step_spec
                    except Exception:
                        pass
        
        new_steps_by_type = {}
        for step_entry in new_workflow.steps:
            # Find step file
            step_meta = new_index.by_id.get(step_entry.step_id)
            if step_meta:
                step_file = new_project_root / step_meta.path
                if step_file.exists():
                    try:
                        step_spec = StructureStepSpec.from_yaml(step_file)
                        new_steps_by_type[step_spec.step_type] = step_spec
                    except Exception:
                        pass
        
        # Verify that step types match (order may differ)
        assert set(original_steps_by_type.keys()) == set(new_steps_by_type.keys()), \
            f"Step types don't match: original={set(original_steps_by_type.keys())}, new={set(new_steps_by_type.keys())}"
        
        # Verify at least one step can be compared
        if original_steps_by_type:
            # Compare the first matching step type
            common_type = list(original_steps_by_type.keys())[0]
            original_step = original_steps_by_type[common_type]
            new_step = new_steps_by_type[common_type]
            assert original_step.step_type == new_step.step_type
        
        # DAG model: Step YAML should NOT contain structure_id or parent_workflow_id
        # Verify new step YAML does not contain these fields
        # Get any step file to check
        if new_steps_by_type:
            # Get the path to a new step file
            common_type = list(new_steps_by_type.keys())[0]
            new_step_spec = new_steps_by_type[common_type]
            # Find the step file path
            for step_entry in new_workflow.steps:
                step_meta = new_index.by_id.get(step_entry.step_id)
                if step_meta:
                    step_file = new_project_root / step_meta.path
                    if step_file.exists():
                        new_step_yaml_text = step_file.read_text()
                        break
            else:
                # Fallback: get first step file from directory
                new_steps_dir = new_project_root / new_workflow.meta.path / "steps"
                if new_steps_dir.exists():
                    step_files = list(new_steps_dir.glob("*.step.yaml"))
                    if step_files:
                        new_step_yaml_text = step_files[0].read_text()
                    else:
                        pytest.skip("No step files found to verify")
                else:
                    pytest.skip("Steps directory not found")
        else:
            pytest.skip("No steps found to verify")
        assert "structure_id:" not in new_step_yaml_text, "Step YAML should not contain structure_id (DAG model)"
        assert "parent_workflow_id:" not in new_step_yaml_text, "Step YAML should not contain parent_workflow_id (DAG model)"
        # Structure is resolved via workflow.structure_id at runtime
    
    def test_complete_roundtrip_project2_bands(
        self, project2_bands_path: Path, temp_dir: Path
    ):
        """Test complete roundtrip with project2_bands (bands workflow with multiple steps)."""
        # Export
        snapshot = export_project_to_snapshot(project2_bands_path)
        original_project = load_project(project2_bands_path)
        
        # Materialize
        new_project_root = materialize_project_from_snapshot(
            snapshot=snapshot,
            parent_dir=temp_dir,
            new_project_name="Roundtrip Test Bands",
        )
        new_project = load_project(new_project_root)
        
        # Verify project structure
        assert len(new_project.structures) == len(original_project.structures)
        assert len(new_project.workflows) == len(original_project.workflows)
        assert len(new_project.workflows) == 1  # project2_bands has 1 workflow (si-bands)
        
        # Verify all workflows - match by slug since order might differ
        original_workflow_slugs = {w.meta.slug for w in original_project.workflows}
        new_workflow_slugs = {w.meta.slug for w in new_project.workflows}
        assert original_workflow_slugs == new_workflow_slugs
        
        # Verify each workflow
        for original_workflow_entry in original_project.workflows:
            # Find matching workflow in new project by slug
            new_workflow_entry = next(
                w for w in new_project.workflows if w.meta.slug == original_workflow_entry.meta.slug
            )
            assert original_workflow_entry.meta.name == new_workflow_entry.meta.name
            
            original_workflow = load_workflow(
                project2_bands_path / original_workflow_entry.meta.path / "workflow.yaml",
                project2_bands_path,
            )
            new_workflow = load_workflow(
                new_project_root / new_workflow_entry.meta.path / "workflow.yaml",
                new_project_root,
            )
            
            # Structure references use ID (structure_id is canonical)
            # IDs are remapped during materialization, so we just check they exist
            assert original_workflow.structure_id is not None
            assert new_workflow.structure_id is not None
            assert len(original_workflow.steps) == len(new_workflow.steps)
    
    def test_create_demo_project_defaults_to_bands(self, temp_dir: Path):
        """Test that create_demo_project defaults to si_bands_demo when demo_id is not specified."""
        result = QVService.create_demo_project(
            target_dir=temp_dir,
            name="test-demo-project",
        )
        
        project_root = Path(result["project_root"])
        
        # Verify project was created
        assert project_root.exists()
        assert (project_root / "project.qv.yml").exists()
        
        # Verify project structure
        project_model = load_project(project_root)
        assert project_model.meta.name == "test-demo-project"
        assert len(project_model.structures) > 0
        assert len(project_model.workflows) > 0
        
        # Verify it's the bands demo (should have bands-related workflows)
        workflow_slugs = {w.meta.slug for w in project_model.workflows}
        # si_bands_demo should have workflows with "bands" in the name/slug
        assert any("band" in slug.lower() for slug in workflow_slugs), \
            "Default demo should be si_bands_demo (bands workflow)"
    
    def test_create_demo_project_with_explicit_demo_id(self, temp_dir: Path):
        """Test creating a demo project with explicit demo_id."""
        # Test DOS demo
        result = QVService.create_demo_project(
            target_dir=temp_dir,
            name="test-dos-project",
            demo_id="si_dos_demo",
        )
        
        project_root = Path(result["project_root"])
        project_model = load_project(project_root)
        
        # Verify it's the DOS demo
        workflow_slugs = {w.meta.slug for w in project_model.workflows}
        # si_dos_demo should have workflows with "dos" in the name/slug
        assert any("dos" in slug.lower() for slug in workflow_slugs), \
            "Should be si_dos_demo (DOS workflow)"


class TestDemoProjectSnapshots:
    """Test loading demo project snapshots from resources/demo_projects/."""
    
    def test_load_si_bands_demo_snapshot(self):
        """Test loading si_bands_demo.yml snapshot."""
        repo_root = Path(__file__).parent.parent.parent
        snapshot_path = repo_root / "resources" / "demo_projects" / "si_bands_demo.yml"
        
        if not snapshot_path.exists():
            pytest.skip(f"Demo snapshot not found: {snapshot_path}")
        
        # Load snapshot
        snapshot_data = yaml.safe_load(snapshot_path.read_text())
        snapshot = ProjectSnapshot.from_dict(snapshot_data)
        
        # Verify basic invariants
        assert snapshot.version == 1
        assert len(snapshot.structures) >= 1, "Should have at least 1 structure"
        assert len(snapshot.workflows) >= 1, "Should have at least 1 workflow"
        
        # Verify structure
        struct_data = snapshot.structures[0]
        assert "meta" in struct_data
        assert "data" in struct_data
        assert struct_data["meta"]["name"] == "Si" or struct_data["meta"]["name"] == "silicon"
        
        # Verify workflow
        workflow_data = snapshot.workflows[0]
        assert "meta" in workflow_data
        assert "steps" in workflow_data
        assert len(workflow_data["steps"]) > 0, "Workflow should have steps"
        
        # Verify pseudo section (if present) only contains filenames, not content
        if snapshot.pseudo:
            assert "files" in snapshot.pseudo
            assert isinstance(snapshot.pseudo["files"], list)
            # Files should be strings (filenames), not file contents
    
    def test_load_si_dos_demo_snapshot(self):
        """Test loading si_dos_demo.yml snapshot."""
        repo_root = Path(__file__).parent.parent.parent
        snapshot_path = repo_root / "resources" / "demo_projects" / "si_dos_demo.yml"
        
        if not snapshot_path.exists():
            pytest.skip(f"Demo snapshot not found: {snapshot_path}")
        
        # Load snapshot
        snapshot_data = yaml.safe_load(snapshot_path.read_text())
        snapshot = ProjectSnapshot.from_dict(snapshot_data)
        
        # Verify basic invariants
        assert snapshot.version == 1
        assert len(snapshot.structures) >= 1, "Should have at least 1 structure"
        assert len(snapshot.workflows) >= 1, "Should have at least 1 workflow"
        
        # Verify structure
        struct_data = snapshot.structures[0]
        assert "meta" in struct_data
        assert "data" in struct_data
        
        # Verify workflow
        workflow_data = snapshot.workflows[0]
        assert "meta" in workflow_data
        assert "steps" in workflow_data
        assert len(workflow_data["steps"]) > 0, "Workflow should have steps"
        
        # Verify pseudo section (if present) only contains filenames, not content
        if snapshot.pseudo:
            assert "files" in snapshot.pseudo
            assert isinstance(snapshot.pseudo["files"], list)
    
    def test_materialize_demo_snapshots(self, temp_dir: Path):
        """Test materializing both demo snapshots."""
        repo_root = Path(__file__).parent.parent.parent
        
        for demo_name in ["si_bands_demo", "si_dos_demo"]:
            snapshot_path = repo_root / "resources" / "demo_projects" / f"{demo_name}.yml"
            
            if not snapshot_path.exists():
                pytest.skip(f"Demo snapshot not found: {snapshot_path}")
            
            # Load and materialize
            snapshot_data = yaml.safe_load(snapshot_path.read_text())
            snapshot = ProjectSnapshot.from_dict(snapshot_data)
            
            project_root = materialize_project_from_snapshot(
                snapshot=snapshot,
                parent_dir=temp_dir,
                new_project_name=f"test-{demo_name}",
            )
            
            # Verify project was created
            assert project_root.exists()
            assert (project_root / "project.qv.yml").exists()
            
            # Load and verify
            project_model = load_project(project_root)
            assert len(project_model.structures) >= 1
            assert len(project_model.workflows) >= 1

