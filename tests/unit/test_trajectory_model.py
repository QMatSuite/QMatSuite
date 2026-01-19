"""Tests for trajectory model."""
import pytest
import numpy as np

from quantumvitas.core.analysis.trajectory.model import Frame, Trajectory
from quantumvitas.core.analysis.base import AnalysisObjectMeta, SourceFileStat


class TestFrame:
    def test_valid_frame(self):
        """Test creating a valid frame."""
        frame = Frame(
            frame_index=0,
            positions=np.array([[0, 0, 0], [1, 1, 1]]),
            species=["Si", "Si"],
            cell=np.eye(3) * 5.43,
            pbc=(True, True, True),
        )
        
        assert frame.n_atoms == 2
        assert frame.frame_index == 0
    
    def test_molecular_no_box(self):
        """Molecule without box (cell=None)."""
        frame = Frame(
            frame_index=0,
            positions=np.array([[0, 0, 0], [1.5, 0, 0]]),
            species=["H", "H"],
            cell=None,
            pbc=(False, False, False),
        )
        
        assert frame.cell is None
        assert frame.pbc == (False, False, False)
    
    def test_molecular_with_box(self):
        """Molecule with box but no PBC."""
        frame = Frame(
            frame_index=0,
            positions=np.array([[0, 0, 0], [1.5, 0, 0]]),
            species=["H", "H"],
            cell=np.eye(3) * 20.0,  # Large box for viz
            pbc=(False, False, False),
        )
        
        assert frame.cell is not None
        assert not any(frame.pbc)
    
    def test_pbc_requires_cell(self):
        """PBC requires cell."""
        with pytest.raises(ValueError, match="PBC requires cell"):
            Frame(
                frame_index=0,
                positions=np.array([[0, 0, 0]]),
                species=["H"],
                cell=None,
                pbc=(True, False, False),  # PBC without cell
            )
    
    def test_species_count_match(self):
        """Species count must match positions."""
        with pytest.raises(ValueError, match="Species count"):
            Frame(
                frame_index=0,
                positions=np.array([[0, 0, 0], [1, 1, 1]]),
                species=["Si"],  # Only 1 species for 2 atoms
                cell=None,
                pbc=(False, False, False),
            )


class TestTrajectory:
    def test_observable_series(self):
        """Test extracting observable series."""
        frames = [
            Frame(
                frame_index=i,
                positions=np.array([[0, 0, 0]]),
                species=["H"],
                cell=None,
                pbc=(False, False, False),
                iteration=i,
                energy=-10.0 + i * 0.1,
            )
            for i in range(5)
        ]
        
        meta = AnalysisObjectMeta.create("trajectory", [])
        traj = Trajectory(meta=meta, frames=frames, trajectory_type="relax")
        
        series = traj.get_observable_series("energy")
        
        assert series is not None
        assert len(series.y) == 5
        assert series.y_unit == "eV"
    
    def test_to_visual_primitives(self):
        """Test visual primitives extraction."""
        frames = [
            Frame(
                frame_index=0,
                positions=np.array([[0, 0, 0]]),
                species=["H"],
                cell=np.eye(3) * 5.0,
                pbc=(True, True, True),
                energy=-10.0,
            )
        ]
        
        meta = AnalysisObjectMeta.create("trajectory", [])
        traj = Trajectory(meta=meta, frames=frames, trajectory_type="md")
        
        primitives = traj.to_visual_primitives()
        
        assert "geometry" in primitives
        assert primitives["geometry"].frames[0].n_atoms == 1

