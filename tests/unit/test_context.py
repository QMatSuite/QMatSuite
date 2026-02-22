"""Unit tests for core/context.py - PWD context helper."""

import pytest
from pathlib import Path

import yaml

from qmatsuite.core.context import (
    ContextNotFoundError,
    ContextNode,
    PathContext,
    find_path_context_from_pwd,
    get_project_root_from_pwd,
    get_calculation_from_pwd,
)


class TestPathContext:
    """Test PathContext dataclass methods."""
    
    def test_empty_context(self):
        """Empty context has no calculation/step."""
        ctx = PathContext(project_root=Path("/test"))
        assert ctx.calculation_node is None
        assert ctx.step_node is None
        assert ctx.calculation_selector is None
        assert ctx.is_inside_project()
        assert not ctx.is_inside_calculation()
    
    def test_context_with_calculation(self):
        """Context with calculation node."""
        ctx = PathContext(
            project_root=Path("/test"),
            nodes=[
                ContextNode(kind="project", directory=Path("/test")),
                ContextNode(kind="calculation", directory=Path("/test/calculations/my-wf"), selector="my-wf"),
            ],
        )
        assert ctx.is_inside_calculation()
        assert ctx.calculation_selector == "my-wf"
        assert ctx.calculation_directory == Path("/test/calculations/my-wf")


class TestFindPathContext:
    """Test find_path_context_from_pwd."""
    
    @pytest.fixture
    def project_tree(self, tmp_path):
        """Create a project directory tree."""
        project_root = tmp_path / "my-project"
        project_root.mkdir()
        
        # Create project.qms.yml
        config = {
            "project": {
                "name": "My Project",
                "meta": {"slug": "my-project"},
            },
            "calculations": [
                {"name": "Test Calculation", "path": "calculations/test-wf", "meta": {"slug": "test-wf"}},
            ],
            "structures": [],
        }
        (project_root / "project.qms.yml").write_text(yaml.safe_dump(config))
        
        # Create calculation
        calculation_dir = project_root / "calculations" / "test-wf"
        calculation_dir.mkdir(parents=True)
        (calculation_dir / "steps").mkdir()
        
        wf_yaml = {"meta": {"slug": "test-wf", "name": "Test Calculation"}}
        (calculation_dir / "calculation.yaml").write_text(yaml.safe_dump(wf_yaml))
        
        return project_root
    
    def test_find_from_project_root(self, project_tree):
        """Find context from project root."""
        ctx = find_path_context_from_pwd(project_tree)
        assert ctx.project_root == project_tree
        assert not ctx.is_inside_calculation()
    
    def test_find_from_calculation_dir(self, project_tree):
        """Find context from calculation directory."""
        calculation_dir = project_tree / "calculations" / "test-wf"
        ctx = find_path_context_from_pwd(calculation_dir)
        
        assert ctx.project_root == project_tree
        assert ctx.is_inside_calculation()
        assert ctx.calculation_selector == "test-wf"
    
    def test_find_from_steps_dir(self, project_tree):
        """Find context from steps directory."""
        steps_dir = project_tree / "calculations" / "test-wf" / "steps"
        ctx = find_path_context_from_pwd(steps_dir)
        
        assert ctx.project_root == project_tree
        assert ctx.is_inside_calculation()
        assert ctx.calculation_selector == "test-wf"
    
    def test_find_from_subdirectory(self, project_tree):
        """Find context from nested subdirectory."""
        nested = project_tree / "calculations" / "test-wf" / "raw" / "subdir"
        nested.mkdir(parents=True)
        
        ctx = find_path_context_from_pwd(nested)
        assert ctx.project_root == project_tree
        assert ctx.is_inside_calculation()
    
    def test_not_found_raises(self, tmp_path):
        """Raise ContextNotFoundError when no project found."""
        not_a_project = tmp_path / "not-a-project"
        not_a_project.mkdir()
        
        with pytest.raises(ContextNotFoundError):
            find_path_context_from_pwd(not_a_project)
    
    def test_max_depth_respected(self, tmp_path):
        """max_depth limits search."""
        # Create deeply nested structure
        deep = tmp_path
        for i in range(5):
            deep = deep / f"level{i}"
            deep.mkdir()
        
        # Put project.qms.yml at root
        config = {"project": {"name": "Deep"}, "structures": [], "calculations": []}
        (tmp_path / "project.qms.yml").write_text(yaml.safe_dump(config))
        
        # With max_depth=3, should not find project from level4
        start = tmp_path / "level0" / "level1" / "level2" / "level3" / "level4"
        with pytest.raises(ContextNotFoundError):
            find_path_context_from_pwd(start, max_depth=3)
        
        # With max_depth=5, should find it
        ctx = find_path_context_from_pwd(start, max_depth=5)
        assert ctx.project_root == tmp_path


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    @pytest.fixture
    def simple_project(self, tmp_path):
        """Create a simple project."""
        project_root = tmp_path / "proj"
        project_root.mkdir()
        
        calculation_dir = project_root / "calculations" / "my-calculation"
        calculation_dir.mkdir(parents=True)
        
        config = {
            "project": {"name": "Proj"},
            "calculations": [{"name": "My Calculation", "path": "calculations/my-calculation", "meta": {"slug": "my-calculation"}}],
            "structures": [],
        }
        (project_root / "project.qms.yml").write_text(yaml.safe_dump(config))
        
        wf_yaml = {"meta": {"slug": "my-calculation"}}
        (calculation_dir / "calculation.yaml").write_text(yaml.safe_dump(wf_yaml))
        
        return project_root
    
    def test_get_project_root_from_pwd(self, simple_project):
        """get_project_root_from_pwd returns project root."""
        root = get_project_root_from_pwd(simple_project)
        assert root == simple_project
    
    def test_get_calculation_from_pwd_inside_calculation(self, simple_project):
        """get_calculation_from_pwd returns selector when inside calculation."""
        calculation_dir = simple_project / "calculations" / "my-calculation"
        selector = get_calculation_from_pwd(calculation_dir)
        assert selector == "my-calculation"
    
    def test_get_calculation_from_pwd_outside_calculation(self, simple_project):
        """get_calculation_from_pwd returns None when outside calculation."""
        selector = get_calculation_from_pwd(simple_project)
        assert selector is None

