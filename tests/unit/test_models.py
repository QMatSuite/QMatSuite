"""Unit tests for core/models.py - Resource data models."""

import pytest
from pathlib import Path

import yaml

from quantumvitas.core.models import (
    WorkflowModel,
    WorkflowStepEntry,
    ProjectModel,
    StructureEntry,
    WorkflowEntry,
    StructureModel,
    load_workflow,
    save_workflow,
    load_project,
    save_project,
    load_structure_model,
    save_structure_model,
    ensure_workflow_meta,
)
from quantumvitas.core.resources import ResourceMeta


class TestWorkflowStepEntry:
    """Test WorkflowStepEntry dataclass."""
    
    def test_to_dict_minimal(self):
        """Minimal entry only has step_id (ULID)."""
        entry = WorkflowStepEntry(step_id="01TESTSTEPID123456789")
        d = entry.to_dict()
        assert d == {"step_id": "01TESTSTEPID123456789"}
    
    def test_to_dict_full(self):
        """Full entry has all fields (ID-only model)."""
        entry = WorkflowStepEntry(
            step_id="01TESTSTEPID123456789",
            type="scf",
            reference="reference/scf.out",
        )
        d = entry.to_dict()
        assert d["step_id"] == "01TESTSTEPID123456789"
        assert d["type"] == "scf"
        assert d["reference"] == "reference/scf.out"
        # step_file is NOT written (resolved via registry using step_id)
        assert "step_file" not in d
        # legacy id field is NOT written
        assert "id" not in d
    
    def test_from_dict(self):
        """Parse entry from dict."""
        data = {"id": "nscf", "type": "nscf", "file": "raw/nscf.in"}
        entry = WorkflowStepEntry.from_dict(data)
        assert entry.id == "nscf"
        assert entry.type == "nscf"
        assert entry.input == "raw/nscf.in"  # "file" becomes "input"


class TestWorkflowModel:
    """Test WorkflowModel dataclass."""
    
    def test_from_dict_minimal(self):
        """Parse minimal workflow dict."""
        data = {"meta": {"id": "01ABCDEFGHIJKLMNOPQRSTUV", "name": "Test"}}
        model = WorkflowModel.from_dict(data, default_name="Test", default_path="workflows/test")
        
        assert model.meta.id == "01ABCDEFGHIJKLMNOPQRSTUV"
        assert model.meta.name == "Test"
        assert model.structure is None
        assert model.steps == []
    
    def test_from_dict_with_steps(self):
        """Parse workflow with steps."""
        data = {
            "meta": {"id": "01ABC", "name": "DOS Calc", "slug": "dos-calc"},
            "structure": "silicon",
            "steps": [
                {"id": "scf", "type": "scf"},
                {"id": "nscf", "type": "nscf"},
            ],
        }
        model = WorkflowModel.from_dict(data, default_name="DOS Calc", default_path="workflows/dos-calc")
        
        assert model.structure == "silicon"
        assert len(model.steps) == 2
        assert model.steps[0].id == "scf"
        assert model.steps[1].id == "nscf"
    
    def test_from_dict_legacy_format(self):
        """Parse legacy format where structure is in 'workflow' section."""
        data = {
            "id": "si-dos",
            "workflow": {
                "structure": "si",
                "working_dir": "raw",
            },
            "steps": [],
        }
        model = WorkflowModel.from_dict(data, default_name="si-dos", default_path="workflows/si-dos")
        
        assert model.structure == "si"
        assert model.working_dir == "raw"
    
    def test_to_dict_roundtrip(self):
        """Convert to dict and back (ID-only model)."""
        meta = ResourceMeta(
            id="01WORKFLOW_ID_HERE______",
            name="My Workflow",
            slug="my-workflow",
            path="workflows/my-workflow",
            kind="workflow",
        )
        model = WorkflowModel(
            meta=meta,
            structure_id="01STRUCTURE_ID_HERE_____",
            structure_name="Graphene",
            structure="graphene",  # Legacy field (not written to YAML)
            steps=[WorkflowStepEntry(step_id="01STEP_ID_HERE________", type="scf")],
        )
        
        d = model.to_dict()
        assert d["meta"]["id"] == "01WORKFLOW_ID_HERE______"
        assert d["structure_id"] == "01STRUCTURE_ID_HERE_____"
        # DAG + ID-only model: structure_name is NOT written to YAML (cosmetic only)
        assert "structure_name" not in d
        # Legacy structure selector is NOT written (ID-only model)
        assert "structure" not in d
        assert len(d["steps"]) == 1
        
        # Roundtrip
        model2 = WorkflowModel.from_dict(d, default_name="fallback", default_path="workflows/fallback")
        assert model2.meta.id == model.meta.id
        assert model2.structure_id == model.structure_id
        # structure_name is not persisted, so it will be None after roundtrip
        # (it's cosmetic only, structure_id is the canonical reference)


class TestWorkflowIO:
    """Test load_workflow and save_workflow functions."""
    
    @pytest.fixture
    def workflow_dir(self, tmp_path):
        """Create a workflow directory."""
        wf_dir = tmp_path / "workflows" / "test-workflow"
        wf_dir.mkdir(parents=True)
        (wf_dir / "steps").mkdir()
        
        workflow_yaml = {
            "meta": {
                "id": "01WORKFLOW_TEST_________",
                "name": "Test Workflow",
                "slug": "test-workflow",
                "path": "workflows/test-workflow",
                "kind": "workflow",
            },
            "structure": "silicon",
            "steps": [
                {"id": "scf", "type": "scf", "step_file": "steps/scf.step.yaml"},
            ],
        }
        (wf_dir / "workflow.yaml").write_text(yaml.safe_dump(workflow_yaml))
        
        return wf_dir, tmp_path
    
    def test_load_workflow(self, workflow_dir):
        """Load workflow from directory."""
        wf_dir, project_root = workflow_dir
        model = load_workflow(wf_dir, project_root)
        
        assert model.meta.id == "01WORKFLOW_TEST_________"
        assert model.meta.name == "Test Workflow"
        assert model.structure == "silicon"
        assert len(model.steps) == 1
    
    def test_load_workflow_from_yaml_path(self, workflow_dir):
        """Load workflow from yaml file path."""
        wf_dir, project_root = workflow_dir
        model = load_workflow(wf_dir / "workflow.yaml", project_root)
        
        assert model.meta.name == "Test Workflow"
    
    def test_save_workflow(self, tmp_path):
        """Save workflow creates yaml file (ID-only model)."""
        wf_dir = tmp_path / "workflows" / "new-workflow"
        wf_dir.mkdir(parents=True)
        
        meta = ResourceMeta(
            id="01NEW_WORKFLOW__________",
            name="New Workflow",
            slug="new-workflow",
            path="workflows/new-workflow",
            kind="workflow",
        )
        model = WorkflowModel(
            meta=meta,
            structure_id="01STRUCTURE_ID_HERE_____",
            structure_name="Graphene",
            structure="graphene",  # Legacy field (not written to YAML)
        )
        
        save_workflow(model, wf_dir)
        
        yaml_path = wf_dir / "workflow.yaml"
        assert yaml_path.exists()
        
        loaded = yaml.safe_load(yaml_path.read_text())
        assert loaded["meta"]["id"] == "01NEW_WORKFLOW__________"
        assert loaded["structure_id"] == "01STRUCTURE_ID_HERE_____"
        # DAG + ID-only constitution: structure_name and structure selector are NOT persisted
        assert "structure_name" not in loaded, "structure_name should not be written to workflow.yaml"
        assert "structure" not in loaded, "structure selector should not be written to workflow.yaml"
    
    def test_roundtrip(self, tmp_path):
        """Save and load produces equivalent model."""
        wf_dir = tmp_path / "workflows" / "roundtrip"
        wf_dir.mkdir(parents=True)
        
        meta = ResourceMeta(
            id="01ROUNDTRIP_ID__________",
            name="Roundtrip Test",
            slug="roundtrip-test",
            path="workflows/roundtrip",
            kind="workflow",
        )
        original = WorkflowModel(
            meta=meta,
            structure_id="01STRUCTURE_ID_HERE_____",
            structure_name="Silicon",
            structure="silicon",  # Legacy field (not written to YAML)
            mode="normal",
            working_dir="raw",
            steps=[
                WorkflowStepEntry(step_id="01STEP_SCF_ID_HERE_____", type="scf"),
                WorkflowStepEntry(step_id="01STEP_NSCF_ID_HERE____", type="nscf"),
            ],
        )
        
        save_workflow(original, wf_dir)
        loaded = load_workflow(wf_dir, tmp_path)
        
        assert loaded.meta.id == original.meta.id
        assert loaded.meta.name == original.meta.name
        assert loaded.structure_id == original.structure_id
        # structure_name is in-memory only (not persisted)
        # It may be None after roundtrip if not provided in YAML
        assert len(loaded.steps) == len(original.steps)
        
        # Verify on-disk YAML only contains structure_id (DAG + ID-only constitution)
        yaml_path = wf_dir / "workflow.yaml"
        on_disk = yaml.safe_load(yaml_path.read_text())
        assert "structure_id" in on_disk
        assert "structure_name" not in on_disk, "structure_name should not be persisted to workflow.yaml"
        assert "structure" not in on_disk, "structure selector should not be persisted to workflow.yaml"


class TestProjectModel:
    """Test ProjectModel dataclass."""
    
    def test_from_dict_minimal(self):
        """Parse minimal project dict."""
        data = {"project": {"name": "My Project"}}
        model = ProjectModel.from_dict(data, root=Path("/test"))
        
        assert model.name == "My Project"
        assert model.structures == []
        assert model.workflows == []
    
    def test_from_dict_with_resources(self):
        """Parse project with structures and workflows."""
        data = {
            "project": {
                "name": "Full Project",
                "meta": {"id": "01PROJECT_ID_HERE_______"},
            },
            "structures": [
                {"name": "Silicon", "file": "structures/si.json"},
            ],
            "workflows": [
                {"name": "DOS Calc", "path": "workflows/dos"},
            ],
        }
        model = ProjectModel.from_dict(data, root=Path("/test"))
        
        assert len(model.structures) == 1
        assert model.structures[0].meta.name == "Silicon"
        
        assert len(model.workflows) == 1
        assert model.workflows[0].meta.name == "DOS Calc"
    
    def test_get_structure_by_selector(self):
        """Find structure by various selectors."""
        data = {
            "project": {"name": "Test"},
            "structures": [
                {
                    "name": "Silicon",
                    "file": "structures/si.json",
                    "meta": {"id": "01SILICON_ID_HERE_______", "slug": "silicon"},
                },
            ],
            "workflows": [],
        }
        model = ProjectModel.from_dict(data, root=Path("/test"))
        
        # By slug
        assert model.get_structure_by_selector("silicon") is not None
        # By name (case-insensitive)
        assert model.get_structure_by_selector("Silicon") is not None
        assert model.get_structure_by_selector("SILICON") is not None
        # By ULID
        assert model.get_structure_by_selector("01SILICON_ID_HERE_______") is not None
        # Not found
        assert model.get_structure_by_selector("graphene") is None


class TestProjectIO:
    """Test load_project and save_project functions."""
    
    @pytest.fixture
    def project_dir(self, tmp_path):
        """Create a project directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        
        config = {
            "project": {
                "name": "Test Project",
                "meta": {
                    "id": "01PROJECT_TEST__________",
                    "name": "Test Project",
                    "slug": "test-project",
                    "path": ".",
                    "kind": "project",
                },
            },
            "structures": [
                {"name": "Silicon", "file": "structures/si.json"},
            ],
            "workflows": [
                {"name": "DOS", "path": "workflows/dos"},
            ],
        }
        (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
        
        return project_root
    
    def test_load_project(self, project_dir):
        """Load project from directory."""
        model = load_project(project_dir)
        
        assert model.meta.id == "01PROJECT_TEST__________"
        assert model.name == "Test Project"
        assert len(model.structures) == 1
        assert len(model.workflows) == 1
    
    def test_save_project(self, tmp_path):
        """Save project creates yaml file."""
        project_root = tmp_path / "new-project"
        project_root.mkdir()
        
        meta = ResourceMeta(
            id="01NEW_PROJECT___________",
            name="New Project",
            slug="new-project",
            path=".",
            kind="project",
        )
        model = ProjectModel(
            meta=meta,
            root=project_root,
        )
        
        save_project(model)
        
        config_file = project_root / "project.qv.yml"
        assert config_file.exists()
        
        loaded = yaml.safe_load(config_file.read_text())
        assert loaded["project"]["meta"]["id"] == "01NEW_PROJECT___________"


class TestStructureModel:
    """Test StructureModel dataclass."""
    
    def test_from_dict_with_meta(self):
        """Parse structure with meta."""
        data = {
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5, 0, 0], [0, 5, 0], [0, 0, 5]]},
            "meta": {
                "id": "01STRUCTURE_ID__________",
                "name": "Silicon",
                "slug": "silicon",
                "path": "structures/si.json",
                "kind": "structure",
            },
        }
        model = StructureModel.from_dict(data, default_name="default", default_path="structures/default.json")
        
        assert model.meta.id == "01STRUCTURE_ID__________"
        assert model.meta.name == "Silicon"
        assert "@module" in model.data
        assert "meta" not in model.data  # Meta should be separate
    
    def test_to_dict_includes_meta(self):
        """to_dict includes meta in output."""
        meta = ResourceMeta(
            id="01TEST_STRUCTURE________",
            name="Test",
            slug="test",
            path="structures/test.json",
            kind="structure",
        )
        model = StructureModel(
            meta=meta,
            data={"@module": "test", "lattice": {}},
        )
        
        d = model.to_dict()
        assert "meta" in d
        assert d["meta"]["id"] == "01TEST_STRUCTURE________"
        assert d["@module"] == "test"


class TestEnsureWorkflowMeta:
    """Test ensure_workflow_meta function."""
    
    def test_creates_meta_for_new_workflow(self, tmp_path):
        """Creates meta and workflow.yaml for new workflow."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        workflow_dir = project_root / "workflows" / "new-workflow"
        workflow_dir.mkdir(parents=True)
        
        meta = ensure_workflow_meta(workflow_dir, project_root, name="New Workflow")
        
        assert len(meta.id) == 26  # ULID length
        assert meta.name == "New Workflow"
        assert meta.slug == "new-workflow"
        assert (workflow_dir / "workflow.yaml").exists()
    
    def test_preserves_existing_meta(self, tmp_path):
        """Preserves meta from existing workflow.yaml."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        workflow_dir = project_root / "workflows" / "existing"
        workflow_dir.mkdir(parents=True)
        
        # Create existing workflow.yaml with valid ULID (26 uppercase alphanumeric)
        existing_yaml = {
            "meta": {
                "id": "01JGWX6YZ0ABCDEFGHIJKLMNOP",  # Valid 26-char ULID
                "name": "Existing Workflow",
                "slug": "existing",
                "path": "workflows/existing",
                "kind": "workflow",
            },
            "structure": "silicon",
        }
        (workflow_dir / "workflow.yaml").write_text(yaml.safe_dump(existing_yaml))
        
        meta = ensure_workflow_meta(workflow_dir, project_root)
        
        assert meta.id == "01JGWX6YZ0ABCDEFGHIJKLMNOP"
        assert meta.name == "Existing Workflow"

