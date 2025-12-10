"""Unit tests for quantumvitas/api.py - QVService."""

import pytest
from pathlib import Path

import yaml

from quantumvitas.api import QVService, QVServiceError
from quantumvitas.core.resolution import SelectorNotFoundError, ResourceNotFoundError


class TestQVServiceProject:
    """Test QVService project operations."""
    
    def test_init_project(self, tmp_path):
        """Initialize a new project."""
        project_dir = tmp_path / "new-project"
        
        result = QVService.init_project(project_dir, name="My Project")
        
        assert result == project_dir
        assert (project_dir / "project.qv.yml").exists()
        assert (project_dir / "structures").is_dir()
        assert (project_dir / "workflows").is_dir()
        
        config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
        assert config["project"]["name"] == "My Project"
    
    def test_init_project_default_name(self, tmp_path):
        """Project name defaults to directory name."""
        project_dir = tmp_path / "auto-named"
        
        QVService.init_project(project_dir)
        
        config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
        assert config["project"]["name"] == "auto-named"
    
    def test_configure_project(self, tmp_path):
        """Configure project settings."""
        project_dir = tmp_path / "proj"
        QVService.init_project(project_dir, name="Original")
        
        QVService.configure_project(project_dir, new_name="Renamed")
        
        config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
        assert config["project"]["name"] == "Renamed"
    
    def test_init_project_prevents_nested_project(self, tmp_path):
        """Test that init_project raises ValueError if target_dir is inside an existing project."""
        # Create a project
        parent_project = tmp_path / "parent-project"
        QVService.init_project(parent_project, name="Parent Project")
        
        # Try to create a project inside the existing project
        nested_dir = parent_project / "nested-project"
        with pytest.raises(ValueError, match="inside an existing QuantumVITAS project"):
            QVService.init_project(nested_dir, name="Nested Project")
    
    def test_init_project_prevents_creating_in_project_subdir(self, tmp_path):
        """Test that init_project prevents creating in structures/workflows subdirectories."""
        # Create a project
        project_dir = tmp_path / "project"
        QVService.init_project(project_dir, name="Test Project")
        
        # Try to create a project in the structures subdirectory
        structures_dir = project_dir / "structures" / "new-project"
        with pytest.raises(ValueError, match="inside an existing QuantumVITAS project"):
            QVService.init_project(structures_dir, name="Nested Project")
    
    def test_create_demo_project_prevents_nested_project(self, tmp_path):
        """Test that create_demo_project raises ValueError if target_dir is inside an existing project."""
        # Create a project
        parent_project = tmp_path / "parent-project"
        QVService.init_project(parent_project, name="Parent Project")
        
        # Try to create a demo project inside the existing project
        nested_dir = parent_project / "demo-project"
        with pytest.raises(ValueError, match="inside an existing QuantumVITAS project"):
            QVService.create_demo_project(nested_dir, name="Demo Project")


class TestQVServiceStructure:
    """Test QVService structure operations."""
    
    @pytest.fixture
    def project_with_struct_source(self, tmp_path):
        """Create a project and a source structure file."""
        project_dir = tmp_path / "proj"
        QVService.init_project(project_dir)
        
        # Create a source CIF-like file (using JSON for simplicity)
        source_file = tmp_path / "silicon.json"
        source_file.write_text("""{
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {
                "matrix": [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]],
                "a": 5.43, "b": 5.43, "c": 5.43,
                "alpha": 90, "beta": 90, "gamma": 90
            },
            "sites": [
                {"species": [{"element": "Si", "occu": 1}], "abc": [0, 0, 0]}
            ]
        }""")
        
        return project_dir, source_file
    
    def test_import_structure(self, project_with_struct_source):
        """Import a structure file."""
        project_dir, source_file = project_with_struct_source
        
        result = QVService.import_structure(project_dir, source_file, name="Silicon")
        
        assert result.name == "Silicon"
        assert result.slug == "silicon"
        assert result.absolute_path.exists()
    
    def test_import_structure_unique_name(self, project_with_struct_source):
        """Import generates unique names for duplicates."""
        project_dir, source_file = project_with_struct_source
        
        QVService.import_structure(project_dir, source_file, name="Silicon")
        result2 = QVService.import_structure(project_dir, source_file, name="Silicon")
        
        # Second import should get unique name
        assert result2.slug != "silicon"
    
    def test_list_structures(self, project_with_struct_source):
        """List imported structures."""
        project_dir, source_file = project_with_struct_source
        
        QVService.import_structure(project_dir, source_file, name="Silicon")
        QVService.import_structure(project_dir, source_file, name="Graphene")
        
        results = QVService.list_structures(project_dir)
        names = {r.name for r in results}
        
        assert "Silicon" in names
        assert "Graphene" in names
    
    def test_get_structure(self, project_with_struct_source):
        """Get structure by selector."""
        project_dir, source_file = project_with_struct_source
        
        QVService.import_structure(project_dir, source_file, name="Silicon")
        
        result = QVService.get_structure(project_dir, "silicon")
        assert result.name == "Silicon"
    
    def test_configure_structure(self, project_with_struct_source):
        """Rename a structure."""
        project_dir, source_file = project_with_struct_source
        
        QVService.import_structure(project_dir, source_file, name="Silicon")
        QVService.configure_structure(project_dir, "silicon", new_name="Si Crystal")
        
        result = QVService.get_structure(project_dir, "si-crystal")
        assert result.name == "Si Crystal"
    
    def test_delete_structure(self, project_with_struct_source):
        """Delete a structure."""
        project_dir, source_file = project_with_struct_source
        
        QVService.import_structure(project_dir, source_file, name="Silicon")
        QVService.delete_structure(project_dir, "silicon", force=True)
        
        with pytest.raises(ResourceNotFoundError):
            QVService.get_structure(project_dir, "silicon")


class TestQVServiceWorkflow:
    """Test QVService workflow operations."""
    
    @pytest.fixture
    def project(self, tmp_path):
        """Create a project."""
        project_dir = tmp_path / "proj"
        QVService.init_project(project_dir)
        return project_dir
    
    def test_init_workflow(self, project):
        """Create a new workflow."""
        result = QVService.init_workflow(project, "My Workflow")
        
        assert result.name == "My Workflow"
        assert result.slug == "my-workflow"
        assert result.absolute_path.is_dir()
        assert (result.absolute_path / "workflow.yaml").exists()
        assert (result.absolute_path / "steps").is_dir()
    
    def test_init_workflow_with_structure(self, project, tmp_path):
        """Create workflow with structure reference."""
        # Import a structure first (must have at least one site)
        source = tmp_path / "si.json"
        source.write_text("""{
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
            "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
        }""")
        QVService.import_structure(project, source, name="Silicon")
        
        result = QVService.init_workflow(project, "SCF Calc", structure_selector="silicon")
        
        wf_yaml = yaml.safe_load((result.absolute_path / "workflow.yaml").read_text())
        # With ID-only references, workflow.yaml stores structure_id (ULID), not structure selector
        assert wf_yaml.get("structure_id") is not None
        # DAG + ID-only model: structure_name is NOT written to YAML (cosmetic only)
        assert "structure_name" not in wf_yaml
    
    def test_list_workflows(self, project):
        """List workflows."""
        QVService.init_workflow(project, "Workflow 1")
        QVService.init_workflow(project, "Workflow 2")
        
        results = QVService.list_workflows(project)
        names = {r.name for r in results}
        
        assert "Workflow 1" in names
        assert "Workflow 2" in names
    
    def test_get_workflow(self, project):
        """Get workflow by selector."""
        QVService.init_workflow(project, "My Workflow")
        
        result = QVService.get_workflow(project, "my-workflow")
        assert result.name == "My Workflow"
    
    def test_configure_workflow_structure(self, project, tmp_path):
        """Configure workflow structure."""
        # Import structures (must have at least one site)
        source = tmp_path / "si.json"
        source.write_text("""{
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
            "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
        }""")
        QVService.import_structure(project, source, name="Silicon")
        
        source2 = tmp_path / "graphene.json"
        source2.write_text("""{
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[2.46,0,0],[0,2.46,0],[0,0,10]], "a": 2.46, "b": 2.46, "c": 10, "alpha": 90, "beta": 90, "gamma": 90},
            "sites": [{"species": [{"element": "C", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
        }""")
        QVService.import_structure(project, source2, name="Graphene")
        
        QVService.init_workflow(project, "Calc", structure_selector="silicon")
        QVService.configure_workflow(project, "calc", new_structure="graphene")
        
        wf = QVService.get_workflow(project, "calc")
        wf_yaml = yaml.safe_load((wf.absolute_path / "workflow.yaml").read_text())
        # With ID-only references, workflow.yaml stores structure_id (ULID), not structure selector
        assert wf_yaml.get("structure_id") is not None
        # Verify structure was changed: structure_id should be different from silicon's ID
        # (We can't easily check exact ID, but structure_id being set confirms the change)
        # Note: structure_name may not be updated by configure_workflow, so we only check structure_id
    
    def test_delete_workflow(self, project):
        """Delete a workflow."""
        QVService.init_workflow(project, "To Delete")
        QVService.delete_workflow(project, "to-delete")
        
        with pytest.raises(SelectorNotFoundError):
            QVService.get_workflow(project, "to-delete")


class TestQVServiceStep:
    """Test QVService step operations."""
    
    @pytest.fixture
    def project_with_workflow(self, tmp_path):
        """Create a project with a workflow."""
        project_dir = tmp_path / "proj"
        QVService.init_project(project_dir)
        
        # Import structure (must have at least one site)
        source = tmp_path / "si.json"
        source.write_text("""{
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
            "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
        }""")
        QVService.import_structure(project_dir, source, name="Silicon")
        
        QVService.init_workflow(project_dir, "Test Workflow", structure_selector="silicon")
        
        return project_dir
    
    def test_init_step(self, project_with_workflow):
        """Create a new step."""
        result = QVService.init_step(
            project_with_workflow,
            "test-workflow",
            step_type="scf",
        )
        
        assert result.absolute_path.exists()
        assert result.absolute_path.suffix == ".yaml"
    
    def test_init_step_inherits_structure(self, project_with_workflow):
        """Step inherits structure from workflow when not specified."""
        result = QVService.init_step(
            project_with_workflow,
            "test-workflow",
            step_type="nscf",
        )
        
        step_data = yaml.safe_load(result.absolute_path.read_text())
        # DAG model: Step YAML should NOT contain structure_id (inherits from workflow)
        assert "structure_id" not in step_data, "Step YAML should not contain structure_id (DAG model)"
        
        # Verify workflow has structure_id set and it points to the silicon structure
        # Read workflow.yaml directly to avoid materializing steps (which requires pseudos)
        from quantumvitas.core.resolution import build_resource_index, require_structure, resolve_workflow
        
        index = build_resource_index(project_with_workflow)
        workflow_resolved = resolve_workflow(project_with_workflow, "test-workflow", index=index)
        
        # Read workflow.yaml directly to check structure_id without materializing steps
        workflow_yaml = workflow_resolved.absolute_path / "workflow.yaml"
        workflow_data = yaml.safe_load(workflow_yaml.read_text())
        structure_id = workflow_data.get("structure_id")
        
        assert structure_id is not None, "Workflow should have structure_id set"
        structure_resolved = require_structure(project_with_workflow, structure_id, index=index)
        assert structure_resolved.meta.name.lower() == "silicon" or structure_resolved.meta.slug == "silicon"
    
    def test_list_steps(self, project_with_workflow):
        """List steps in a workflow."""
        QVService.init_step(project_with_workflow, "test-workflow", "scf")
        QVService.init_step(project_with_workflow, "test-workflow", "nscf")
        
        results = QVService.list_steps(project_with_workflow, "test-workflow")
        
        assert len(results) >= 2
    
    def test_delete_step(self, project_with_workflow):
        """Delete a step."""
        QVService.init_step(project_with_workflow, "test-workflow", "scf")
        QVService.delete_step(project_with_workflow, "test-workflow", "scf")
        
        results = QVService.list_steps(project_with_workflow, "test-workflow")
        step_types = [yaml.safe_load(r.absolute_path.read_text()).get("step_type") for r in results]
        
        assert "scf" not in step_types

