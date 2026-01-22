"""
Tests for API service facade methods.

These tests verify API methods work without requiring engines.
They test the instance-based API (QVService(project_root)).
"""

import os
import pytest
from pathlib import Path

from quantumvitas.api import QVService, QVServiceError


class TestAPIServiceFacade:
    """Test that API facade instance methods work correctly."""

    @pytest.fixture
    def demo_project(self, tmp_path):
        """Create a minimal demo project."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        
        # Create minimal project.qv.yml
        (project_root / "project.qv.yml").write_text("""project:
  name: test_project
  meta:
    id: 01ARZ3NDEKTSV4RRFFQ69G5FAV
    name: test_project
    slug: test-project
    path: "."
    kind: project
structures: []
calculations: []
""")
        
        # Create standard directories
        (project_root / "structures").mkdir()
        (project_root / "calculations").mkdir()
        (project_root / "pseudo").mkdir()
        (project_root / "trash").mkdir()
        
        return project_root

    def test_service_initialization(self, demo_project):
        """QVService can be initialized with project_root."""
        svc = QVService(demo_project)
        assert svc.project_root == demo_project.resolve()

    def test_service_initialization_fails_for_non_project(self, tmp_path):
        """QVService raises error for non-project directory."""
        non_project = tmp_path / "not_a_project"
        non_project.mkdir()
        
        with pytest.raises(QVServiceError, match="Not a project"):
            QVService(non_project)

    def test_load_project_config(self, demo_project):
        """API can load project config."""
        svc = QVService(demo_project)
        config = svc.load_project_config()
        assert "project" in config
        assert config["project"]["name"] == "test_project"

    def test_build_resource_index(self, demo_project):
        """API can build resource index."""
        svc = QVService(demo_project)
        index = svc.build_resource_index()
        assert index is not None
        # Index should be empty for a project with no resources
        assert len(index.by_id) == 0

    def test_detect_context(self, demo_project):
        """API can detect context from cwd."""
        svc = QVService(demo_project)
        
        # Change to project dir
        old_cwd = os.getcwd()
        try:
            os.chdir(demo_project)
            ctx = svc.detect_context()
            # Should detect project root at minimum
            assert ctx is not None
            assert ctx["project_root"] == demo_project.resolve()
            assert ctx["is_project"] is True
        finally:
            os.chdir(old_cwd)

    def test_detect_context_with_cwd(self, demo_project):
        """API can detect context from specified cwd."""
        svc = QVService(demo_project)
        
        # Test with explicit cwd
        ctx = svc.detect_context(cwd=demo_project)
        assert ctx is not None
        assert ctx["project_root"] == demo_project.resolve()
        assert ctx["is_project"] is True

    def test_list_calculations_empty(self, demo_project):
        """API can list calculations (empty project)."""
        # Use static method (instance methods removed to avoid conflicts with static methods)
        calcs = QVService.list_calculations(demo_project)
        assert isinstance(calcs, list)
        assert len(calcs) == 0

    def test_list_steps_empty(self, demo_project):
        """API can list steps (empty calculation)."""
        # Create a minimal calculation
        calc_dir = demo_project / "calculations" / "test-calc"
        calc_dir.mkdir()
        (calc_dir / "calculation.yaml").write_text("""meta:
  id: 01ARZ3NDEKTSV4RRFFQ69G5FAW
  name: test-calc
  slug: test-calc
  path: calculations/test-calc/calculation.yaml
  kind: calculation
steps: []
""")
        
        # Update project config
        import yaml
        svc = QVService(demo_project)
        config = svc.load_project_config()
        config["calculations"] = [{
            "id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
        }]
        from quantumvitas.core.project_utils import save_project_config
        save_project_config(demo_project, config)
        
        # List steps (should be empty) - use static method
        steps = QVService.list_steps(demo_project, "test-calc")
        assert isinstance(steps, list)
        assert len(steps) == 0

    def test_resolve_calculation_ref_not_found(self, demo_project):
        """API raises QVServiceError for non-existent calculation."""
        svc = QVService(demo_project)
        
        with pytest.raises(QVServiceError, match="Failed to resolve calculation"):
            svc.resolve_calculation_ref("nonexistent")

    def test_resolve_structure_ref_not_found(self, demo_project):
        """API raises QVServiceError for non-existent structure."""
        svc = QVService(demo_project)
        
        with pytest.raises(QVServiceError, match="Failed to resolve structure"):
            svc.resolve_structure_ref("nonexistent")

    def test_resolve_step_ref_not_found(self, demo_project):
        """API raises QVServiceError for non-existent step."""
        svc = QVService(demo_project)
        
        # Create a minimal calculation first
        calc_dir = demo_project / "calculations" / "test-calc"
        calc_dir.mkdir()
        (calc_dir / "calculation.yaml").write_text("""meta:
  id: 01ARZ3NDEKTSV4RRFFQ69G5FAW
  name: test-calc
  slug: test-calc
  path: calculations/test-calc/calculation.yaml
  kind: calculation
steps: []
""")
        
        import yaml
        config = svc.load_project_config()
        config["calculations"] = [{
            "id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
        }]
        from quantumvitas.core.project_utils import save_project_config
        save_project_config(demo_project, config)
        
        with pytest.raises(QVServiceError, match="Failed to resolve step"):
            svc.resolve_step_ref("test-calc", "nonexistent")

    def test_api_importable(self):
        """API module is importable."""
        from quantumvitas.api import QVService, QVServiceError
        assert QVService is not None
        assert QVServiceError is not None

    def test_instance_methods_exist(self, demo_project):
        """All required instance methods exist."""
        svc = QVService(demo_project)
        
        # Check that all required methods exist
        assert hasattr(svc, "detect_context")
        assert hasattr(svc, "load_project_config")
        assert hasattr(svc, "build_resource_index")
        assert hasattr(svc, "resolve_calculation_ref")
        assert hasattr(svc, "resolve_step_ref")
        assert hasattr(svc, "resolve_structure_ref")
        # list_calculations and list_steps are static methods (not instance methods)
        assert hasattr(QVService, "list_calculations")
        assert hasattr(QVService, "list_steps")
        
        # Check they are callable
        assert callable(svc.detect_context)
        assert callable(svc.load_project_config)
        assert callable(svc.build_resource_index)
        assert callable(svc.resolve_calculation_ref)
        assert callable(svc.resolve_step_ref)
        assert callable(svc.resolve_structure_ref)
        # New Chunk 1 wrappers
        assert hasattr(svc, "require_calculation_ref")
        assert hasattr(svc, "require_structure_ref")
        assert hasattr(svc, "require_step_ref")
        assert hasattr(svc, "make_structure_selector_resolver_ref")
        assert callable(svc.require_calculation_ref)
        assert callable(svc.require_structure_ref)
        assert callable(svc.require_step_ref)
        assert callable(svc.make_structure_selector_resolver_ref)
        assert callable(QVService.list_calculations)
        assert callable(QVService.list_steps)

    def test_require_calculation_ref_not_found(self, demo_project):
        """require_calculation_ref raises QVServiceError for non-existent calculation."""
        svc = QVService(demo_project)
        
        with pytest.raises(QVServiceError, match="Calculation.*not found"):
            svc.require_calculation_ref("nonexistent")

    def test_require_structure_ref_not_found(self, demo_project):
        """require_structure_ref raises QVServiceError for non-existent structure."""
        svc = QVService(demo_project)
        
        with pytest.raises(QVServiceError, match="Structure.*not found"):
            svc.require_structure_ref("nonexistent")

    def test_require_step_ref_not_found(self, demo_project):
        """require_step_ref raises QVServiceError for non-existent step."""
        svc = QVService(demo_project)
        
        # Create a minimal calculation first
        calc_dir = demo_project / "calculations" / "test-calc"
        calc_dir.mkdir()
        (calc_dir / "calculation.yaml").write_text("""meta:
  id: 01ARZ3NDEKTSV4RRFFQ69G5FAW
  name: test-calc
  slug: test-calc
  path: calculations/test-calc/calculation.yaml
  kind: calculation
steps: []
""")
        
        import yaml
        config = svc.load_project_config()
        config["calculations"] = [{
            "id": "01ARZ3NDEKTSV4RRFFQ69G5FAW",
        }]
        from quantumvitas.core.project_utils import save_project_config
        save_project_config(demo_project, config)
        
        with pytest.raises(QVServiceError, match="Step.*not found"):
            svc.require_step_ref("test-calc", "nonexistent")

    def test_make_structure_selector_resolver_ref(self, demo_project):
        """make_structure_selector_resolver_ref returns a callable resolver."""
        svc = QVService(demo_project)
        
        resolver = svc.make_structure_selector_resolver_ref()
        assert callable(resolver)
        
        # Resolver should raise error for non-existent structure
        with pytest.raises(Exception):  # May be ResourceNotFoundError or QVServiceError
            resolver("nonexistent")

    def test_generate_resource_id(self, demo_project):
        """generate_resource_id generates unique IDs."""
        # Test static method
        id1 = QVService.generate_resource_id()
        id2 = QVService.generate_resource_id()
        
        assert isinstance(id1, str)
        assert isinstance(id2, str)
        assert len(id1) > 0
        assert len(id2) > 0
        # IDs should be unique
        assert id1 != id2
        
        # Test instance method (should also work)
        svc = QVService(demo_project)
        id3 = svc.generate_resource_id()
        assert isinstance(id3, str)
        assert len(id3) > 0
        # Should also be unique
        assert id3 != id1
        assert id3 != id2

    def test_ensure_relative_path(self, demo_project):
        """ensure_relative_path converts absolute paths to relative."""
        # Test static method
        abs_path = demo_project / "structures" / "test.json"
        rel_path = QVService.ensure_relative_path(abs_path, base=demo_project)
        
        assert isinstance(rel_path, str)
        assert not Path(rel_path).is_absolute()
        assert "structures" in rel_path
        
        # Test with already relative path
        rel_path2 = QVService.ensure_relative_path("structures/test.json", base=demo_project)
        assert isinstance(rel_path2, str)
        
        # Test instance method
        svc = QVService(demo_project)
        rel_path3 = svc.ensure_relative_path(abs_path, base=demo_project)
        assert isinstance(rel_path3, str)
        assert not Path(rel_path3).is_absolute()

    def test_generate_unique_name_and_slug(self):
        """generate_unique_name_and_slug generates unique names and slugs."""
        # Test static method
        name1, slug1 = QVService.generate_unique_name_and_slug(
            kind="structure",
            preferred_name="test",
            existing_slugs=[]
        )
        
        assert isinstance(name1, str)
        assert isinstance(slug1, str)
        assert name1 == "test"
        assert slug1 == "test"
        
        # Test with existing slug (should generate unique)
        name2, slug2 = QVService.generate_unique_name_and_slug(
            kind="structure",
            preferred_name="test",
            existing_slugs=["test"]
        )
        
        assert name2 != "test" or slug2 != "test"  # Should be unique
        assert isinstance(name2, str)
        assert isinstance(slug2, str)

