"""
Unit tests for demo snapshot restore functionality.

Tests that demo snapshots can be loaded and materialized correctly,
ensuring that the project directory is populated with all necessary files.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from quantumvitas.api import QVService
from quantumvitas.core.resources import get_resources_dir
from quantumvitas.project.snapshot import ProjectSnapshot, materialize_project_from_snapshot


class TestDemoSnapshotRestore:
    """Test demo snapshot restore functionality."""
    
    def test_si_bands_demo_restore(self):
        """Test that si_bands_demo snapshot can be restored correctly."""
        resources_dir = get_resources_dir()
        snapshot_path = resources_dir / "demo_projects" / "si_bands_demo.yml"
        
        if not snapshot_path.exists():
            pytest.skip(f"Demo snapshot not found: {snapshot_path}")
        
        # Load snapshot
        with open(snapshot_path, "r") as f:
            snapshot_data = yaml.safe_load(f)
        
        snapshot = ProjectSnapshot.from_dict(snapshot_data)
        
        # Materialize in temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = materialize_project_from_snapshot(
                snapshot=snapshot,
                parent_dir=Path(tmpdir),
                new_project_name="test_si_bands",
            )
            
            # Verify project root exists
            assert project_root.exists(), f"Project root should exist: {project_root}"
            assert project_root.is_dir(), f"Project root should be a directory: {project_root}"
            
            # Verify project.qv.yml exists
            project_config = project_root / "project.qv.yml"
            assert project_config.exists(), f"project.qv.yml should exist: {project_config}"
            
            # Verify structures directory exists and has files
            structures_dir = project_root / "structures"
            assert structures_dir.exists(), f"structures directory should exist: {structures_dir}"
            structure_files = list(structures_dir.glob("*.json"))
            assert len(structure_files) > 0, f"At least one structure file should exist in {structures_dir}"
            
            # Verify calculations directory exists and has files
            calculations_dir = project_root / "calculations"
            assert calculations_dir.exists(), f"calculations directory should exist: {calculations_dir}"
            calculation_dirs = [d for d in calculations_dir.iterdir() if d.is_dir()]
            assert len(calculation_dirs) > 0, f"At least one calculation directory should exist in {calculations_dir}"
            
            # Verify at least one calculation has a calculation.yaml
            calculation_yamls = list(calculations_dir.glob("*/calculation.yaml"))
            assert len(calculation_yamls) > 0, f"At least one calculation.yaml should exist in {calculations_dir}"
            
            # Verify at least one calculation has step files
            step_files = list(calculations_dir.glob("*/steps/*.step.yaml"))
            assert len(step_files) > 0, f"At least one step file should exist in {calculations_dir}"
    
    def test_si_dos_demo_restore(self):
        """Test that si_dos_demo snapshot can be restored correctly."""
        resources_dir = get_resources_dir()
        snapshot_path = resources_dir / "demo_projects" / "si_dos_demo.yml"
        
        if not snapshot_path.exists():
            pytest.skip(f"Demo snapshot not found: {snapshot_path}")
        
        # Load snapshot
        with open(snapshot_path, "r") as f:
            snapshot_data = yaml.safe_load(f)
        
        snapshot = ProjectSnapshot.from_dict(snapshot_data)
        
        # Materialize in temp directory
        with tempfile.TemporaryDirectory() as tmpdir:
            project_root = materialize_project_from_snapshot(
                snapshot=snapshot,
                parent_dir=Path(tmpdir),
                new_project_name="test_si_dos",
            )
            
            # Verify project root exists
            assert project_root.exists(), f"Project root should exist: {project_root}"
            
            # Verify project.qv.yml exists
            project_config = project_root / "project.qv.yml"
            assert project_config.exists(), f"project.qv.yml should exist: {project_config}"
            
            # Verify structures directory exists
            structures_dir = project_root / "structures"
            assert structures_dir.exists(), f"structures directory should exist: {structures_dir}"
            
            # Verify calculations directory exists
            calculations_dir = project_root / "calculations"
            assert calculations_dir.exists(), f"calculations directory should exist: {calculations_dir}"
    
    def test_create_demo_project_via_api(self):
        """Test creating demo project via LegacyService.create_demo_project."""
        from quantumvitas._api_legacy import QVService as LegacyService

        with tempfile.TemporaryDirectory() as tmpdir:
            result = LegacyService.create_demo_project(
                target_dir=Path(tmpdir),
                name="test_demo",
                demo_id="si_bands_demo",
            )

            project_root = Path(result["project_root"])

            # Verify project root exists
            assert project_root.exists(), f"Project root should exist: {project_root}"

            # Verify project.qv.yml exists
            project_config = project_root / "project.qv.yml"
            assert project_config.exists(), f"project.qv.yml should exist: {project_config}"

            # Verify structures directory exists and has files
            structures_dir = project_root / "structures"
            assert structures_dir.exists(), f"structures directory should exist: {structures_dir}"
            structure_files = list(structures_dir.glob("*.json"))
            assert len(structure_files) > 0, f"At least one structure file should exist"

            # Verify calculations directory exists and has files
            calculations_dir = project_root / "calculations"
            assert calculations_dir.exists(), f"calculations directory should exist: {calculations_dir}"
            calculation_yamls = list(calculations_dir.glob("*/calculation.yaml"))
            assert len(calculation_yamls) > 0, f"At least one calculation.yaml should exist"

            # Verify project can be opened by QVService
            summary = LegacyService.get_project_summary(project_root)
            assert summary is not None, "Project summary should be available"
            assert summary["n_structures"] > 0, "Project should have at least one structure"
            assert summary["n_calculations"] > 0, "Project should have at least one calculation"
    
    def test_create_demo_project_with_invalid_demo_id(self):
        """Test that creating demo project with invalid demo_id raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(Exception) as exc_info:
                QVService.create_demo_project(
                    target_dir=Path(tmpdir),
                    name="test_demo",
                    demo_id="nonexistent_demo",
                )
            
            # Should raise an error about demo not found
            assert "not found" in str(exc_info.value).lower() or "demo" in str(exc_info.value).lower()

