"""
Unit tests for QVService GUI-ready methods.

Tests the pure data methods that return JSON-serializable results.
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from quantumvitas.api import QVService, QVServiceError


class TestGetProjectSummary:
    """Tests for QVService.get_project_summary()."""
    
    def test_returns_project_info(self, tmp_path):
        """Test that get_project_summary returns correct structure."""
        # Create a minimal project
        project_root = QVService.init_project(tmp_path / "test_project", name="Test Project")
        
        summary = QVService.get_project_summary(project_root)
        
        assert "id" in summary
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
        QVService.init_calculation(project_root, "calculation1")
        QVService.init_calculation(project_root, "calculation2")
        
        summary = QVService.get_project_summary(project_root)
        
        assert summary["n_calculations"] == 2
        assert "calculation1" in summary["calculation_names"]
        assert "calculation2" in summary["calculation_names"]


class TestListStructuresData:
    """Tests for QVService.list_structures_data()."""
    
    def test_returns_list(self, tmp_path):
        """Test that list_structures_data returns a list."""
        project_root = QVService.init_project(tmp_path / "test_project")
        
        structures = QVService.list_structures_data(project_root)
        
        assert isinstance(structures, list)
        assert len(structures) == 0
    
    def test_structure_entry_schema(self, tmp_path, sample_structure_file):
        """Test that structure entries have expected fields."""
        project_root = QVService.init_project(tmp_path / "test_project")
        
        # Import a structure
        QVService.import_structure(project_root, sample_structure_file, name="Test Structure")
        
        structures = QVService.list_structures_data(project_root)
        
        assert len(structures) == 1
        entry = structures[0]
        
        # Required fields
        assert "id" in entry
        assert "name" in entry
        assert "slug" in entry
        assert "path" in entry
        assert "absolute_path" in entry
        
        # Optional fields (should be present for valid structure)
        assert "formula" in entry
        assert "n_atoms" in entry
        assert "lattice_params" in entry


class TestListCalculationsData:
    """Tests for QVService.list_calculations_data()."""
    
    def test_returns_list(self, tmp_path):
        """Test that list_calculations_data returns a list."""
        project_root = QVService.init_project(tmp_path / "test_project")
        
        calculations = QVService.list_calculations_data(project_root)
        
        assert isinstance(calculations, list)
        assert len(calculations) == 0
    
    def test_calculation_entry_schema(self, tmp_path):
        """Test that calculation entries have expected fields."""
        project_root = QVService.init_project(tmp_path / "test_project")
        QVService.init_calculation(project_root, "test-calculation")
        
        calculations = QVService.list_calculations_data(project_root)
        
        assert len(calculations) == 1
        entry = calculations[0]
        
        # Required fields
        assert "id" in entry
        assert "name" in entry
        assert "slug" in entry
        assert "path" in entry
        assert "absolute_path" in entry
        
        # Calculation-specific fields
        assert "mode" in entry
        assert "n_steps" in entry
        assert "steps" in entry


class TestGetStructureVisData:
    """Tests for QVService.get_structure_vis_data()."""
    
    def test_returns_visualization_data(self, tmp_path, sample_structure_file):
        """Test that get_structure_vis_data returns complete data."""
        project_root = QVService.init_project(tmp_path / "test_project")
        QVService.import_structure(project_root, sample_structure_file, name="si")
        
        vis_data = QVService.get_structure_vis_data(project_root, "si")
        
        # Core fields
        assert "structure_id" in vis_data
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
        
        vis_1x1x1 = QVService.get_structure_vis_data(project_root, "si", supercell=(1, 1, 1))
        vis_2x2x2 = QVService.get_structure_vis_data(project_root, "si", supercell=(2, 2, 2))
        
        # 2x2x2 supercell should have 8x the atoms
        assert vis_2x2x2["n_atoms"] == vis_1x1x1["n_atoms"] * 8
    
    def test_boundary_repeat_adds_image_atoms(self, tmp_path, sample_structure_file):
        """Test that boundary repeat generates image atoms for primitive cell."""
        project_root = QVService.init_project(tmp_path / "test_project")
        QVService.import_structure(project_root, sample_structure_file, name="si")
        
        vis_plain = QVService.get_structure_vis_data(
            project_root, "si", 
            supercell=(1, 1, 1), 
            repeat_boundary=False,
            display_mode="primitive"
        )
        vis_repeat = QVService.get_structure_vis_data(
            project_root, "si", 
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
        
        # Boundary atoms count should be > 0 when repeat_boundary=True
        assert vis_plain.get("n_boundary_atoms", 0) == 0, "No boundary atoms when repeat_boundary=False"
        assert vis_repeat.get("n_boundary_atoms", 0) > 0, (
            f"Boundary repeat should add image atoms. Got n_boundary_atoms={vis_repeat.get('n_boundary_atoms', 0)}"
        )
        
        # Verify contract: n_atoms = canonical + boundary
        # (boundary atoms are included in atoms array)
        assert vis_repeat["n_atoms"] >= vis_plain["n_atoms"] + vis_repeat.get("n_boundary_atoms", 0), (
            f"n_atoms should include boundary atoms. "
            f"Got n_atoms={vis_repeat['n_atoms']} "
            f"plain_n_atoms={vis_plain['n_atoms']} "
            f"n_boundary_atoms={vis_repeat.get('n_boundary_atoms', 0)}"
        )
        
        # Check that boundary_atoms array is populated
        assert "boundary_atoms" in vis_repeat, "Response should include boundary_atoms field"
        assert len(vis_repeat["boundary_atoms"]) > 0, "boundary_atoms array should be non-empty"
        
        # NEW CONTRACT: boundary_atoms is a subset of atoms (those with is_boundary=True)
        # Verify all boundary_atoms are in atoms array and marked with is_boundary
        boundary_atom_positions = {tuple(atom["cart_coords"]) for atom in vis_repeat["boundary_atoms"]}
        all_atom_positions = {tuple(atom["cart_coords"]) for atom in vis_repeat["atoms"]}
        
        # All boundary atoms should be in the main atoms array
        assert boundary_atom_positions.issubset(all_atom_positions), (
            "All boundary_atoms should be included in atoms array (new contract)"
        )
        
        # Verify boundary atoms are marked with is_boundary flag
        atoms_with_boundary_flag = {
            tuple(atom["cart_coords"]) 
            for atom in vis_repeat["atoms"] 
            if atom.get("is_boundary", False)
        }
        assert atoms_with_boundary_flag == boundary_atom_positions, (
            "Atoms with is_boundary=True should match boundary_atoms positions"
        )
    
    def test_not_found_raises_error(self, tmp_path):
        """Test that missing structure raises error."""
        project_root = QVService.init_project(tmp_path / "test_project")
        
        with pytest.raises(Exception):  # SelectorNotFoundError or similar
            QVService.get_structure_vis_data(project_root, "nonexistent")


class TestJSONSerializability:
    """Tests that all returned data is JSON-serializable."""
    
    def test_project_summary_serializable(self, tmp_path):
        """Test that project summary is JSON-serializable."""
        import json
        project_root = QVService.init_project(tmp_path / "test_project")
        
        summary = QVService.get_project_summary(project_root)
        
        # Should not raise
        json_str = json.dumps(summary)
        assert json_str
    
    def test_structures_list_serializable(self, tmp_path):
        """Test that structures list is JSON-serializable."""
        import json
        project_root = QVService.init_project(tmp_path / "test_project")
        
        structures = QVService.list_structures_data(project_root)
        
        json_str = json.dumps(structures)
        assert json_str
    
    def test_calculations_list_serializable(self, tmp_path):
        """Test that calculations list is JSON-serializable."""
        import json
        project_root = QVService.init_project(tmp_path / "test_project")
        
        calculations = QVService.list_calculations_data(project_root)
        
        json_str = json.dumps(calculations)
        assert json_str
    
    def test_structure_vis_serializable(self, tmp_path, sample_structure_file):
        """Test that structure vis data is JSON-serializable."""
        import json
        project_root = QVService.init_project(tmp_path / "test_project")
        QVService.import_structure(project_root, sample_structure_file, name="si")
        
        vis_data = QVService.get_structure_vis_data(project_root, "si")
        
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

