"""
Tests for API service facade methods.

These tests verify the PR10 Domain Accessor API:
- svc.structure.*
- svc.calculation.*
- svc.run.*
- svc.analysis.*

Tests for deprecated wrapper methods and re-exports have been removed.
Use original modules directly for IO, parsing, plotting, etc.
"""

import pytest
from pathlib import Path

from quantumvitas.api import QVService, APIError, NotFoundError


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
    ulid: 01ARZ3NDEKTSV4RRFFQ69G5FAV
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

    # -------------------------------------------------------------------------
    # Basic Service Tests
    # -------------------------------------------------------------------------

    def test_service_initialization(self, demo_project):
        """QVService can be initialized with project_root."""
        svc = QVService(demo_project)
        assert svc.project_root == demo_project.resolve()

    def test_service_initialization_fails_for_non_project(self, tmp_path):
        """QVService raises error for non-project directory."""
        non_project = tmp_path / "not_a_project"
        non_project.mkdir()

        with pytest.raises(ValueError, match="Not a project"):
            QVService(non_project)

    def test_load_project_config(self, demo_project):
        """API can load project config via svc.project.get_config()."""
        svc = QVService(demo_project)
        config = svc.project.get_config()
        assert "project" in config
        assert config["project"]["name"] == "test_project"

    def test_api_importable(self):
        """API module is importable."""
        from quantumvitas.api import QVService, APIError
        assert QVService is not None
        assert APIError is not None

    # -------------------------------------------------------------------------
    # Structure Domain Tests
    # -------------------------------------------------------------------------

    def test_structure_list_empty(self, demo_project):
        """svc.structure.list() returns empty list for project with no structures."""
        svc = QVService(demo_project)
        structures = svc.structure.list()
        assert isinstance(structures, list)
        assert len(structures) == 0

    def test_structure_get_not_found(self, demo_project):
        """svc.structure.get() raises NotFoundError for non-existent structure."""
        svc = QVService(demo_project)
        with pytest.raises(APIError):
            svc.structure.get("nonexistent")

    def test_structure_require_ref_not_found(self, demo_project):
        """svc.structure.require_ref() raises APIError for non-existent structure."""
        svc = QVService(demo_project)
        with pytest.raises(APIError):
            svc.structure.require_ref("nonexistent")

    # -------------------------------------------------------------------------
    # Calculation Domain Tests
    # -------------------------------------------------------------------------

    def test_calculation_list_empty(self, demo_project):
        """svc.calculation.list() returns empty list for project with no calculations."""
        svc = QVService(demo_project)
        calcs = svc.calculation.list()
        assert isinstance(calcs, list)
        assert len(calcs) == 0

    def test_calculation_get_not_found(self, demo_project):
        """svc.calculation.get() raises NotFoundError for non-existent calculation."""
        svc = QVService(demo_project)
        with pytest.raises(APIError):
            svc.calculation.get("nonexistent")

    def test_calculation_require_ref_not_found(self, demo_project):
        """svc.calculation.require_ref() raises APIError for non-existent calculation."""
        svc = QVService(demo_project)
        with pytest.raises(APIError):
            svc.calculation.require_ref("nonexistent")

    def test_calculation_list_steps_not_found(self, demo_project):
        """svc.calculation.list_steps() raises APIError for non-existent calculation."""
        svc = QVService(demo_project)
        with pytest.raises(APIError):
            svc.calculation.list_steps("nonexistent")

    def test_calculation_resolve_enclosing_returns_none(self, demo_project):
        """svc.calculation.resolve_enclosing_path() returns None when not in calculation."""
        svc = QVService(demo_project)
        result = svc.calculation.resolve_enclosing_path(demo_project / "structures")
        assert result is None

    # -------------------------------------------------------------------------
    # Static Method Tests
    # -------------------------------------------------------------------------

    def test_get_default_step_params_wrapper(self):
        """QVService.get_default_step_params() returns step defaults."""
        defaults = QVService.get_default_step_params("scf")

        assert isinstance(defaults, dict)
        assert "parameters" in defaults
        assert "cards" in defaults
        assert "species_overrides" in defaults

        # Verify it has expected content for scf
        assert "CONTROL" in defaults["parameters"]
        assert defaults["parameters"]["CONTROL"]["calculation"] == "scf"

        # Test with unknown step type (should return empty dicts)
        unknown_defaults = QVService.get_default_step_params("unknown_step_type")
        assert isinstance(unknown_defaults, dict)
        assert "parameters" in unknown_defaults

    def test_get_workflow_service_wrapper(self, monkeypatch):
        """QVService.get_workflow_service() returns workflow service."""
        import quantumvitas.workflow.templates as templates_module

        called = {}

        class FakeWorkflowService:
            def __init__(self):
                called["initialized"] = True

        fake_service = FakeWorkflowService()

        def fake_get_workflow_service():
            called["called"] = True
            return fake_service

        monkeypatch.setattr(templates_module, "get_workflow_service", fake_get_workflow_service)

        result = QVService.get_workflow_service()

        assert result == fake_service
        assert called["called"] is True

    # -------------------------------------------------------------------------
    # Domain Accessor Existence Tests
    # -------------------------------------------------------------------------

    def test_domain_accessors_exist(self, demo_project):
        """All domain accessors exist on QVService instance."""
        svc = QVService(demo_project)

        # Check domain accessors exist
        assert hasattr(svc, "structure")
        assert hasattr(svc, "calculation")
        assert hasattr(svc, "run")
        assert hasattr(svc, "analysis")
        assert hasattr(svc, "project")

        # Check structure methods
        assert hasattr(svc.structure, "get")
        assert hasattr(svc.structure, "list")
        assert hasattr(svc.structure, "require_ref")

        # Check calculation methods
        assert hasattr(svc.calculation, "get")
        assert hasattr(svc.calculation, "list")
        assert hasattr(svc.calculation, "require_ref")
        assert hasattr(svc.calculation, "list_steps")
        assert hasattr(svc.calculation, "add_step")
        assert hasattr(svc.calculation, "remove_step")

        # Check run methods
        assert hasattr(svc.run, "run_calculation")
        assert hasattr(svc.run, "run_step")

        # Check analysis methods
        assert hasattr(svc.analysis, "get_summary")
        assert hasattr(svc.analysis, "list_properties")


class TestAPIUtils:
    """Test api.utils functions are accessible."""

    def test_utils_importable(self):
        """api.utils functions are importable."""
        from quantumvitas.api.utils import (
            slugify,
            ensure_relative_path,
            read_structure,
            write_structure,
            find_project_root,
            is_ulid_like,
        )

        # Basic smoke tests
        assert callable(slugify)
        assert callable(ensure_relative_path)
        assert callable(read_structure)
        assert callable(write_structure)
        assert callable(find_project_root)
        assert callable(is_ulid_like)

    def test_slugify(self):
        """slugify converts names to slugs."""
        from quantumvitas.api.utils import slugify

        assert slugify("Test Name") == "test-name"
        assert slugify("UPPER_CASE") == "upper_case"  # underscores preserved
        assert slugify("with  spaces") == "with-spaces"

    def test_is_ulid_like(self):
        """is_ulid_like correctly identifies ULID strings."""
        from quantumvitas.api.utils import is_ulid_like

        assert is_ulid_like("01ARZ3NDEKTSV4RRFFQ69G5FAV")
        assert not is_ulid_like("short")
        assert not is_ulid_like("not-a-ulid-at-all-because-too-long")

    def test_ensure_relative_path(self, tmp_path):
        """ensure_relative_path converts absolute to relative."""
        from quantumvitas.api.utils import ensure_relative_path

        abs_path = tmp_path / "subdir" / "file.txt"
        rel_path = ensure_relative_path(abs_path, base=tmp_path)

        assert isinstance(rel_path, str)
        assert not Path(rel_path).is_absolute()
        assert "subdir" in rel_path


class TestAPITypes:
    """Test api types (DTOs) are accessible."""

    def test_types_importable(self):
        """API types are importable."""
        from quantumvitas.api import (
            CalculationDTO,
            StepDTO,
            StructureDTO,
            RunResultDTO,
            AnalysisRefDTO,
            AnalysisSummaryDTO,
        )

        # These should all be DTO classes
        assert CalculationDTO is not None
        assert StepDTO is not None
        assert StructureDTO is not None
        assert RunResultDTO is not None
        assert AnalysisRefDTO is not None
        assert AnalysisSummaryDTO is not None


class TestAPIErrors:
    """Test api error types are accessible."""

    def test_errors_importable(self):
        """API error types are importable."""
        from quantumvitas.api import (
            APIError,
            NotFoundError,
            AmbiguousError,
            ValidationError,
            ConflictError,
            EngineError,
            ConfigError,
            FilesystemError,
            InternalError,
        )

        # All should be exception classes
        assert issubclass(APIError, Exception)
        assert issubclass(NotFoundError, APIError)
        assert issubclass(AmbiguousError, APIError)
        assert issubclass(ValidationError, APIError)
        assert issubclass(ConflictError, APIError)
        assert issubclass(EngineError, APIError)
        assert issubclass(ConfigError, APIError)
        assert issubclass(FilesystemError, APIError)
        assert issubclass(InternalError, APIError)

    def test_error_instantiation(self):
        """API errors can be instantiated with message and context."""
        from quantumvitas.api import NotFoundError

        err = NotFoundError("Resource not found", context={"ulid": "123"})
        assert "Resource not found" in str(err)
