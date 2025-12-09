"""
Unit tests for analysis artifacts module.

Tests the JSON artifact management for analysis data (SCF, DOS, bands).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np

from quantumvitas.analysis.artifacts import (
    AnalysisType,
    AnalysisStatus,
    get_analysis_dir,
    get_artifact_path,
    artifact_exists,
    read_artifact,
    write_artifact,
    delete_artifact,
    clear_analysis_artifacts,
    ensure_analysis_artifact,
    get_required_files_for_analysis,
)


class TestArtifactPaths:
    """Tests for artifact path generation."""
    
    def test_get_analysis_dir(self, tmp_path):
        """Test analysis directory path generation."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        analysis_dir = get_analysis_dir(workflow_dir)
        
        assert analysis_dir == workflow_dir / "analysis"
    
    def test_get_artifact_path_scf(self, tmp_path):
        """Test SCF artifact path."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        
        path = get_artifact_path(workflow_dir, AnalysisType.SCF)
        
        assert path == workflow_dir / "analysis" / "scf.json"
    
    def test_get_artifact_path_dos(self, tmp_path):
        """Test DOS artifact path."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        
        path = get_artifact_path(workflow_dir, AnalysisType.DOS)
        
        assert path == workflow_dir / "analysis" / "dos.json"
    
    def test_get_artifact_path_bands(self, tmp_path):
        """Test bands artifact path."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        
        path = get_artifact_path(workflow_dir, AnalysisType.BANDS)
        
        assert path == workflow_dir / "analysis" / "bands.json"
    
    def test_get_artifact_path_string_type(self, tmp_path):
        """Test artifact path with string type."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        
        path = get_artifact_path(workflow_dir, "scf")
        
        assert path == workflow_dir / "analysis" / "scf.json"


class TestArtifactReadWrite:
    """Tests for artifact read/write operations."""
    
    def test_write_artifact_creates_dir(self, tmp_path):
        """Test that write_artifact creates analysis directory."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        data = {"test": "data", "value": 42}
        path = write_artifact(workflow_dir, AnalysisType.SCF, data)
        
        assert path.exists()
        assert (workflow_dir / "analysis").exists()
    
    def test_write_artifact_adds_metadata(self, tmp_path):
        """Test that write_artifact adds metadata."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        data = {"test": "data"}
        write_artifact(workflow_dir, AnalysisType.SCF, data)
        
        # Read back and check metadata
        path = get_artifact_path(workflow_dir, AnalysisType.SCF)
        content = json.loads(path.read_text())
        
        assert "_artifact_meta" in content
        assert content["_artifact_meta"]["analysis_type"] == "scf"
        assert "created_at" in content["_artifact_meta"]
    
    def test_read_artifact_returns_none_if_missing(self, tmp_path):
        """Test that read_artifact returns None for missing file."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        result = read_artifact(workflow_dir, AnalysisType.SCF)
        
        assert result is None
    
    def test_read_artifact_returns_data(self, tmp_path):
        """Test that read_artifact returns written data."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        original = {"test": "data", "value": 42}
        write_artifact(workflow_dir, AnalysisType.SCF, original)
        
        result = read_artifact(workflow_dir, AnalysisType.SCF)
        
        assert result["test"] == "data"
        assert result["value"] == 42
    
    def test_artifact_exists_true(self, tmp_path):
        """Test artifact_exists returns True when artifact exists."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        write_artifact(workflow_dir, AnalysisType.SCF, {"test": "data"})
        
        assert artifact_exists(workflow_dir, AnalysisType.SCF) is True
    
    def test_artifact_exists_false(self, tmp_path):
        """Test artifact_exists returns False when artifact missing."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        assert artifact_exists(workflow_dir, AnalysisType.SCF) is False


class TestArtifactDeletion:
    """Tests for artifact deletion."""
    
    def test_delete_artifact_removes_file(self, tmp_path):
        """Test that delete_artifact removes the file."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        write_artifact(workflow_dir, AnalysisType.SCF, {"test": "data"})
        assert artifact_exists(workflow_dir, AnalysisType.SCF)
        
        deleted = delete_artifact(workflow_dir, AnalysisType.SCF)
        
        assert deleted is True
        assert artifact_exists(workflow_dir, AnalysisType.SCF) is False
    
    def test_delete_artifact_returns_false_if_missing(self, tmp_path):
        """Test delete_artifact returns False for missing file."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        deleted = delete_artifact(workflow_dir, AnalysisType.SCF)
        
        assert deleted is False
    
    def test_clear_analysis_artifacts(self, tmp_path):
        """Test clearing all analysis artifacts."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        # Create multiple artifacts
        write_artifact(workflow_dir, AnalysisType.SCF, {"test": "scf"})
        write_artifact(workflow_dir, AnalysisType.DOS, {"test": "dos"})
        write_artifact(workflow_dir, AnalysisType.BANDS, {"test": "bands"})
        
        deleted_count = clear_analysis_artifacts(workflow_dir)
        
        assert deleted_count == 3
        assert not artifact_exists(workflow_dir, AnalysisType.SCF)
        assert not artifact_exists(workflow_dir, AnalysisType.DOS)
        assert not artifact_exists(workflow_dir, AnalysisType.BANDS)
    
    def test_clear_analysis_artifacts_no_dir(self, tmp_path):
        """Test clearing artifacts when analysis dir doesn't exist."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        
        deleted_count = clear_analysis_artifacts(workflow_dir)
        
        assert deleted_count == 0


class TestAnalysisStatus:
    """Tests for AnalysisStatus dataclass."""
    
    def test_to_dict_success(self):
        """Test AnalysisStatus.to_dict for successful status."""
        status = AnalysisStatus(
            ok=True,
            analysis_type="scf",
            artifact_path="/path/to/scf.json",
            parsed_fresh=True,
            summary={"converged": True, "n_iterations": 10},
        )
        
        result = status.to_dict()
        
        assert result["ok"] is True
        assert result["analysis_type"] == "scf"
        assert result["artifact_path"] == "/path/to/scf.json"
        assert result["parsed_fresh"] is True
        assert result["error"] is None
        assert result["summary"]["converged"] is True
    
    def test_to_dict_error(self):
        """Test AnalysisStatus.to_dict for error status."""
        status = AnalysisStatus(
            ok=False,
            analysis_type="bands",
            error="Bands file not found",
        )
        
        result = status.to_dict()
        
        assert result["ok"] is False
        assert result["analysis_type"] == "bands"
        assert result["artifact_path"] is None
        assert result["error"] == "Bands file not found"


class TestGetRequiredFiles:
    """Tests for get_required_files_for_analysis."""
    
    def test_scf_finds_output(self, tmp_path):
        """Test finding SCF output file."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create a fake SCF output file
        (raw_dir / "scf_scf.pw.out").write_text("dummy content")
        
        result = get_required_files_for_analysis(AnalysisType.SCF, raw_dir)
        
        assert result["found"] is True
        assert "scf_output" in result["files"]
    
    def test_scf_not_found(self, tmp_path):
        """Test when SCF output is missing."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        result = get_required_files_for_analysis(AnalysisType.SCF, raw_dir)
        
        assert result["found"] is False
        assert len(result["missing"]) > 0
    
    def test_dos_finds_file(self, tmp_path):
        """Test finding DOS data file."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create a fake DOS file
        (raw_dir / "prefix.dos.dat").write_text("# dummy DOS data")
        
        result = get_required_files_for_analysis(AnalysisType.DOS, raw_dir)
        
        assert result["found"] is True
        assert "dos_data" in result["files"]
    
    def test_bands_finds_gnu_file(self, tmp_path):
        """Test finding bands.dat.gnu file."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        
        # Create a fake bands file
        (raw_dir / "bands.dat.gnu").write_text("0.0 -5.0")
        
        result = get_required_files_for_analysis(AnalysisType.BANDS, raw_dir)
        
        assert result["found"] is True
        assert "bands_gnu" in result["files"]


class TestEnsureAnalysisArtifact:
    """Tests for ensure_analysis_artifact function."""
    
    def test_returns_cached_if_exists(self, tmp_path):
        """Test that cached artifact is returned without re-parsing."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        raw_dir = workflow_dir / "raw"
        raw_dir.mkdir()
        
        # Pre-create an artifact
        cached_data = {
            "converged": True,
            "iterations": [{"iteration": 1, "total_energy_ry": -100.0, "scf_accuracy_ry": 1e-8}],
            "total_energy_ry": -100.0,
            "fermi_energy_ev": 5.5,
        }
        write_artifact(workflow_dir, AnalysisType.SCF, cached_data)
        
        status = ensure_analysis_artifact(
            analysis_type=AnalysisType.SCF,
            workflow_dir=workflow_dir,
            raw_dir=raw_dir,
            force=False,
        )
        
        assert status.ok is True
        assert status.parsed_fresh is False  # Should use cache
        assert status.summary is not None
    
    def test_force_reparses(self, tmp_path):
        """Test that force=True triggers re-parsing."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        raw_dir = workflow_dir / "raw"
        raw_dir.mkdir()
        
        # Pre-create an artifact
        write_artifact(workflow_dir, AnalysisType.SCF, {"test": "old"})
        
        # Even with artifact present, force=True should try to parse
        # Without actual QE output files, it will fail
        status = ensure_analysis_artifact(
            analysis_type=AnalysisType.SCF,
            workflow_dir=workflow_dir,
            raw_dir=raw_dir,
            force=True,
        )
        
        # Should fail because no actual QE output exists
        assert status.ok is False
        assert "Missing required files" in (status.error or "")
    
    def test_error_on_missing_files(self, tmp_path):
        """Test error when required files are missing."""
        workflow_dir = tmp_path / "workflows" / "test-workflow"
        workflow_dir.mkdir(parents=True)
        raw_dir = workflow_dir / "raw"
        raw_dir.mkdir()
        
        status = ensure_analysis_artifact(
            analysis_type=AnalysisType.BANDS,
            workflow_dir=workflow_dir,
            raw_dir=raw_dir,
        )
        
        assert status.ok is False
        assert status.error is not None
        assert "Missing" in status.error


class TestIntegrationWithQVService:
    """Integration tests with QVService."""
    
    def test_ensure_workflow_analysis_method_exists(self):
        """Test that QVService has ensure_workflow_analysis method."""
        from quantumvitas.api import QVService
        
        assert hasattr(QVService, "ensure_workflow_analysis")
        assert callable(QVService.ensure_workflow_analysis)
    
    def test_get_scf_uses_artifact(self, tmp_path):
        """Test that get_scf_convergence_data reads from artifact."""
        # This test verifies the integration without running actual QE
        from quantumvitas.api import QVService
        
        # Create a minimal project
        project_root = QVService.init_project(tmp_path / "test_project")
        
        # Create workflow
        QVService.init_workflow(project_root, "test-workflow")
        
        # Create raw directory (may already exist from init_workflow)
        raw_dir = project_root / "workflows" / "test-workflow" / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Pre-create SCF artifact (simulating prior analysis)
        workflow_dir = project_root / "workflows" / "test-workflow"
        cached_data = {
            "converged": True,
            "iterations": [
                {"iteration": 1, "total_energy_ry": -100.0, "scf_accuracy_ry": 1e-6},
                {"iteration": 2, "total_energy_ry": -100.5, "scf_accuracy_ry": 1e-8},
            ],
            "total_energy_ry": -100.5,
            "fermi_energy_ev": 5.5,
            "calculation_type": "scf",
            "n_electrons": 8.0,
            "n_kpoints": 4,
            "ecutwfc_ry": 30.0,
            "source_file": str(raw_dir / "scf.out"),
            "units": {"energy": "Ry", "fermi": "eV"},
        }
        write_artifact(workflow_dir, AnalysisType.SCF, cached_data)
        
        # Now call get_scf_convergence_data - should read from artifact
        result = QVService.get_scf_convergence_data(
            project_root=project_root,
            workflow_selector="test-workflow",
            step_selector="scf",
        )
        
        assert result["converged"] is True
        assert result["total_energy_ry"] == -100.5
        assert result["fermi_energy_ev"] == 5.5
        assert len(result["iterations"]) == 2


class TestGetReferenceAnalysis:
    """Tests for QVService.get_reference_analysis."""
    
    def test_non_demo_project_returns_none(self, tmp_path):
        """Test that non-demo projects return None for reference analysis."""
        from quantumvitas.api import QVService
        
        # Create a regular (non-demo) project
        project_root = QVService.init_project(tmp_path / "regular_project")
        QVService.init_workflow(project_root, "test-workflow")
        
        # Should return None since it's not a demo project
        result = QVService.get_reference_analysis(
            project_root=project_root,
            workflow_selector="test-workflow",
            analysis_type="bands",
        )
        
        assert result is None
    
    def test_demo_project_returns_reference_data(self, tmp_path):
        """Test that demo projects return reference analysis data."""
        from quantumvitas.api import QVService
        from quantumvitas.core.project_utils import load_project_config, save_project_config
        
        # Create a project and manually set it up as a demo project
        project_root = QVService.init_project(tmp_path / "demo_project")
        QVService.init_workflow(project_root, "si-bands")
        
        # Add demo origin info to project settings
        config = load_project_config(project_root)
        if "project" not in config:
            config["project"] = {}
        if "settings" not in config["project"]:
            config["project"]["settings"] = {}
        config["project"]["settings"]["origin"] = {
            "kind": "demo",
            "demo_id": "si_bands_demo",
            "reference_artifacts": {
                "bands": "si_bands_demo.bands.json",
                "scf": "si_bands_demo.scf.json",
            }
        }
        save_project_config(project_root, config)
        
        # Should return reference data
        result = QVService.get_reference_analysis(
            project_root=project_root,
            workflow_selector="si-bands",
            analysis_type="bands",
        )
        
        assert result is not None
        assert "_is_reference" in result
        assert result["_is_reference"] is True
        assert result["_reference_source"] == "si_bands_demo"
        # Check that bands data has expected fields
        assert "k_distances" in result
        assert "energies_ev" in result
        assert "fermi_energy_ev" in result
        assert "high_symmetry_points" in result
        assert result["n_bands"] == 8
    
    def test_demo_project_scf_reference(self, tmp_path):
        """Test SCF reference data from demo project."""
        from quantumvitas.api import QVService
        from quantumvitas.core.project_utils import load_project_config, save_project_config
        
        # Create a project and manually set it up as a demo project
        project_root = QVService.init_project(tmp_path / "demo_project_scf")
        QVService.init_workflow(project_root, "si-bands")
        
        # Add demo origin info
        config = load_project_config(project_root)
        config["project"]["settings"] = {
            "origin": {
                "kind": "demo",
                "demo_id": "si_bands_demo",
                "reference_artifacts": {
                    "bands": "si_bands_demo.bands.json",
                    "scf": "si_bands_demo.scf.json",
                }
            }
        }
        save_project_config(project_root, config)
        
        # Get SCF reference
        result = QVService.get_reference_analysis(
            project_root=project_root,
            workflow_selector="si-bands",
            analysis_type="scf",
        )
        
        assert result is not None
        assert result["_is_reference"] is True
        assert "converged" in result
        assert "iterations" in result
        assert result["converged"] is True
    
    def test_missing_artifact_type_returns_none(self, tmp_path):
        """Test that missing artifact type returns None."""
        from quantumvitas.api import QVService
        from quantumvitas.core.project_utils import load_project_config, save_project_config
        
        # Create a demo project without DOS reference
        project_root = QVService.init_project(tmp_path / "demo_no_dos")
        QVService.init_workflow(project_root, "si-bands")
        
        config = load_project_config(project_root)
        config["project"]["settings"] = {
            "origin": {
                "kind": "demo",
                "demo_id": "si_bands_demo",
                "reference_artifacts": {
                    "bands": "si_bands_demo.bands.json",
                    "scf": "si_bands_demo.scf.json",
                    # No DOS artifact
                }
            }
        }
        save_project_config(project_root, config)
        
        # Should return None for DOS (not available)
        result = QVService.get_reference_analysis(
            project_root=project_root,
            workflow_selector="si-bands",
            analysis_type="dos",
        )
        
        assert result is None

