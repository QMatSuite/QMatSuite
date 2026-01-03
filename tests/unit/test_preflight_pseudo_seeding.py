"""
Unit tests for preflight pseudo auto-seeding.

Tests the _preflight_check_and_seed_pseudos function which:
1. Checks if pseudos exist in project/pseudo
2. Auto-seeds from resources/pseudo (internal library) if needed
3. Verifies SHA256 if provided in species_map

This ensures that demo projects with species_map pointing to internal library
pseudos will work without manual pseudo copying.
"""

from __future__ import annotations

import shutil
import pytest
from pathlib import Path
from typing import Dict, Any

from quantumvitas.api import QVService
from quantumvitas.core.pseudo_provenance import compute_sha256_file


class TestPreflightPseudoSeeding:
    """Test pseudo auto-seeding in preflight checks."""
    
    @pytest.fixture
    def temp_project(self, tmp_path: Path) -> Path:
        """Create a temporary project structure."""
        project_root = tmp_path / "test_project"
        project_root.mkdir()
        (project_root / "pseudo").mkdir()
        return project_root
    
    @pytest.fixture
    def internal_pseudo_dir(self, project_root_path: Path) -> Path:
        """Get the internal pseudo library path."""
        return project_root_path / "resources" / "pseudo"
    
    def test_no_species_map(self, temp_project: Path):
        """Test with no species_map - should pass."""
        result = QVService._preflight_check_and_seed_pseudos(
            project_root=temp_project,
            species_map=None,
            project_pseudo_dir=temp_project / "pseudo",
        )
        
        assert result["check"]["ok"] is True
        assert "error" not in result
    
    def test_empty_species_map(self, temp_project: Path):
        """Test with empty species_map - should pass."""
        result = QVService._preflight_check_and_seed_pseudos(
            project_root=temp_project,
            species_map={},
            project_pseudo_dir=temp_project / "pseudo",
        )
        
        assert result["check"]["ok"] is True
        assert "error" not in result
    
    def test_pseudo_already_in_project(self, temp_project: Path):
        """Test when pseudo already exists in project - no seeding needed."""
        pseudo_dir = temp_project / "pseudo"
        pseudo_file = pseudo_dir / "Si.test.UPF"
        pseudo_file.write_text("test pseudo content")
        
        species_map: Dict[str, Dict[str, Any]] = {
            "Si": {
                "pseudopot": "Si.test.UPF",
                "mass": 28.0855,
            }
        }
        
        result = QVService._preflight_check_and_seed_pseudos(
            project_root=temp_project,
            species_map=species_map,
            project_pseudo_dir=pseudo_dir,
        )
        
        assert result["check"]["ok"] is True
        assert "error" not in result
        assert pseudo_file.exists()
    
    def test_seed_from_internal_library(self, temp_project: Path, internal_pseudo_dir: Path):
        """Test auto-seeding from internal library."""
        # Skip if no internal pseudos available
        if not internal_pseudo_dir.exists():
            pytest.skip("Internal pseudo library not available")
        
        # Find a pseudo in internal library
        internal_pseudos = list(internal_pseudo_dir.glob("*.UPF"))
        if not internal_pseudos:
            pytest.skip("No pseudos in internal library")
        
        internal_pseudo = internal_pseudos[0]
        pseudo_name = internal_pseudo.name
        element = pseudo_name.split(".")[0]
        
        species_map: Dict[str, Dict[str, Any]] = {
            element: {
                "pseudopot": pseudo_name,
                "mass": 1.0,
            }
        }
        
        pseudo_dir = temp_project / "pseudo"
        project_pseudo = pseudo_dir / pseudo_name
        
        # Ensure pseudo doesn't exist in project
        assert not project_pseudo.exists()
        
        result = QVService._preflight_check_and_seed_pseudos(
            project_root=temp_project,
            species_map=species_map,
            project_pseudo_dir=pseudo_dir,
        )
        
        # Should succeed and seed the pseudo
        assert result["check"]["ok"] is True
        assert "seeded" in result["check"]["message"].lower()
        assert project_pseudo.exists()
        assert "error" not in result
    
    def test_seed_with_sha256_verification(self, temp_project: Path, internal_pseudo_dir: Path):
        """Test that SHA256 is verified after seeding."""
        if not internal_pseudo_dir.exists():
            pytest.skip("Internal pseudo library not available")
        
        internal_pseudos = list(internal_pseudo_dir.glob("*.UPF"))
        if not internal_pseudos:
            pytest.skip("No pseudos in internal library")
        
        internal_pseudo = internal_pseudos[0]
        pseudo_name = internal_pseudo.name
        element = pseudo_name.split(".")[0]
        
        # Compute correct SHA256
        correct_sha256 = compute_sha256_file(internal_pseudo)
        
        species_map: Dict[str, Dict[str, Any]] = {
            element: {
                "pseudopot": pseudo_name,
                "pseudo_sha256": correct_sha256,
                "mass": 1.0,
            }
        }
        
        pseudo_dir = temp_project / "pseudo"
        
        result = QVService._preflight_check_and_seed_pseudos(
            project_root=temp_project,
            species_map=species_map,
            project_pseudo_dir=pseudo_dir,
        )
        
        # Should succeed
        assert result["check"]["ok"] is True
        assert "error" not in result
    
    def test_sha256_mismatch_error(self, temp_project: Path, internal_pseudo_dir: Path):
        """Test that SHA256 mismatch is detected."""
        if not internal_pseudo_dir.exists():
            pytest.skip("Internal pseudo library not available")
        
        internal_pseudos = list(internal_pseudo_dir.glob("*.UPF"))
        if not internal_pseudos:
            pytest.skip("No pseudos in internal library")
        
        internal_pseudo = internal_pseudos[0]
        pseudo_name = internal_pseudo.name
        element = pseudo_name.split(".")[0]
        
        # Use wrong SHA256
        wrong_sha256 = "0" * 64
        
        species_map: Dict[str, Dict[str, Any]] = {
            element: {
                "pseudopot": pseudo_name,
                "pseudo_sha256": wrong_sha256,
                "mass": 1.0,
            }
        }
        
        pseudo_dir = temp_project / "pseudo"
        
        result = QVService._preflight_check_and_seed_pseudos(
            project_root=temp_project,
            species_map=species_map,
            project_pseudo_dir=pseudo_dir,
        )
        
        # Should fail with SHA256 mismatch
        assert result["check"]["ok"] is False
        assert "error" in result
        assert "SHA256" in result["error"] or "mismatch" in result["error"].lower()
    
    def test_missing_pseudo_error(self, temp_project: Path):
        """Test that missing pseudo is reported correctly."""
        species_map: Dict[str, Dict[str, Any]] = {
            "Xx": {
                "pseudopot": "Xx.nonexistent.UPF",
                "mass": 1.0,
            }
        }
        
        pseudo_dir = temp_project / "pseudo"
        
        result = QVService._preflight_check_and_seed_pseudos(
            project_root=temp_project,
            species_map=species_map,
            project_pseudo_dir=pseudo_dir,
        )
        
        # Should fail with missing pseudo
        assert result["check"]["ok"] is False
        assert "error" in result
        assert "not found" in result["error"].lower() or "missing" in result["error"].lower()
    
    def test_no_pseudopot_configured(self, temp_project: Path):
        """Test species entry without pseudopot configured."""
        species_map: Dict[str, Dict[str, Any]] = {
            "Si": {
                "mass": 28.0855,
                # No pseudopot field
            }
        }
        
        pseudo_dir = temp_project / "pseudo"
        
        result = QVService._preflight_check_and_seed_pseudos(
            project_root=temp_project,
            species_map=species_map,
            project_pseudo_dir=pseudo_dir,
        )
        
        # Should fail - no pseudopot configured
        assert result["check"]["ok"] is False
        assert "error" in result


class TestDiamondDemoPseudoSeeding:
    """
    Regression test: Diamond Wannier90 demo should pass preflight.
    
    The diamond demo has species_map with C.pz-vbc.UPF which should
    be auto-seeded from resources/pseudo.
    """
    
    def test_diamond_demo_preflight(self, tmp_path: Path, project_root_path: Path):
        """Diamond demo pseudo should be auto-seeded."""
        # Check if the pseudo exists in internal library
        internal_pseudo = project_root_path / "resources" / "pseudo" / "C.pz-vbc.UPF"
        if not internal_pseudo.exists():
            pytest.skip("C.pz-vbc.UPF not in internal library")
        
        # Create project structure
        project_root = tmp_path / "diamond_demo"
        project_root.mkdir()
        pseudo_dir = project_root / "pseudo"
        pseudo_dir.mkdir()
        
        # Species map from diamond demo
        species_map: Dict[str, Dict[str, Any]] = {
            "C": {
                "mass": 12.0,
                "pseudopot": "C.pz-vbc.UPF",
                "pseudo_basename": "C.pz-vbc.UPF",
                "pseudo_sha256": compute_sha256_file(internal_pseudo),
            }
        }
        
        result = QVService._preflight_check_and_seed_pseudos(
            project_root=project_root,
            species_map=species_map,
            project_pseudo_dir=pseudo_dir,
        )
        
        # Should succeed
        assert result["check"]["ok"] is True, f"Preflight failed: {result}"
        assert (pseudo_dir / "C.pz-vbc.UPF").exists()
        assert "error" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

