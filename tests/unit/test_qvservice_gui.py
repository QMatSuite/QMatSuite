"""
Unit tests for QVService GUI-ready methods.

Tests the pure data methods that return JSON-serializable results.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from quantumvitas.api import QVService, APIError


class TestGetProjectSummary:
    """Tests for QVService.project.get_summary()."""

    def test_returns_project_info(self, tmp_path):
        """Test that project.get_summary returns correct structure."""
        # Create a minimal project
        project_root = QVService.init_project(tmp_path / "test_project", name="Test Project")

        svc = QVService(project_root)
        summary = svc.project.get_summary()

        assert "ulid" in summary
        assert summary["name"] == "Test Project"
        assert "slug" in summary
        assert summary["path"] == str(project_root)
        assert summary["n_structures"] == 0
        assert summary["n_calculations"] == 0
        assert isinstance(summary["structure_names"], list)
        assert isinstance(summary["calculation_names"], list)

    def test_counts_resources(self, tmp_path):
        """Test that resource counts are accurate."""
        project_root = QVService.init_project(tmp_path / "test_project")

        # Create some calculations
        QVService(project_root).project.init_calculation("calculation1")
        QVService(project_root).project.init_calculation("calculation2")

        svc = QVService(project_root)
        summary = svc.project.get_summary()

        assert summary["n_calculations"] == 2
        assert "calculation1" in summary["calculation_names"]
        assert "calculation2" in summary["calculation_names"]


class TestGetStructureVisData:
    """Tests for QVService.get_structure_vis_data()."""
    
    def test_returns_visualization_data(self, tmp_path, sample_structure_file):
        """Test that get_structure_vis_data returns complete data."""
        project_root = QVService.init_project(tmp_path / "test_project")
        QVService.import_structure(project_root, sample_structure_file, name="si")
        
        svc = QVService(project_root)
        vis_data = svc.structure.get_vis_data("si")
        
        # Core fields
        assert "structure_ulid" in vis_data
        assert "structure_name" in vis_data
        assert "formula" in vis_data
        assert "n_atoms" in vis_data
        
        # Lattice data
        assert "lattice" in vis_data
        lattice = vis_data["lattice"]
        assert "matrix" in lattice
        assert len(lattice["matrix"]) == 3
        assert "a" in lattice
        assert "b" in lattice
        assert "c" in lattice
        assert "volume" in lattice
        
        # Atoms data
        assert "atoms" in vis_data
        assert len(vis_data["atoms"]) == vis_data["n_atoms"]
        
        if vis_data["atoms"]:
            atom = vis_data["atoms"][0]
            assert "element" in atom
            assert "cart_coords" in atom
            assert "frac_coords" in atom
            assert "color" in atom
            assert "radius" in atom
        
        # Bonds data
        assert "bonds" in vis_data
        assert "n_bonds" in vis_data
        
        # Element colors lookup
        assert "element_colors" in vis_data
    
    def test_supercell_increases_atoms(self, tmp_path, sample_structure_file):
        """Test that supercell parameter increases atom count."""
        project_root = QVService.init_project(tmp_path / "test_project")
        QVService.import_structure(project_root, sample_structure_file, name="si")
        
        svc = QVService(project_root)
        vis_1x1x1 = svc.structure.get_vis_data("si", supercell=(1, 1, 1))
        vis_2x2x2 = svc.structure.get_vis_data("si", supercell=(2, 2, 2))
        
        # 2x2x2 supercell should have 8x the atoms
        assert vis_2x2x2["n_atoms"] == vis_1x1x1["n_atoms"] * 8
    
    def test_boundary_repeat_adds_image_atoms(self, tmp_path, sample_structure_file):
        """Test that boundary repeat generates image atoms for primitive cell."""
        project_root = QVService.init_project(tmp_path / "test_project")
        QVService.import_structure(project_root, sample_structure_file, name="si")
        
        svc = QVService(project_root)
        vis_plain = svc.structure.get_vis_data(
            "si", 
            supercell=(1, 1, 1), 
            repeat_boundary=False,
            display_mode="primitive"
        )
        vis_repeat = svc.structure.get_vis_data(
            "si", 
            supercell=(1, 1, 1), 
            repeat_boundary=True,
            display_mode="primitive"
        )
        
        # NEW CONTRACT: atoms contains ALL display atoms (canonical + boundary)
        # So n_atoms increases when repeat_boundary=True
        assert vis_repeat["n_atoms"] > vis_plain["n_atoms"], (
            f"With repeat_boundary=True, n_atoms should increase. "
            f"Got plain={vis_plain['n_atoms']} repeat={vis_repeat['n_atoms']}"
        )
        
        # NEW CONTRACT (2024): boundary atoms are indicated by is_boundary flag in atoms array
        # n_boundary_atoms and boundary_atoms array are DEPRECATED (always 0/empty)
        # Count boundary atoms from atoms array using is_boundary flag
        plain_boundary_count = sum(1 for a in vis_plain["atoms"] if a.get("is_boundary", False))
        repeat_boundary_count = sum(1 for a in vis_repeat["atoms"] if a.get("is_boundary", False))
        
        assert plain_boundary_count == 0, "No boundary atoms when repeat_boundary=False"
        assert repeat_boundary_count > 0, (
            f"Boundary repeat should add image atoms with is_boundary=True flag. "
            f"Got {repeat_boundary_count} atoms with is_boundary=True"
        )
        
        # Verify contract: n_atoms = canonical + boundary
        # Count canonical atoms (those without is_boundary flag)
        canonical_count = sum(1 for a in vis_repeat["atoms"] if not a.get("is_boundary", False))
        assert vis_repeat["n_atoms"] == canonical_count + repeat_boundary_count, (
            f"n_atoms should equal canonical + boundary. "
            f"Got n_atoms={vis_repeat['n_atoms']} "
            f"canonical={canonical_count} boundary={repeat_boundary_count}"
        )
        
        # Verify boundary_atoms field exists (for backwards compatibility, may be empty)
        assert "boundary_atoms" in vis_repeat, "Response should include boundary_atoms field"
        # NOTE: boundary_atoms array is DEPRECATED and may be empty
        # The is_boundary flag on atoms is the authoritative source
    
    def test_not_found_raises_error(self, tmp_path):
        """Test that missing structure raises error."""
        project_root = QVService.init_project(tmp_path / "test_project")
        
        svc = QVService(project_root)
        with pytest.raises(Exception):  # SelectorNotFoundError or similar
            svc.structure.get_vis_data("nonexistent")


class TestJSONSerializability:
    """Tests that all returned data is JSON-serializable."""
    
    def test_project_summary_serializable(self, tmp_path):
        """Test that project summary is JSON-serializable."""
        import json
        project_root = QVService.init_project(tmp_path / "test_project")

        svc = QVService(project_root)
        summary = svc.project.get_summary()

        # Should not raise
        json_str = json.dumps(summary)
        assert json_str
    
    def test_structure_vis_serializable(self, tmp_path, sample_structure_file):
        """Test that structure vis data is JSON-serializable."""
        import json
        project_root = QVService.init_project(tmp_path / "test_project")
        QVService.import_structure(project_root, sample_structure_file, name="si")
        
        svc = QVService(project_root)
        vis_data = svc.structure.get_vis_data("si")
        
        json_str = json.dumps(vis_data)
        assert json_str
        
        # Verify roundtrip
        parsed = json.loads(json_str)
        assert parsed["n_atoms"] == vis_data["n_atoms"]


# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------

@pytest.fixture
def sample_structure_file(tmp_path):
    """Create a sample structure file for testing."""
    # Create a simple Si structure JSON
    structure_json = tmp_path / "si.json"
    structure_json.write_text('''{
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {
            "matrix": [
                [3.348898, 0.0, 1.933487],
                [1.116299, 3.157372, 1.933487],
                [0.0, 0.0, 3.866975]
            ],
            "pbc": [true, true, true]
        },
        "sites": [
            {
                "species": [{"element": "Si", "occu": 1}],
                "abc": [0.0, 0.0, 0.0],
                "xyz": [0.0, 0.0, 0.0],
                "properties": {}
            },
            {
                "species": [{"element": "Si", "occu": 1}],
                "abc": [0.25, 0.25, 0.25],
                "xyz": [1.116299, 0.789343, 1.933487],
                "properties": {}
            }
        ]
    }''')
    return structure_json

