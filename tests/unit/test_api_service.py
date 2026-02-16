"""Unit tests for quantumvitas/api.py - QVService."""

import pytest
from pathlib import Path

import yaml

from quantumvitas.api import QVService, APIError, get_service
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

    def test_configure_project(self, tmp_path):
        """Configure project settings via project accessor."""
        project_dir = tmp_path / "config-project"
        QVService.init_project(project_dir, name="Original Name")

        # Configure project via project.update_config accessor
        svc = get_service(project_dir)
        svc.project.update_config({"project": {"name": "New Name"}})

        config = yaml.safe_load((project_dir / "project.qv.yml").read_text())
        assert config["project"]["name"] == "New Name"

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

    def test_init_project_allows_tmp_subdir_inside_project(self, tmp_path):
        """Test that init_project allows nested projects under <project>/.tmp/."""
        parent_project = tmp_path / "parent-project"
        QVService.init_project(parent_project, name="Parent Project")

        nested_tmp_dir = parent_project / ".tmp" / "nested-project"
        result = QVService.init_project(nested_tmp_dir, name="Nested Tmp Project")

        assert result == nested_tmp_dir
        assert (nested_tmp_dir / "project.qv.yml").exists()

    def test_create_demo_project_prevents_nested_project(self, tmp_path):
        """Test that create_demo_project raises ValueError if target_dir is inside an existing project."""
        # Create a project first
        parent_project = tmp_path / "parent-project"
        QVService.init_project(parent_project, name="Parent Project")

        # Try to create a demo project inside the existing project
        nested_dir = parent_project / "nested-demo"
        with pytest.raises(ValueError, match="inside an existing QuantumVITAS project"):
            QVService.create_demo_project(nested_dir, name="Nested Demo")


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

        result = QVService(project_dir).structure.import_file(source_file, name="Silicon")

        assert result.meta.name == "Silicon"
        assert result.meta.slug == "silicon"
        # Verify structure file exists using slug (StructureDTO doesn't have absolute_path)
        structure_path = project_dir / "structures" / f"{result.meta.slug}.json"
        assert structure_path.exists()

    def test_import_structure_unique_name(self, project_with_struct_source):
        """Import generates unique names for duplicates."""
        project_dir, source_file = project_with_struct_source

        QVService(project_dir).structure.import_file(source_file, name="Silicon")
        result2 = QVService(project_dir).structure.import_file(source_file, name="Silicon")

        # Second import should get unique name
        assert result2.meta.slug != "silicon"

    def test_list_structures(self, project_with_struct_source):
        """List imported structures using domain API."""
        project_dir, source_file = project_with_struct_source

        QVService(project_dir).structure.import_file(source_file, name="Silicon")
        QVService(project_dir).structure.import_file(source_file, name="Graphene")

        svc = get_service(project_dir)
        results = svc.structure.list()
        names = {r.meta.name for r in results if r.meta}

        assert "Silicon" in names
        assert "Graphene" in names

    def test_get_structure(self, project_with_struct_source):
        """Get structure by selector using domain API."""
        project_dir, source_file = project_with_struct_source

        QVService(project_dir).structure.import_file(source_file, name="Silicon")

        svc = get_service(project_dir)
        result = svc.structure.get("silicon")
        assert result.meta.name == "Silicon"

    def test_configure_structure(self, project_with_struct_source):
        """Rename a structure using domain API."""
        project_dir, source_file = project_with_struct_source

        QVService(project_dir).structure.import_file(source_file, name="Silicon")

        svc = get_service(project_dir)
        svc.structure.update_meta("silicon", new_name="Si Crystal")

        result = svc.structure.get("si-crystal")
        assert result.meta.name == "Si Crystal"

    def test_delete_structure(self, project_with_struct_source):
        """Delete a structure."""
        project_dir, source_file = project_with_struct_source

        # Import a structure
        result = QVService(project_dir).structure.import_file(source_file, name="To Delete")
        structure_ulid = result.meta.ulid

        # Verify structure exists
        svc = get_service(project_dir)
        structures_before = svc.structure.list()
        assert any(s.meta.ulid == structure_ulid for s in structures_before)

        # Delete the structure via domain accessor
        svc.structure.delete(structure_ulid)

        # Verify structure is gone
        structures_after = svc.structure.list()
        assert not any(s.meta.ulid == structure_ulid for s in structures_after)


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
        result = QVService(project).project.init_calculation("My Calculation", engine_family="qe")

        assert result.name == "My Calculation"
        assert result.slug == "my-calculation"
        assert result.absolute_path.is_dir()
        assert (result.absolute_path / "calculation.yaml").exists()
        # Note: steps dir is created lazily when first step is added

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
        QVService(project).structure.import_file(source, name="Silicon")

        result = QVService(project).project.init_calculation("SCF Calc", structure_selector="silicon", engine_family="qe")

        wf_yaml = yaml.safe_load((result.absolute_path / "calculation.yaml").read_text())
        # With ID-only references, calculation.yaml stores structure_ulid (ULID), not structure selector
        assert wf_yaml.get("structure_ulid") is not None
        # DAG + ID-only model: structure_name is NOT written to YAML (cosmetic only)
        assert "structure_name" not in wf_yaml

    def test_list_calculations(self, project):
        """List calculations using domain API."""
        QVService(project).project.init_calculation("Calculation 1", engine_family="qe")
        QVService(project).project.init_calculation("Calculation 2", engine_family="qe")

        svc = get_service(project)
        results = svc.calculation.list()
        names = {r.meta.name for r in results if r.meta}

        assert "Calculation 1" in names
        assert "Calculation 2" in names

    def test_get_calculation(self, project):
        """Get calculation by selector using domain API."""
        QVService(project).project.init_calculation("My Calculation", engine_family="qe")

        svc = get_service(project)
        result = svc.calculation.get("my-calculation")
        assert result.meta.name == "My Calculation"

    def test_configure_calculation_structure(self, project, tmp_path):
        """Configure calculation structure using set_structure."""
        # Import two structures
        source1 = tmp_path / "si1.json"
        source1.write_text("""{
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
            "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
        }""")
        source2 = tmp_path / "si2.json"
        source2.write_text("""{
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5.5,0,0],[0,5.5,0],[0,0,5.5]], "a": 5.5, "b": 5.5, "c": 5.5, "alpha": 90, "beta": 90, "gamma": 90},
            "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
        }""")
        struct1 = QVService(project).structure.import_file(source1, name="Silicon1")
        struct2 = QVService(project).structure.import_file(source2, name="Silicon2")

        # Create calculation with first structure
        calc = QVService(project).project.init_calculation("Test Calc", structure_selector=struct1.meta.ulid, engine_family="qe")

        # Change calculation structure via domain accessor
        svc = get_service(project)
        svc.calculation.set_structure(calc.meta.ulid, struct2.meta.ulid)

        # Verify structure was changed
        calc_yaml = yaml.safe_load((calc.absolute_path / "calculation.yaml").read_text())
        assert calc_yaml.get("structure_ulid") == struct2.meta.ulid

    def test_delete_calculation(self, project):
        """Delete a calculation using domain API."""
        # Create calculation and get its ULID
        calc_resource = QVService(project).project.init_calculation("To Delete", engine_family="qe")
        calculation_ulid = calc_resource.ulid

        # Delete using domain API
        svc = get_service(project)
        svc.calculation.delete(calculation_ulid)

        # Verify deletion: get should raise error
        from quantumvitas.api.errors import NotFoundError
        with pytest.raises(NotFoundError):
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
        QVService(project_dir).structure.import_file(source, name="Silicon")

        QVService(project_dir).project.init_calculation("Test Calculation", structure_selector="silicon", engine_family="qe")

        return project_dir

    def test_init_step(self, project_with_calculation):
        """Create a new step using domain API."""
        svc = get_service(project_with_calculation)
        result = svc.calculation.add_step(
            calc_selector="test-calculation",
            step_type_gen="scf",
        )

        # StepDTO has step_id and meta
        assert result.step_ulid is not None
        # Verify step file was created
        from quantumvitas.core.resolution import require_step
        step_resolved = require_step(project_with_calculation, "test-calculation", result.step_ulid)
        assert step_resolved.absolute_path.exists()
        assert step_resolved.absolute_path.suffix == ".yaml"

    def test_init_step_inherits_structure(self, project_with_calculation):
        """Step inherits structure from calculation when not specified."""
        svc = get_service(project_with_calculation)
        result = svc.calculation.add_step(
            calc_selector="test-calculation",
            step_type_gen="nscf",
        )

        # Read step file to verify no structure_ulid
        from quantumvitas.core.resolution import require_step
        step_resolved = require_step(project_with_calculation, "test-calculation", result.step_ulid)
        step_data = yaml.safe_load(step_resolved.absolute_path.read_text())
        # DAG model: Step YAML should NOT contain structure_ulid (inherits from calculation)
        assert "structure_ulid" not in step_data, "Step YAML should not contain structure_ulid (DAG model)"

        # Verify calculation has structure_ulid set and it points to the silicon structure
        # Read calculation.yaml directly to avoid materializing steps (which requires pseudos)
        from quantumvitas.core.resolution import build_resource_index, require_structure, resolve_calculation

        index = build_resource_index(project_with_calculation)
        calculation_resolved = resolve_calculation(project_with_calculation, "test-calculation", index=index)

        # Read calculation.yaml directly to check structure_ulid without materializing steps
        calculation_yaml = calculation_resolved.absolute_path / "calculation.yaml"
        calculation_data = yaml.safe_load(calculation_yaml.read_text())
        structure_ulid = calculation_data.get("structure_ulid")

        assert structure_ulid is not None, "Calculation should have structure_ulid set"
        structure_resolved = require_structure(project_with_calculation, structure_ulid, index=index)
        assert structure_resolved.meta.name.lower() == "silicon" or structure_resolved.meta.slug == "silicon"

    def test_list_steps(self, project_with_calculation):
        """List steps in a calculation using domain API."""
        svc = get_service(project_with_calculation)
        svc.calculation.add_step(calc_selector="test-calculation", step_type_gen="scf")
        svc.calculation.add_step(calc_selector="test-calculation", step_type_gen="nscf")

        # Use calculation.get() which includes step_ids
        calc_dto = svc.calculation.get("test-calculation")

        assert calc_dto.step_ulids is not None
        assert len(calc_dto.step_ulids) >= 2

    def test_delete_step(self, project_with_calculation):
        """Delete a step using domain API."""
        svc = get_service(project_with_calculation)
        step_result = svc.calculation.add_step(calc_selector="test-calculation", step_type_gen="scf")
        step_id = step_result.step_ulid

        # Delete the step
        svc.calculation.remove_step(calc_selector="test-calculation", step_selector=step_id)

        # Verify step is gone from calculation
        calc_dto = svc.calculation.get("test-calculation")
        step_ids = calc_dto.step_ulids or []

        assert step_id not in step_ids
