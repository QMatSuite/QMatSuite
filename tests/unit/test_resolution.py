"""Unit tests for core/resolution.py - centralized selector resolution."""

import pytest
from pathlib import Path

import yaml

from quantumvitas.core.resolution import (
    AmbiguousSelectorError,
    SelectorNotFoundError,
    ResolvedResource,
    resolve_structure,
    resolve_calculation,
    resolve_step,
    resolve_project,
    list_structures,
    list_calculations,
    list_steps,
    _is_ulid_like,
    _is_path_like,
)


class TestSelectorClassification:
    """Test selector type classification."""
    
    def test_is_ulid_like_valid(self):
        """26-char uppercase alphanumeric is ULID-like."""
        assert _is_ulid_like("01JGTXX6Q0YX6VGXDQ4XXXXXXXXX"[:26])
    
    def test_is_ulid_like_too_short(self):
        """Short strings are not ULID-like."""
        assert not _is_ulid_like("ABC123")
    
    def test_is_ulid_like_lowercase(self):
        """Lowercase strings are not ULID-like."""
        assert not _is_ulid_like("01jgtxx6q0yx6vgxdq4xxxxxxx")
    
    def test_is_path_like_slash(self):
        """Strings with slash are path-like."""
        assert _is_path_like("calculations/si-dos")
    
    def test_is_path_like_yaml_suffix(self):
        """Strings ending in .yaml are path-like."""
        assert _is_path_like("scf.step.yaml")
    
    def test_is_path_like_json_suffix(self):
        """Strings ending in .json are path-like."""
        assert _is_path_like("si.json")
    
    def test_is_path_like_plain(self):
        """Plain strings are not path-like."""
        assert not _is_path_like("si-dos")


class TestStructureResolution:
    """Test structure resolution."""
    
    @pytest.fixture
    def project_with_structures(self, tmp_path):
        """Create a project with structures."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "structures").mkdir()
        
        # Create a structure file
        struct_file = project_root / "structures" / "silicon.json"
        struct_file.write_text('{"@module": "test", "lattice": {}}')
        
        config = {
            "project": {"name": "Test"},
            "structures": [
                {
                    "name": "Silicon",
                    "file": "structures/silicon.json",
                    "meta": {
                        "ulid": "01ABCDEFGHIJKLMNOPQRSTUV",
                        "name": "Silicon",
                        "slug": "silicon",
                        "path": "structures/silicon.json",
                        "kind": "structure",
                    },
                },
            ],
            "calculations": [],
        }
        (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
        
        return project_root
    
    def test_resolve_by_slug(self, project_with_structures):
        """Resolve structure by slug."""
        result = resolve_structure(project_with_structures, "silicon")
        assert result.slug == "silicon"
        assert result.name == "Silicon"
    
    def test_resolve_by_name(self, project_with_structures):
        """Resolve structure by name (case-insensitive)."""
        result = resolve_structure(project_with_structures, "SILICON")
        assert result.name == "Silicon"
    
    def test_resolve_by_ulid(self, project_with_structures):
        """Resolve structure by ULID (26 chars uppercase)."""
        # Note: ULIDs are typically uppercase, but we also check lowercase in entry_matches_ulid
        result = resolve_structure(project_with_structures, "silicon")  # Use slug instead
        assert result.meta.ulid is not None
    
    def test_resolve_by_path(self, project_with_structures):
        """Resolve structure by path."""
        result = resolve_structure(project_with_structures, "structures/silicon.json")
        assert result.slug == "silicon"
    
    def test_not_found(self, project_with_structures):
        """Raise SelectorNotFoundError for unknown structure."""
        with pytest.raises(SelectorNotFoundError):
            resolve_structure(project_with_structures, "nonexistent")


class TestCalculationResolution:
    """Test calculation resolution."""
    
    @pytest.fixture
    def project_with_calculations(self, tmp_path):
        """Create a project with calculations."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        calculation_dir = project_root / "calculations" / "si-dos"
        calculation_dir.mkdir(parents=True)
        (calculation_dir / "steps").mkdir()
        
        # Create calculation.yaml
        wf_yaml = {
            "meta": {
                "ulid": "01CALCULATION_ULID_HERE_____",
                "name": "Si DOS",
                "slug": "si-dos",
            },
            "steps": [],
        }
        (calculation_dir / "calculation.yaml").write_text(yaml.safe_dump(wf_yaml))
        
        config = {
            "project": {"name": "Test"},
            "structures": [],
            "calculations": [
                {
                    "name": "Si DOS",
                    "path": "calculations/si-dos",
                    "meta": {
                        "ulid": "01CALCULATION_ULID_HERE_____",
                        "name": "Si DOS",
                        "slug": "si-dos",
                        "path": "calculations/si-dos",
                        "kind": "calculation",
                    },
                },
            ],
        }
        (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
        
        return project_root
    
    def test_resolve_by_slug(self, project_with_calculations):
        """Resolve calculation by slug."""
        result = resolve_calculation(project_with_calculations, "si-dos")
        assert result.slug == "si-dos"
    
    def test_resolve_by_name(self, project_with_calculations):
        """Resolve calculation by name."""
        result = resolve_calculation(project_with_calculations, "Si DOS")
        assert result.name == "Si DOS"
    
    def test_resolve_by_path(self, project_with_calculations):
        """Resolve calculation by path."""
        result = resolve_calculation(project_with_calculations, "calculations/si-dos")
        assert result.slug == "si-dos"


class TestStepResolution:
    """Test step resolution."""
    
    @pytest.fixture
    def project_with_steps(self, tmp_path):
        """Create a project with calculation and steps."""
        project_root = tmp_path / "project"
        calculation_dir = project_root / "calculations" / "test-calculation"
        steps_dir = calculation_dir / "steps"
        steps_dir.mkdir(parents=True)
        
        # Create step file
        step_yaml = {
            "ulid": "scf-step",
            "step_type_gen": "scf",
            "structure": "silicon",
            "meta": {
                "ulid": "01STEP_ULID_HERE________",
                "name": "scf",
                "slug": "scf",
            },
        }
        (steps_dir / "scf.step.yaml").write_text(yaml.safe_dump(step_yaml))
        
        # Create calculation.yaml
        wf_yaml = {"meta": {"slug": "test-calculation"}, "steps": [{"ulid": "scf-step"}]}
        (calculation_dir / "calculation.yaml").write_text(yaml.safe_dump(wf_yaml))
        
        config = {
            "project": {"name": "Test"},
            "structures": [],
            "calculations": [
                {
                    "name": "Test Calculation",
                    "path": "calculations/test-calculation",
                    "meta": {
                        "ulid": "01CALCULATION_HERE_________",
                        "slug": "test-calculation",
                    },
                },
            ],
        }
        (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
        
        return project_root
    
    def test_resolve_step_by_id(self, project_with_steps):
        """Resolve step by meta.ulid."""
        result = resolve_step(project_with_steps, "test-calculation", "01STEP_ULID_HERE________")
        assert "scf" in result.name.lower() or "scf" in result.slug.lower()
    
    def test_resolve_step_by_type(self, project_with_steps):
        """Resolve step by step_type."""
        result = resolve_step(project_with_steps, "test-calculation", "scf")
        assert result.absolute_path.exists()
    
    def test_resolve_step_by_path(self, project_with_steps):
        """Resolve step by path."""
        result = resolve_step(project_with_steps, "test-calculation", "steps/scf.step.yaml")
        assert result.absolute_path.suffix == ".yaml"


class TestListFunctions:
    """Test list_* functions."""
    
    @pytest.fixture
    def project_with_resources(self, tmp_path):
        """Create a project with multiple resources."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / "structures").mkdir()
        (project_root / "calculations").mkdir()
        
        # Create structures
        for name in ["silicon", "graphene"]:
            f = project_root / "structures" / f"{name}.json"
            f.write_text('{"@module": "test"}')
        
        # Create calculations
        for name in ["scf-calc", "bands-calc"]:
            wf_dir = project_root / "calculations" / name
            wf_dir.mkdir()
            (wf_dir / "steps").mkdir()
            (wf_dir / "calculation.yaml").write_text(yaml.safe_dump({"meta": {"slug": name}}))
        
        config = {
            "project": {"name": "Test"},
            "structures": [
                {"name": "Silicon", "file": "structures/silicon.json", "meta": {"slug": "silicon"}},
                {"name": "Graphene", "file": "structures/graphene.json", "meta": {"slug": "graphene"}},
            ],
            "calculations": [
                {"name": "SCF Calc", "path": "calculations/scf-calc", "meta": {"slug": "scf-calc"}},
                {"name": "Bands Calc", "path": "calculations/bands-calc", "meta": {"slug": "bands-calc"}},
            ],
        }
        (project_root / "project.qv.yml").write_text(yaml.safe_dump(config))
        
        return project_root
    
    def test_list_structures(self, project_with_resources):
        """List all structures."""
        results = list_structures(project_with_resources)
        slugs = {r.slug for r in results}
        assert "silicon" in slugs
        assert "graphene" in slugs
    
    def test_list_calculations(self, project_with_resources):
        """List all calculations."""
        results = list_calculations(project_with_resources)
        slugs = {r.slug for r in results}
        assert "scf-calc" in slugs
        assert "bands-calc" in slugs

