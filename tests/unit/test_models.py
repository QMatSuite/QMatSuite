"""Unit tests for core/models.py - Resource data models."""

import pytest
from pathlib import Path

import yaml

from qmatsuite.core.models import (
    CalculationModel,
    CalculationStepEntry,
    ProjectModel,
    StructureEntry,
    CalculationEntry,
    StructureModel,
    load_calculation,
    save_calculation,
    load_project,
    save_project,
    load_structure_model,
    save_structure_model,
    ensure_calculation_meta,
)
from qmatsuite.core.resources import ResourceMeta


class TestCalculationStepEntry:
    """Test CalculationStepEntry dataclass."""
    
    def test_to_dict_minimal(self):
        """Minimal entry only has step_ulid (ULID)."""
        entry = CalculationStepEntry(step_ulid="01TESTSTEPID123456789")
        d = entry.to_dict()
        assert d == {"step_ulid": "01TESTSTEPID123456789"}

    def test_to_dict_full(self):
        """Full entry has all fields (ID-only model)."""
        entry = CalculationStepEntry(
            step_ulid="01TESTSTEPID123456789",
            step_type_spec="qe_scf",
            reference="reference/scf.out",
        )
        d = entry.to_dict()
        assert d["step_ulid"] == "01TESTSTEPID123456789"
        assert d["step_type_spec"] == "qe_scf"
        assert d["reference"] == "reference/scf.out"
        # step_file is NOT written (resolved via registry using step_ulid)
        assert "step_file" not in d
        # legacy id field is NOT written
        assert "id" not in d

    def test_from_dict_valid_dag_entry(self):
        """Parse entry from dict with valid DAG format (step_ulid ULID)."""
        from qmatsuite.core.resources import generate_resource_id

        step_ulid = generate_resource_id()
        data = {"step_ulid": step_ulid, "step_type_spec": "qe_nscf", "input": "raw/nscf.in"}
        entry = CalculationStepEntry.from_dict(data, project_root=Path.cwd())
        assert entry.step_ulid == step_ulid
        assert entry.step_type_spec == "qe_nscf"
        assert entry.input == "raw/nscf.in"
    
    def test_from_dict_legacy_format_raises_error(self):
        """Parse entry from dict with legacy format raises LegacyProjectError."""
        from qmatsuite.core.exceptions import LegacyProjectError

        # Legacy format: has "type" but no "step_type_spec"
        data = {"step_ulid": "01TESTSTEPID123456789", "step_type_gen": "nscf", "file": "raw/nscf.in"}
        with pytest.raises(LegacyProjectError) as exc_info:
            CalculationStepEntry.from_dict(data, project_root=Path.cwd())

        assert "type" in str(exc_info.value).lower() or "legacy" in str(exc_info.value).lower()


class TestCalculationModel:
    """Test CalculationModel dataclass."""
    
    def test_from_dict_minimal(self):
        """Parse minimal calculation dict."""
        data = {"meta": {"ulid": "01ABCDEFGHIJKLMNOPQRSTUV", "name": "Test"}}
        model = CalculationModel.from_dict(data, default_name="Test", default_path="calculations/test")
        
        assert model.meta.ulid == "01ABCDEFGHIJKLMNOPQRSTUV"
        assert model.meta.name == "Test"
        assert model.structure_ulid is None
        assert model.steps == []
    
    def test_from_dict_with_steps(self):
        """Parse calculation with steps (DAG + ULID model)."""
        from qmatsuite.core.resources import generate_resource_id
        
        structure_ulid = generate_resource_id()
        step1_ulid = generate_resource_id()
        step2_ulid = generate_resource_id()
        
        data = {
            "meta": {"ulid": "01ABCDEFGHIJKLMNOPQRSTUV", "name": "DOS Calc", "slug": "dos-calc"},
            "structure_ulid": structure_ulid,
            "steps": [
                {"step_ulid": step1_ulid, "step_type_spec": "qe_scf"},
                {"step_ulid": step2_ulid, "step_type_spec": "qe_nscf"},
            ],
        }
        model = CalculationModel.from_dict(data, default_name="DOS Calc", default_path="calculations/dos-calc")
        
        assert model.structure_ulid == structure_ulid
        assert len(model.steps) == 2
        assert model.steps[0].step_ulid == step1_ulid
        assert model.steps[1].step_ulid == step2_ulid
    
    def test_from_dict_legacy_format_raises_error(self):
        """Legacy format (structure selector without structure_ulid) should raise LegacyProjectError."""
        from qmatsuite.core.exceptions import LegacyProjectError
        
        data = {
            "ulid": "si-dos",
            "calculation": {
                "structure": "si",  # Legacy selector without structure_ulid
                "working_dir": "raw",
            },
            "steps": [],
        }
        with pytest.raises(LegacyProjectError):
            CalculationModel.from_dict(data, default_name="si-dos", default_path="calculations/si-dos")
    
    def test_to_dict_roundtrip(self):
        """Convert to dict and back (ID-only model)."""
        from qmatsuite.core.resources import generate_resource_id
        
        step_ulid = generate_resource_id()
        meta = ResourceMeta(ulid="01CALCULATION_ID_HERE______",
            name="My Calculation",
            slug="my-calculation",
            path="calculations/my-calculation",
            kind="calculation",
        )
        model = CalculationModel(
            meta=meta,
            structure_ulid="01STRUCTURE_ID_HERE_____",
            structure_name="Graphene",
            steps=[CalculationStepEntry(step_ulid=step_ulid, step_type_spec="qe_scf")],
        )
        
        d = model.to_dict()
        assert d["meta"]["ulid"] == "01CALCULATION_ID_HERE______"
        assert d["structure_ulid"] == "01STRUCTURE_ID_HERE_____"
        # DAG + ID-only model: structure_name is NOT written to YAML (cosmetic only)
        assert "structure_name" not in d
        # Legacy structure selector is NOT written (ID-only model)
        assert "structure" not in d
        assert len(d["steps"]) == 1
        
        # Roundtrip
        model2 = CalculationModel.from_dict(d, default_name="fallback", default_path="calculations/fallback")
        assert model2.meta.ulid == model.meta.ulid
        assert model2.structure_ulid == model.structure_ulid
        # structure_name is not persisted, so it will be None after roundtrip
        # (it's cosmetic only, structure_ulid is the canonical reference)


class TestCalculationIO:
    """Test load_calculation and save_calculation functions."""
    
    @pytest.fixture
    def calculation_dir(self, tmp_path):
        """Create a calculation directory with DAG + ULID format."""
        from qmatsuite.core.resources import generate_resource_id
        
        wf_dir = tmp_path / "calculations" / "test-calculation"
        wf_dir.mkdir(parents=True)
        (wf_dir / "steps").mkdir()
        
        structure_ulid = generate_resource_id()
        step_ulid = generate_resource_id()
        
        calculation_yaml = {
            "meta": {
                "ulid": "01CALCULATION_TEST_________",
                "name": "Test Calculation",
                "slug": "test-calculation",
                "path": "calculations/test-calculation",
                "kind": "calculation",
            },
            "structure_ulid": structure_ulid,  # DAG + ULID format
            "steps": [
                {"step_ulid": step_ulid, "step_type_spec": "qe_scf"},  # DAG + ULID format
            ],
        }
        (wf_dir / "calculation.yaml").write_text(yaml.safe_dump(calculation_yaml))
        
        return wf_dir, tmp_path
    
    def test_load_calculation(self, calculation_dir):
        """Load calculation from directory."""
        from qmatsuite.core.resources import generate_resource_id
        
        wf_dir, project_root = calculation_dir
        model = load_calculation(wf_dir, project_root)
        
        assert model.meta.ulid == "01CALCULATION_TEST_________"
        assert model.meta.name == "Test Calculation"
        assert model.structure_ulid is not None  # Should have structure_ulid from YAML
        assert len(model.steps) == 1
        assert model.steps[0].step_ulid is not None  # Should have step_id ULID
        assert len(model.steps[0].step_ulid) == 26  # ULID length
    
    def test_load_calculation_from_yaml_path(self, calculation_dir):
        """Load calculation from yaml file path."""
        wf_dir, project_root = calculation_dir
        model = load_calculation(wf_dir / "calculation.yaml", project_root)
        
        assert model.meta.name == "Test Calculation"
        assert model.structure_ulid is not None  # Should have structure_ulid from YAML
        assert len(model.steps) == 1
        assert model.steps[0].step_ulid is not None  # Should have step_id ULID
    
    def test_save_calculation(self, tmp_path):
        """Save calculation creates yaml file (ID-only model)."""
        wf_dir = tmp_path / "calculations" / "new-calculation"
        wf_dir.mkdir(parents=True)
        
        meta = ResourceMeta(ulid="01NEW_CALCULATION_______",
            name="New Calculation",
            slug="new-calculation",
            path="calculations/new-calculation",
            kind="calculation",
        )
        model = CalculationModel(
            meta=meta,
            structure_ulid="01STRUCTURE_ID_HERE_____",
            structure_name="Graphene",
        )
        
        save_calculation(model, wf_dir)
        
        yaml_path = wf_dir / "calculation.yaml"
        assert yaml_path.exists()
        
        loaded = yaml.safe_load(yaml_path.read_text())
        assert loaded["meta"]["ulid"] == "01NEW_CALCULATION_______"
        assert loaded["structure_ulid"] == "01STRUCTURE_ID_HERE_____"
        # DAG + ID-only constitution: structure_name and structure selector are NOT persisted
        assert "structure_name" not in loaded, "structure_name should not be written to calculation.yaml"
        assert "structure" not in loaded, "structure selector should not be written to calculation.yaml"
    
    def test_roundtrip(self, tmp_path):
        """Save and load produces equivalent model."""
        from qmatsuite.core.resources import generate_resource_id
        
        wf_dir = tmp_path / "calculations" / "roundtrip"
        wf_dir.mkdir(parents=True)
        
        step1_ulid = generate_resource_id()
        step2_ulid = generate_resource_id()
        
        meta = ResourceMeta(ulid="01ROUNDTRIP_ID__________",
            name="Roundtrip Test",
            slug="roundtrip-test",
            path="calculations/roundtrip",
            kind="calculation",
        )
        original = CalculationModel(
            meta=meta,
            structure_ulid="01STRUCTURE_ID_HERE_____",
            structure_name="Silicon",
            mode="normal",
            working_dir="raw",
            steps=[
                CalculationStepEntry(step_ulid=step1_ulid, step_type_spec="qe_scf"),
                CalculationStepEntry(step_ulid=step2_ulid, step_type_spec="qe_nscf"),
            ],
        )
        
        save_calculation(original, wf_dir)
        loaded = load_calculation(wf_dir, tmp_path)
        
        assert loaded.meta.ulid == original.meta.ulid
        assert loaded.meta.name == original.meta.name
        assert loaded.structure_ulid == original.structure_ulid
        # structure_name is in-memory only (not persisted)
        # It may be None after roundtrip if not provided in YAML
        assert len(loaded.steps) == len(original.steps)
        
        # Verify on-disk YAML only contains structure_ulid (DAG + ID-only constitution)
        yaml_path = wf_dir / "calculation.yaml"
        on_disk = yaml.safe_load(yaml_path.read_text())
        assert "structure_ulid" in on_disk
        assert "structure_name" not in on_disk, "structure_name should not be persisted to calculation.yaml"
        assert "structure" not in on_disk, "structure selector should not be persisted to calculation.yaml"


class TestProjectModel:
    """Test ProjectModel dataclass."""
    
    def test_from_dict_minimal(self):
        """Parse minimal project dict."""
        data = {"project": {"name": "My Project"}}
        model = ProjectModel.from_dict(data, root=Path("/test"))
        
        assert model.name == "My Project"
        assert model.structures == []
        assert model.calculations == []
    
    def test_from_dict_with_resources(self):
        """Parse project with structures and calculations."""
        data = {
            "project": {
                "name": "Full Project",
                "meta": {"ulid": "01PROJECT_ID_HERE_______"},
            },
            "structures": [
                {"name": "Silicon", "file": "structures/si.json"},
            ],
            "calculations": [
                {"name": "DOS Calc", "path": "calculations/dos"},
            ],
        }
        model = ProjectModel.from_dict(data, root=Path("/test"))
        
        assert len(model.structures) == 1
        assert model.structures[0].meta.name == "Silicon"
        
        assert len(model.calculations) == 1
        assert model.calculations[0].meta.name == "DOS Calc"
    
    def test_get_structure_by_selector(self):
        """Find structure by various selectors."""
        data = {
            "project": {"name": "Test"},
            "structures": [
                {
                    "name": "Silicon",
                    "file": "structures/si.json",
                    "meta": {"ulid": "01SILICON_ID_HERE_______", "slug": "silicon"},
                },
            ],
            "calculations": [],
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
                    "ulid": "01PROJECT_TEST__________",
                    "name": "Test Project",
                    "slug": "test-project",
                    "path": ".",
                    "kind": "project",
                },
            },
            "structures": [
                {"name": "Silicon", "file": "structures/si.json"},
            ],
            "calculations": [
                {"name": "DOS", "path": "calculations/dos"},
            ],
        }
        (project_root / "project.qms.yml").write_text(yaml.safe_dump(config))
        
        return project_root
    
    def test_load_project(self, project_dir):
        """Load project from directory."""
        model = load_project(project_dir)
        
        assert model.meta.ulid == "01PROJECT_TEST__________"
        assert model.name == "Test Project"
        assert len(model.structures) == 1
        assert len(model.calculations) == 1
    
    def test_save_project(self, tmp_path):
        """Save project creates yaml file."""
        project_root = tmp_path / "new-project"
        project_root.mkdir()
        
        meta = ResourceMeta(ulid="01NEW_PROJECT___________",
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
        
        config_file = project_root / "project.qms.yml"
        assert config_file.exists()
        
        loaded = yaml.safe_load(config_file.read_text())
        assert loaded["project"]["meta"]["ulid"] == "01NEW_PROJECT___________"


class TestStructureModel:
    """Test StructureModel dataclass."""
    
    def test_from_dict_with_meta(self):
        """Parse structure with meta."""
        data = {
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[5, 0, 0], [0, 5, 0], [0, 0, 5]]},
            "meta": {
                "ulid": "01STRUCTURE_ID__________",
                "name": "Silicon",
                "slug": "silicon",
                "path": "structures/si.json",
                "kind": "structure",
            },
        }
        model = StructureModel.from_dict(data, default_name="default", default_path="structures/default.json")
        
        assert model.meta.ulid == "01STRUCTURE_ID__________"
        assert model.meta.name == "Silicon"
        assert "@module" in model.data
        assert "meta" not in model.data  # Meta should be separate
    
    def test_to_dict_includes_meta(self):
        """to_dict includes meta in output."""
        meta = ResourceMeta(ulid="01TEST_STRUCTURE________",
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
        assert d["meta"]["ulid"] == "01TEST_STRUCTURE________"
        assert d["@module"] == "test"


class TestEnsureCalculationMeta:
    """Test ensure_calculation_meta function."""
    
    def test_creates_meta_for_new_calculation(self, tmp_path):
        """Creates meta and calculation.yaml for new calculation."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        calculation_dir = project_root / "calculations" / "new-calculation"
        calculation_dir.mkdir(parents=True)
        
        meta = ensure_calculation_meta(calculation_dir, project_root, name="New Calculation")
        
        assert len(meta.ulid) == 26  # ULID length
        assert meta.name == "New Calculation"
        assert meta.slug == "new-calculation"
        assert (calculation_dir / "calculation.yaml").exists()
    
    def test_preserves_existing_meta(self, tmp_path):
        """Preserves meta from existing calculation.yaml (DAG + ULID format)."""
        from qmatsuite.core.resources import generate_resource_id
        
        project_root = tmp_path / "project"
        project_root.mkdir()
        calculation_dir = project_root / "calculations" / "existing"
        calculation_dir.mkdir(parents=True)
        
        calculation_ulid = generate_resource_id()
        structure_ulid = generate_resource_id()
        
        # Create existing calculation.yaml with DAG + ULID format
        existing_yaml = {
            "meta": {
                "ulid": calculation_ulid,  # Valid 26-char ULID
                "name": "Existing Calculation",
                "slug": "existing",
                "path": "calculations/existing",
                "kind": "calculation",
            },
            "structure_ulid": structure_ulid,  # DAG + ULID format
            "steps": [],  # Empty steps list
        }
        (calculation_dir / "calculation.yaml").write_text(yaml.safe_dump(existing_yaml))
        
        meta = ensure_calculation_meta(calculation_dir, project_root)
        
        assert meta.ulid == calculation_ulid
        assert meta.name == "Existing Calculation"

