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
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        analysis_dir = get_analysis_dir(calculation_dir)
        
        assert analysis_dir == calculation_dir / "analysis"
    
    def test_get_artifact_path_scf(self, tmp_path):
        """Test SCF artifact path."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        
        path = get_artifact_path(calculation_dir, AnalysisType.SCF)
        
        assert path == calculation_dir / "analysis" / "scf.json"
    
    def test_get_artifact_path_dos(self, tmp_path):
        """Test DOS artifact path."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        
        path = get_artifact_path(calculation_dir, AnalysisType.DOS)
        
        assert path == calculation_dir / "analysis" / "dos.json"
    
    def test_get_artifact_path_bands(self, tmp_path):
        """Test bands artifact path."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        
        path = get_artifact_path(calculation_dir, AnalysisType.BANDS)
        
        assert path == calculation_dir / "analysis" / "bands.json"
    
    def test_get_artifact_path_string_type(self, tmp_path):
        """Test artifact path with string type."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        
        path = get_artifact_path(calculation_dir, "scf")
        
        assert path == calculation_dir / "analysis" / "scf.json"


class TestArtifactReadWrite:
    """Tests for artifact read/write operations."""
    
    def test_write_artifact_creates_dir(self, tmp_path):
        """Test that write_artifact creates analysis directory."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        data = {"test": "data", "value": 42}
        path = write_artifact(calculation_dir, AnalysisType.SCF, data)
        
        assert path.exists()
        assert (calculation_dir / "analysis").exists()
    
    def test_write_artifact_adds_metadata(self, tmp_path):
        """Test that write_artifact adds metadata."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        data = {"test": "data"}
        write_artifact(calculation_dir, AnalysisType.SCF, data)
        
        # Read back and check metadata
        path = get_artifact_path(calculation_dir, AnalysisType.SCF)
        content = json.loads(path.read_text())
        
        assert "_artifact_meta" in content
        assert content["_artifact_meta"]["analysis_type"] == "scf"
        assert "created_at" in content["_artifact_meta"]
    
    def test_read_artifact_returns_none_if_missing(self, tmp_path):
        """Test that read_artifact returns None for missing file."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        result = read_artifact(calculation_dir, AnalysisType.SCF)
        
        assert result is None
    
    def test_read_artifact_returns_data(self, tmp_path):
        """Test that read_artifact returns written data."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        original = {"test": "data", "value": 42}
        write_artifact(calculation_dir, AnalysisType.SCF, original)
        
        result = read_artifact(calculation_dir, AnalysisType.SCF)
        
        assert result["test"] == "data"
        assert result["value"] == 42
    
    def test_artifact_exists_true(self, tmp_path):
        """Test artifact_exists returns True when artifact exists."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        write_artifact(calculation_dir, AnalysisType.SCF, {"test": "data"})
        
        assert artifact_exists(calculation_dir, AnalysisType.SCF) is True
    
    def test_artifact_exists_false(self, tmp_path):
        """Test artifact_exists returns False when artifact missing."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        assert artifact_exists(calculation_dir, AnalysisType.SCF) is False


class TestArtifactDeletion:
    """Tests for artifact deletion."""
    
    def test_delete_artifact_removes_file(self, tmp_path):
        """Test that delete_artifact removes the file."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        write_artifact(calculation_dir, AnalysisType.SCF, {"test": "data"})
        assert artifact_exists(calculation_dir, AnalysisType.SCF)
        
        deleted = delete_artifact(calculation_dir, AnalysisType.SCF)
        
        assert deleted is True
        assert artifact_exists(calculation_dir, AnalysisType.SCF) is False
    
    def test_delete_artifact_returns_false_if_missing(self, tmp_path):
        """Test delete_artifact returns False for missing file."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        deleted = delete_artifact(calculation_dir, AnalysisType.SCF)
        
        assert deleted is False
    
    def test_clear_analysis_artifacts(self, tmp_path):
        """Test clearing all analysis artifacts."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        # Create multiple artifacts
        write_artifact(calculation_dir, AnalysisType.SCF, {"test": "scf"})
        write_artifact(calculation_dir, AnalysisType.DOS, {"test": "dos"})
        write_artifact(calculation_dir, AnalysisType.BANDS, {"test": "bands"})
        
        deleted_count = clear_analysis_artifacts(calculation_dir)
        
        assert deleted_count == 3
        assert not artifact_exists(calculation_dir, AnalysisType.SCF)
        assert not artifact_exists(calculation_dir, AnalysisType.DOS)
        assert not artifact_exists(calculation_dir, AnalysisType.BANDS)
    
    def test_clear_analysis_artifacts_no_dir(self, tmp_path):
        """Test clearing artifacts when analysis dir doesn't exist."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        
        deleted_count = clear_analysis_artifacts(calculation_dir)
        
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
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        raw_dir = calculation_dir / "raw"
        raw_dir.mkdir()
        
        # Pre-create an artifact
        cached_data = {
            "converged": True,
            "iterations": [{"iteration": 1, "total_energy_ry": -100.0, "scf_accuracy_ry": 1e-8}],
            "total_energy_ry": -100.0,
            "fermi_energy_ev": 5.5,
        }
        write_artifact(calculation_dir, AnalysisType.SCF, cached_data)
        
        status = ensure_analysis_artifact(
            analysis_type=AnalysisType.SCF,
            calculation_dir=calculation_dir,
            raw_dir=raw_dir,
            force=False,
        )
        
        assert status.ok is True
        assert status.parsed_fresh is False  # Should use cache
        assert status.summary is not None
    
    def test_force_reparses(self, tmp_path):
        """Test that force=True triggers re-parsing."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        raw_dir = calculation_dir / "raw"
        raw_dir.mkdir()
        
        # Pre-create an artifact
        write_artifact(calculation_dir, AnalysisType.SCF, {"test": "old"})
        
        # Even with artifact present, force=True should try to parse
        # Without actual QE output files, it will fail
        status = ensure_analysis_artifact(
            analysis_type=AnalysisType.SCF,
            calculation_dir=calculation_dir,
            raw_dir=raw_dir,
            force=True,
        )
        
        # Should fail because no actual QE output exists
        assert status.ok is False
        assert "Missing required files" in (status.error or "")
    
    def test_error_on_missing_files(self, tmp_path):
        """Test error when required files are missing."""
        calculation_dir = tmp_path / "calculations" / "test-calculation"
        calculation_dir.mkdir(parents=True)
        raw_dir = calculation_dir / "raw"
        raw_dir.mkdir()
        
        status = ensure_analysis_artifact(
            analysis_type=AnalysisType.BANDS,
            calculation_dir=calculation_dir,
            raw_dir=raw_dir,
        )
        
        assert status.ok is False
        assert status.error is not None
        assert "Missing" in status.error


class TestIntegrationWithQVService:
    """Integration tests with QVService."""

    def test_get_scf_uses_artifact(self, tmp_path):
        """Test that get_scf_convergence_data reads from artifact."""
        # This test verifies the integration without running actual QE
        from quantumvitas.api import QVService

        # Create a minimal project
        project_root = QVService.init_project(tmp_path / "test_project")

        # Create calculation with a step (need step for get_scf_convergence_data)
        calc_result = QVService(project_root).project.init_calculation("test-calculation")
        calc_dir = calc_result.absolute_path

        # Create raw directory (may already exist from init_calculation)
        raw_dir = calc_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        # Pre-create SCF artifact (simulating prior analysis)
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
        write_artifact(calc_dir, AnalysisType.SCF, cached_data)

        # Now call get_scf_convergence_data via domain accessor
        svc = QVService(project_root)
        result = svc.analysis.get_scf_convergence_data(
            calculation_selector="test-calculation",
            step_selector="scf",
        )

        assert result["converged"] is True
        assert result["total_energy_ry"] == -100.5
        assert result["fermi_energy_ev"] == 5.5
        assert len(result["iterations"]) == 2


def _get_reference_analysis(project_root, calculation_selector, analysis_type):
    """
    Get reference analysis data for demo projects.

    This is a helper function inlined from the legacy API for testing purposes.
    If the project was created from a demo snapshot that includes reference
    artifacts, this returns the reference data for comparison.

    Returns:
        Dict with reference analysis data, or None if not available.
    """
    import json
    from quantumvitas.core.project_utils import load_project_config
    from quantumvitas.core.resources import get_resources_dir

    project_root = Path(project_root).resolve()
    config = load_project_config(project_root)

    # Check if project has demo origin
    project_settings = config.get("project", {}).get("settings", {})
    origin = project_settings.get("origin", {})

    if origin.get("kind") != "demo":
        return None

    demo_id = origin.get("demo_id")
    if not demo_id:
        return None

    # Get reference_artifacts mapping
    reference_artifacts = origin.get("reference_artifacts", {})

    # If no reference_artifacts in project settings, try to load from snapshot meta
    if not reference_artifacts:
        import yaml
        resources_dir = get_resources_dir()
        demo_snapshot_path = resources_dir / "demo_projects" / f"{demo_id}.yml"
        if demo_snapshot_path.exists():
            try:
                snapshot_data = yaml.safe_load(demo_snapshot_path.read_text())
                snapshot_meta = snapshot_data.get("meta", {})
                reference_artifacts = snapshot_meta.get("reference_artifacts", {})
            except Exception:
                pass

    # Check if reference artifact exists for this analysis type
    artifact_filename = reference_artifacts.get(analysis_type)
    if not artifact_filename:
        return None

    # Load reference JSON from demo_projects directory
    resources_dir = get_resources_dir()
    reference_path = resources_dir / "demo_projects" / artifact_filename

    if not reference_path.exists():
        return None

    try:
        data = json.loads(reference_path.read_text())

        # Add metadata indicating this is reference data
        data["_is_reference"] = True
        data["_reference_source"] = demo_id

        # Return in format compatible with get_*_data methods
        if analysis_type == "scf":
            return {
                "calculation": calculation_selector,
                "step": None,
                "output_file": str(reference_path),
                "converged": data.get("converged"),
                "n_iterations": len(data.get("iterations", [])),
                "total_energy_ry": data.get("total_energy_ry"),
                "fermi_energy_ev": data.get("fermi_energy_ev"),
                "iterations": data.get("iterations", []),
                "calculation_type": data.get("calculation_type"),
                "n_electrons": data.get("n_electrons"),
                "n_kpoints": data.get("n_kpoints"),
                "ecutwfc_ry": data.get("ecutwfc_ry"),
                "units": data.get("units", {"energy": "Ry", "fermi": "eV"}),
                "_is_reference": True,
                "_reference_source": demo_id,
            }
        elif analysis_type == "dos":
            return {
                "calculation": calculation_selector,
                "step": None,
                "data_file": str(reference_path),
                "n_points": data.get("n_points", len(data.get("energies_ev", []))),
                "fermi_energy_ev": data.get("fermi_energy_ev"),
                "energy_range_ev": data.get("energy_range_ev"),
                "energies_ev": data.get("energies_ev", []),
                "dos_states_per_ev": data.get("dos_states_per_ev", []),
                "idos": data.get("idos"),
                "units": data.get("units", {"energy": "eV", "dos": "states/eV"}),
                "_is_reference": True,
                "_reference_source": demo_id,
            }
        elif analysis_type == "bands":
            return {
                "calculation": calculation_selector,
                "step": None,
                "data_file": str(reference_path),
                "n_bands": data.get("n_bands", 0),
                "n_kpoints": data.get("n_kpoints", 0),
                "fermi_energy_ev": data.get("fermi_energy_ev"),
                "k_distances": data.get("k_distances", []),
                "energies_ev": data.get("energies_ev", []),
                "high_symmetry_points": data.get("high_symmetry_points", []),
                "units": data.get("units", {"energy": "eV", "k_distance": "2π/a"}),
                "_is_reference": True,
                "_reference_source": demo_id,
            }

        return None

    except (json.JSONDecodeError, OSError):
        return None


class TestGetReferenceAnalysis:
    """Tests for reference analysis retrieval from demo projects."""

    def test_non_demo_project_returns_none(self, tmp_path):
        """Test that non-demo projects return None for reference analysis."""
        from quantumvitas.api import QVService

        # Create a regular (non-demo) project
        project_root = QVService.init_project(tmp_path / "regular_project")
        QVService(project_root).project.init_calculation("test-calculation")

        # Should return None since it's not a demo project
        result = _get_reference_analysis(
            project_root=project_root,
            calculation_selector="test-calculation",
            analysis_type="bands",
        )

        assert result is None

    def test_demo_project_returns_reference_data(self, tmp_path):
        """Test that demo projects return reference analysis data."""
        from quantumvitas.api import QVService
        from quantumvitas.core.project_utils import load_project_config, save_project_config

        # Create a project and manually set it up as a demo project
        project_root = QVService.init_project(tmp_path / "demo_project")
        QVService(project_root).project.init_calculation("si-bands")

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
        result = _get_reference_analysis(
            project_root=project_root,
            calculation_selector="si-bands",
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
        QVService(project_root).project.init_calculation("si-bands")

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
        result = _get_reference_analysis(
            project_root=project_root,
            calculation_selector="si-bands",
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
        QVService(project_root).project.init_calculation("si-bands")

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
        result = _get_reference_analysis(
            project_root=project_root,
            calculation_selector="si-bands",
            analysis_type="dos",
        )

        assert result is None

