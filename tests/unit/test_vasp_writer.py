"""Unit tests for VASP input writers."""

import pytest
from pathlib import Path
from pymatgen.core import Structure, Lattice
from quantumvitas.engine.vasp_writer import (
    write_poscar,
    write_incar,
    write_kpoints,
    write_potcar,
)


class TestVASPPOSCARWriter:
    """Test POSCAR writer."""
    
    def test_write_poscar(self, tmp_path):
        """Test writing POSCAR from pymatgen Structure."""
        structure = Structure(
            Lattice.cubic(5.43),
            ["Si", "Si"],
            [[0, 0, 0], [0.25, 0.25, 0.25]],
        )
        
        poscar_path = tmp_path / "POSCAR"
        write_poscar(structure, poscar_path)
        
        assert poscar_path.exists()
        content = poscar_path.read_text()
        assert "Si" in content
        # Check for lattice parameter (may have floating point precision)
        assert "5.4" in content  # Should contain 5.4xxx


class TestVASPINCARWriter:
    """Test INCAR writer."""
    
    def test_write_incar_basic(self, tmp_path):
        """Test writing basic INCAR."""
        params = {
            "SYSTEM": "Si test",
            "ENCUT": 300,
            "ISMEAR": 0,
            "SIGMA": 0.05,
        }
        
        incar_path = tmp_path / "INCAR"
        write_incar(params, incar_path)
        
        assert incar_path.exists()
        content = incar_path.read_text()
        assert "SYSTEM = Si test" in content
        assert "ENCUT = 300" in content
        assert "ISMEAR = 0" in content
    
    def test_write_incar_boolean(self, tmp_path):
        """Test writing INCAR with boolean values."""
        params = {
            "LWAVE": True,
            "LCHARG": False,
        }
        
        incar_path = tmp_path / "INCAR"
        write_incar(params, incar_path)
        
        content = incar_path.read_text()
        assert "LWAVE = .TRUE." in content
        assert "LCHARG = .FALSE." in content


class TestVASPKPOINTSWriter:
    """Test KPOINTS writer."""
    
    def test_write_kpoints_automatic(self, tmp_path):
        """Test writing automatic mesh KPOINTS."""
        params = {
            "mode": "automatic",
            "mesh": [6, 6, 6],
            "shift": [0, 0, 0],
        }
        
        kpoints_path = tmp_path / "KPOINTS"
        write_kpoints(params, kpoints_path)
        
        assert kpoints_path.exists()
        content = kpoints_path.read_text()
        assert "Automatic" in content
        assert "6 6 6" in content
    
    def test_write_kpoints_line_mode(self, tmp_path):
        """Test writing line-mode KPOINTS."""
        params = {
            "mode": "line",
            "path": [
                ([0.0, 0.0, 0.0], [0.5, 0.0, 0.5]),
                ([0.5, 0.0, 0.5], [0.5, 0.5, 0.5]),
            ],
            "npoints": 40,
        }
        
        kpoints_path = tmp_path / "KPOINTS"
        write_kpoints(params, kpoints_path)
        
        assert kpoints_path.exists()
        content = kpoints_path.read_text()
        assert "Line-mode" in content
        assert "40" in content
        assert "0.000000 0.000000 0.000000" in content


class TestVASPPOTCARWriter:
    """Test POTCAR writer."""
    
    def test_write_potcar_assembles_correctly(self, tmp_path, monkeypatch):
        """Test that POTCAR is assembled from fragments."""
        structure = Structure(
            Lattice.cubic(5.43),
            ["Si", "Si"],
            [[0, 0, 0], [0.25, 0.25, 0.25]],
        )
        
        species_map = {"Si": {"pseudo": "Si"}}
        
        # Mock get_potcar_dir to return a test directory
        test_potcar_dir = tmp_path / "potpaw_PBE.64"
        test_potcar_dir.mkdir(parents=True)
        (test_potcar_dir / "Si").mkdir()
        (test_potcar_dir / "Si" / "POTCAR").write_text("fake POTCAR content for Si")
        
        def mock_get_potcar_dir(potcar_type: str = "PBE") -> Path:
            return test_potcar_dir
        
        monkeypatch.setattr(
            "quantumvitas.engine.vasp_writer.get_potcar_dir",
            mock_get_potcar_dir
        )
        
        potcar_path = tmp_path / "POTCAR"
        write_potcar(structure, species_map, potcar_path, "PBE")
        
        assert potcar_path.exists()
        content = potcar_path.read_text()
        assert "fake POTCAR content for Si" in content
    
    def test_write_potcar_raises_on_missing(self, tmp_path, monkeypatch):
        """Test that POTCAR writer raises on missing fragment."""
        structure = Structure(
            Lattice.cubic(5.43),
            ["Si", "Si"],
            [[0, 0, 0], [0.25, 0.25, 0.25]],
        )
        
        species_map = {"Si": {"pseudo": "Si"}}
        
        # Mock get_potcar_dir to return a test directory without Si POTCAR
        test_potcar_dir = tmp_path / "potpaw_PBE.64"
        test_potcar_dir.mkdir(parents=True)
        # Don't create Si/POTCAR
        
        def mock_get_potcar_dir(potcar_type: str = "PBE") -> Path:
            return test_potcar_dir
        
        monkeypatch.setattr(
            "quantumvitas.engine.vasp_writer.get_potcar_dir",
            mock_get_potcar_dir
        )
        
        potcar_path = tmp_path / "POTCAR"
        with pytest.raises(FileNotFoundError, match="POTCAR not found"):
            write_potcar(structure, species_map, potcar_path, "PBE")

