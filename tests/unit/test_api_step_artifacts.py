"""Unit tests for QVService step artifact methods (list_step_artifacts, read_step_artifact_text)."""

import pytest
from pathlib import Path

from quantumvitas.api import QVService, APIError


@pytest.fixture
def project_with_step(tmp_path):
    """Create a project with a calculation and step for testing."""
    project_dir = QVService.init_project(tmp_path / "test_project")
    
    # Import structure (required for calculation)
    source = tmp_path / "si.json"
    source.write_text("""{
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {"matrix": [[5.43,0,0],[0,5.43,0],[0,0,5.43]], "a": 5.43, "b": 5.43, "c": 5.43, "alpha": 90, "beta": 90, "gamma": 90},
        "sites": [{"species": [{"element": "Si", "occu": 1}], "abc": [0,0,0], "xyz": [0,0,0]}]
    }""")
    QVService.import_structure(project_dir, source, name="Silicon")
    
    # Create calculation and step
    calc_slug = "test-calc"
    QVService.init_calculation(project_dir, calc_slug, structure_selector="silicon")
    
    # Use domain accessor API for step creation
    svc = QVService(project_dir)
    svc.calculation.add_step(calc_selector=calc_slug, step_type="scf", name="scf")
    
    # Get step ID
    from quantumvitas.core.models import load_calculation
    from quantumvitas.core.project_utils import load_project_config
    from quantumvitas.core.resolution import make_structure_selector_resolver
    
    config = load_project_config(project_dir)
    resolver = make_structure_selector_resolver(project_dir, config=config)
    calc_dir = project_dir / "calculations" / calc_slug
    calc_yaml = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_yaml, project_root=project_dir, resolve_structure_selector=resolver)
    
    if not calc_model.steps:
        pytest.skip("No steps in calculation")
    
    step_id = calc_model.steps[0].step_id
    
    return project_dir, calc_slug, step_id, calc_dir


@pytest.mark.skip(reason="PR10: list_step_artifacts not in domain API")
class TestListStepArtifacts:
    """Tests for QVService.list_step_artifacts()."""
    
    def test_list_step_artifacts_empty_raw_dir(self, project_with_step):
        """Test listing artifacts when raw directory doesn't exist."""
        project_dir, calc_slug, step_id, calc_dir = project_with_step
        
        result = QVService.list_step_artifacts(
            project_root=project_dir,
            calculation_selector=calc_slug,
            step_selector=step_id,
        )
        
        assert "raw_dir" in result
        assert "artifacts" in result
        assert result["artifacts"] == []
    
    def test_list_step_artifacts_with_files(self, project_with_step):
        """Test listing artifacts with actual output files."""
        project_dir, calc_slug, step_id, calc_dir = project_with_step
        
        # Create raw directory and output files
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        
        # Create scf.out file
        scf_out = raw_dir / "scf.out"
        scf_out.write_text("Test output content")
        
        # Create scf-1.out file (numbered version)
        scf1_out = raw_dir / "scf-1.out"
        scf1_out.write_text("Test output content 1")
        
        result = QVService.list_step_artifacts(
            project_root=project_dir,
            calculation_selector=calc_slug,
            step_selector=step_id,
        )
        
        assert "raw_dir" in result
        assert "artifacts" in result
        assert len(result["artifacts"]) >= 1
        
        # Find scf.out in artifacts
        scf_artifact = next((a for a in result["artifacts"] if a["path_relative_to_raw"] == "scf.out"), None)
        assert scf_artifact is not None
        assert scf_artifact["kind"] == "out"
        assert scf_artifact["size_bytes"] > 0
        assert "mtime" in scf_artifact
        assert scf_artifact["is_default_candidate"] is True  # Exact match should be default
    
    def test_list_step_artifacts_default_selection(self, project_with_step):
        """Test that default artifact selection works correctly."""
        project_dir, calc_slug, step_id, calc_dir = project_with_step
        
        # Create raw directory and files
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        
        # Create only numbered version (no exact match)
        scf1_out = raw_dir / "scf-1.out"
        scf1_out.write_text("Test output")
        
        result = QVService.list_step_artifacts(
            project_root=project_dir,
            calculation_selector=calc_slug,
            step_selector=step_id,
        )
        
        assert len(result["artifacts"]) >= 1
        # Should select scf-1.out as default (newest numbered match)
        default_artifact = next((a for a in result["artifacts"] if a["is_default_candidate"]), None)
        assert default_artifact is not None
        assert default_artifact["path_relative_to_raw"] == "scf-1.out"
    
    def test_list_step_artifacts_rejects_directories(self, project_with_step):
        """Test that directories are rejected (security)."""
        project_dir, calc_slug, step_id, calc_dir = project_with_step
        
        # Create raw directory and a subdirectory (should be ignored)
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        subdir = raw_dir / "scf.out"  # Directory with same name as file
        subdir.mkdir()
        
        result = QVService.list_step_artifacts(
            project_root=project_dir,
            calculation_selector=calc_slug,
            step_selector=step_id,
        )
        
        # Directory should not appear in artifacts
        artifact_names = [a["path_relative_to_raw"] for a in result["artifacts"]]
        assert "scf.out" not in artifact_names


@pytest.mark.skip(reason="PR10: read_step_artifact_text not in domain API")
class TestReadStepArtifactText:
    """Tests for QVService.read_step_artifact_text()."""
    
    def test_read_step_artifact_text_success(self, project_with_step):
        """Test reading artifact text successfully."""
        project_dir, calc_slug, step_id, calc_dir = project_with_step
        
        # Create raw directory and file
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        
        test_content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        scf_out = raw_dir / "scf.out"
        scf_out.write_text(test_content)
        
        result = QVService.read_step_artifact_text(
            project_root=project_dir,
            calculation_selector=calc_slug,
            step_selector=step_id,
            artifact_path="scf.out",
        )
        
        assert "content" in result
        assert result["content"] == test_content
        assert result["truncated"] is False
        assert result["total_bytes"] == len(test_content.encode('utf-8'))
        assert "resolved_path" in result
    
    def test_read_step_artifact_text_truncation(self, project_with_step):
        """Test reading artifact text with truncation."""
        project_dir, calc_slug, step_id, calc_dir = project_with_step
        
        # Create raw directory and file with many lines
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        
        lines = [f"Line {i}" for i in range(100)]
        test_content = "\n".join(lines)
        scf_out = raw_dir / "scf.out"
        scf_out.write_text(test_content)
        
        # Read with truncation (head + tail)
        result = QVService.read_step_artifact_text(
            project_root=project_dir,
            calculation_selector=calc_slug,
            step_selector=step_id,
            artifact_path="scf.out",
            head_lines=5,
            tail_lines=5,
        )
        
        assert "content" in result
        assert result["truncated"] is True
        assert "truncated" in result["content"].lower()
        assert "Line 0" in result["content"]  # First line
        assert "Line 99" in result["content"]  # Last line
    
    def test_read_step_artifact_text_path_traversal_blocked(self, project_with_step, tmp_path):
        """Test that path traversal is blocked (security)."""
        project_dir, calc_slug, step_id, calc_dir = project_with_step
        
        # Create a file outside raw directory
        outside_file = tmp_path / "outside.txt"
        outside_file.write_text("secret content")
        
        # Try to read with path traversal (should fail)
        with pytest.raises(APIError, match="Security violation|Invalid artifact path"):
            QVService.read_step_artifact_text(
                project_root=project_dir,
                calculation_selector=calc_slug,
                step_selector=step_id,
                artifact_path="../outside.txt",  # Path traversal attempt
            )
        
        # Try with absolute path (should also fail)
        with pytest.raises(APIError, match="Security violation|Invalid artifact path"):
            QVService.read_step_artifact_text(
                project_root=project_dir,
                calculation_selector=calc_slug,
                step_selector=step_id,
                artifact_path=str(outside_file),  # Absolute path
            )
    
    def test_read_step_artifact_text_directory_rejected(self, project_with_step):
        """Test that directories are rejected (security)."""
        project_dir, calc_slug, step_id, calc_dir = project_with_step
        
        # Create raw directory and a subdirectory
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        subdir = raw_dir / "subdir"
        subdir.mkdir()
        
        # Try to read directory (should fail)
        with pytest.raises(APIError, match="directory"):
            QVService.read_step_artifact_text(
                project_root=project_dir,
                calculation_selector=calc_slug,
                step_selector=step_id,
                artifact_path="subdir",
            )
    
    def test_read_step_artifact_text_nonexistent_file(self, project_with_step):
        """Test reading non-existent file raises error."""
        project_dir, calc_slug, step_id, calc_dir = project_with_step
        
        # Create raw directory (but no file)
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(exist_ok=True)
        
        # Try to read non-existent file (should fail)
        with pytest.raises(APIError, match="not found"):
            QVService.read_step_artifact_text(
                project_root=project_dir,
                calculation_selector=calc_slug,
                step_selector=step_id,
                artifact_path="nonexistent.out",
            )

