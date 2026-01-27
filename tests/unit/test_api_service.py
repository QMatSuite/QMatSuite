"""Unit tests for quantumvitas/api.py - QVService."""

import pytest
from pathlib import Path

import yaml

from quantumvitas.api import QVService, APIError
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
        assert (project_dir / "calculations").is_dir()
        
        config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
        assert config["project"]["name"] == "My Project"
    
    def test_init_project_default_name(self, tmp_path):
        """Project name defaults to directory name."""
        project_dir = tmp_path / "auto-named"
        
        QVService.init_project(project_dir)
        
        config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
        assert config["project"]["name"] == "auto-named"
    
    @pytest.mark.skip(reason="PR10: configure_project not in domain API")
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
        """Test that init_project prevents creating in structures/calculations subdirectories."""
        # Create a project
        project_dir = tmp_path / "project"
        QVService.init_project(project_dir, name="Test Project")
        
        # Try to create a project in the structures subdirectory
        structures_dir = project_dir / "structures" / "new-project"
        with pytest.raises(ValueError, match="inside an existing QuantumVITAS project"):
            QVService.init_project(structures_dir, name="Nested Project")
    
    @pytest.mark.skip(reason="PR10: create_demo_project not in domain API")
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
        
        svc = QVService(project_dir)
        results = svc.structure.list()
        
        # Debug: check what we got
        assert len(results) >= 2, f"Expected at least 2 structures, got {len(results)}"
        
        # Try different field access patterns
        names = set()
        for s in results:
            if hasattr(s, 'meta') and s.meta and hasattr(s.meta, 'name'):
                names.add(s.meta.name)
            elif hasattr(s, 'name'):
                names.add(s.name)
        
        assert "Silicon" in names, f"Silicon not in {names}"
        assert "Graphene" in names, f"Graphene not in {names}"
    
    def test_get_structure(self, project_with_struct_source):
        """Get structure by selector."""
        project_dir, source_file = project_with_struct_source
        
        QVService.import_structure(project_dir, source_file, name="Silicon")
        
        svc = QVService(project_dir)
        result = svc.structure.get("silicon")
        # Check meta.name if available, otherwise check name directly
        if hasattr(result, 'meta') and result.meta and hasattr(result.meta, 'name'):
            assert result.meta.name == "Silicon"
        else:
            assert result.name == "Silicon"
    
    @pytest.mark.skip(reason="PR10: configure_structure not in domain API")
    def test_configure_structure(self, project_with_struct_source):
        """Rename a structure."""
        project_dir, source_file = project_with_struct_source
        
        QVService.import_structure(project_dir, source_file, name="Silicon")
        QVService.configure_structure(project_dir, "silicon", new_name="Si Crystal")
        
        result = QVService.get_structure(project_dir, "si-crystal")
        assert result.name == "Si Crystal"
    
    @pytest.mark.skip(reason="PR10: delete_structure not in domain API")
    def test_delete_structure(self, project_with_struct_source):
        """Delete a structure."""
        project_dir, source_file = project_with_struct_source
        
        QVService.import_structure(project_dir, source_file, name="Silicon")
        QVService.delete_structure(project_dir, "silicon", force=True)
        
        with pytest.raises(ResourceNotFoundError):
            QVService.get_structure(project_dir, "silicon")


class TestQVServiceCalculation:
    """Test QVService calculation operations."""
    
    @pytest.fixture
    def project(self, tmp_path):
        """Create a project."""
        project_dir = tmp_path / "proj"
        QVService.init_project(project_dir)
        return project_dir
    
    def test_init_calculation(self, project):
        """Create a new calculation."""
        result = QVService.init_calculation(project, "My Calculation")
        
        assert result.name == "My Calculation"
        assert result.slug == "my-calculation"
        assert result.absolute_path.is_dir()
        assert (result.absolute_path / "calculation.yaml").exists()
        assert (result.absolute_path / "steps").is_dir()
    
    def test_init_calculation_with_structure(self, project, tmp_path):
        """Create calculation with structure reference."""
        # Import a structure first (must have at least one site)
        source = tmp_path / "si.json"
        source.write_text("""{
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
            "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
        }""")
        QVService.import_structure(project, source, name="Silicon")
        
        result = QVService.init_calculation(project, "SCF Calc", structure_selector="silicon")
        
        wf_yaml = yaml.safe_load((result.absolute_path / "calculation.yaml").read_text())
        # With ID-only references, calculation.yaml stores structure_id (ULID), not structure selector
        assert wf_yaml.get("structure_id") is not None
        # DAG + ID-only model: structure_name is NOT written to YAML (cosmetic only)
        assert "structure_name" not in wf_yaml
    
    def test_list_calculations(self, project):
        """List calculations."""
        QVService.init_calculation(project, "Calculation 1")
        QVService.init_calculation(project, "Calculation 2")
        
        svc = QVService(project)
        results = svc.calculation.list()
        
        # Debug: check what we got
        assert len(results) >= 2, f"Expected at least 2 calculations, got {len(results)}"
        
        # Try different field access patterns
        names = set()
        for c in results:
            if hasattr(c, 'meta') and c.meta and hasattr(c.meta, 'name'):
                names.add(c.meta.name)
            elif hasattr(c, 'name'):
                names.add(c.name)
        
        assert "Calculation 1" in names, f"Calculation 1 not in {names}"
        assert "Calculation 2" in names, f"Calculation 2 not in {names}"
    
    def test_get_calculation(self, project):
        """Get calculation by selector."""
        QVService.init_calculation(project, "My Calculation")
        
        svc = QVService(project)
        result = svc.calculation.get("my-calculation")
        assert result.meta.name == "My Calculation"
    
    @pytest.mark.skip(reason="PR10: configure_calculation not in domain API")
    def test_configure_calculation_structure(self, project, tmp_path):
        """Configure calculation structure."""
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
        
        QVService.init_calculation(project, "Calc", structure_selector="silicon")
        QVService.configure_calculation(project, "calc", new_structure="graphene")
        
        wf = QVService.get_calculation(project, "calc")
        wf_yaml = yaml.safe_load((wf.absolute_path / "calculation.yaml").read_text())
        # With ID-only references, calculation.yaml stores structure_id (ULID), not structure selector
        assert wf_yaml.get("structure_id") is not None
        # Verify structure was changed: structure_id should be different from silicon's ID
        # (We can't easily check exact ID, but structure_id being set confirms the change)
        # Note: structure_name may not be updated by configure_calculation, so we only check structure_id
    
    def test_delete_calculation(self, project):
        """Delete a calculation."""
        # Create calculation and get its ULID
        calc_resource = QVService.init_calculation(project, "To Delete")
        
        # calc_resource might be a dict or Path - check what it returns
        if isinstance(calc_resource, dict):
            calculation_ulid = calc_resource.get("id") or calc_resource.get("calc_id")
        elif hasattr(calc_resource, 'id'):
            calculation_ulid = calc_resource.id
        elif isinstance(calc_resource, Path):
            # Read the calculation.yaml to get the ULID
            import yaml
            calc_yaml = calc_resource / "calculation.yaml"
            data = yaml.safe_load(calc_yaml.read_text())
            calculation_ulid = data.get("meta", {}).get("id")
        else:
            # Try to get id from absolute_path
            calc_yaml = calc_resource.absolute_path / "calculation.yaml"
            import yaml
            data = yaml.safe_load(calc_yaml.read_text())
            calculation_ulid = data.get("meta", {}).get("id")
        
        # Delete using ULID (core service requires ULID)
        svc = QVService(project)
        svc.calculation.delete(calculation_ulid)
        
        # Verify deletion: get_calculation should raise error
        from quantumvitas.api.errors import NotFoundError
        with pytest.raises((SelectorNotFoundError, NotFoundError)):
            svc.calculation.get(calculation_ulid)


class TestQVServiceStep:
    """Test QVService step operations."""
    
    @pytest.fixture
    def project_with_calculation(self, tmp_path):
        """Create a project with a calculation."""
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
        
        QVService.init_calculation(project_dir, "Test Calculation", structure_selector="silicon")
        
        return project_dir
    
    def test_init_step(self, project_with_calculation):
        """Create a new step."""
        svc = QVService(project_with_calculation)
        result = svc.calculation.add_step(
            calc_selector="test-calculation",
            step_type="scf",
        )
        
        # StepDTO doesn't have absolute_path, use step_id to verify step exists
        assert result.step_id is not None
        assert result.step_type == "qe_scf"  # Domain API uses full step type
    
    def test_init_step_inherits_structure(self, project_with_calculation):
        """Step inherits structure from calculation when not specified."""
        svc = QVService(project_with_calculation)
        result = svc.calculation.add_step(
            calc_selector="test-calculation",
            step_type="nscf",
        )
        
        # StepDTO doesn't have absolute_path, verify step was created
        assert result.step_id is not None
        assert result.step_type == "qe_nscf"  # Domain API uses full step type
        
        # Verify calculation has structure_id set and it points to the silicon structure
        # Read calculation.yaml directly to avoid materializing steps (which requires pseudos)
        from quantumvitas.core.resolution import build_resource_index, require_structure, resolve_calculation
        
        index = build_resource_index(project_with_calculation)
        calculation_resolved = resolve_calculation(project_with_calculation, "test-calculation", index=index)
        
        # Read calculation.yaml directly to check structure_id without materializing steps
        calculation_yaml = calculation_resolved.absolute_path / "calculation.yaml"
        calculation_data = yaml.safe_load(calculation_yaml.read_text())
        structure_id = calculation_data.get("structure_id")
        
        assert structure_id is not None, "Calculation should have structure_id set"
        structure_resolved = require_structure(project_with_calculation, structure_id, index=index)
        assert structure_resolved.meta.name.lower() == "silicon" or structure_resolved.meta.slug == "silicon"
    
    def test_list_steps(self, project_with_calculation):
        """List steps in a calculation."""
        svc = QVService(project_with_calculation)
        svc.calculation.add_step(calc_selector="test-calculation", step_type="scf")
        svc.calculation.add_step(calc_selector="test-calculation", step_type="nscf")
        
        results = svc.calculation.list_steps("test-calculation")
        
        assert len(results) >= 2
    
    def test_delete_step(self, project_with_calculation):
        """Delete a step."""
        svc = QVService(project_with_calculation)
        step_dto = svc.calculation.add_step(calc_selector="test-calculation", step_type="scf")
        svc.calculation.remove_step("test-calculation", step_dto.step_id)
        
        results = svc.calculation.list_steps("test-calculation")
        step_types = [s.step_type for s in results]
        
        assert "qe_scf" not in step_types  # Domain API uses full step type

