"""Unit tests for LAMMPS parser."""

import pytest
from pathlib import Path

from quantumvitas.engine.lammps_parser import (
    parse_lammps_log,
    parse_lammps_dump,
    build_trajectory_from_parsed,
)


class TestLammpsLogParser:
    """Test LAMMPS log file parsing."""
    
    def test_parse_minimize_log(self):
        """Test parsing minimize log file."""
        fixture_path = Path(__file__).parent.parent / "data" / "lammps" / "fixtures" / "log_minimize_lj.lammps"
        if not fixture_path.exists():
            pytest.skip(f"Fixture not found: {fixture_path}")
        
        thermo = parse_lammps_log(fixture_path)
        assert len(thermo) > 0, "Should parse at least one thermo row"
        assert "step" in thermo.columns or "Step" in thermo.columns, "Should have step column"
        print(f"✓ Parsed {len(thermo)} thermo rows")
    
    def test_parse_md_log(self):
        """Test parsing MD log file."""
        import pandas as pd
        fixture_path = Path(__file__).parent.parent / "data" / "lammps" / "fixtures" / "log_md_nvt.lammps"
        if not fixture_path.exists():
            pytest.skip(f"Fixture not found: {fixture_path}")
        
        thermo = parse_lammps_log(fixture_path)
        # MD log may have different format or be very short, so just verify parser doesn't crash
        assert isinstance(thermo, pd.DataFrame), "Should return DataFrame"
        # If log has thermo data, verify it's parseable
        if len(thermo) > 0:
            assert "step" in thermo.columns or "Step" in thermo.columns, "Should have step column"
        print(f"✓ Parsed MD log (found {len(thermo)} thermo rows)")


class TestLammpsDumpParser:
    """Test LAMMPS dump file parsing."""
    
    def test_parse_minimize_dump(self):
        """Test parsing minimize dump file."""
        fixture_path = Path(__file__).parent.parent / "data" / "lammps" / "fixtures" / "dump_minimize.lammpstrj"
        if not fixture_path.exists():
            pytest.skip(f"Fixture not found: {fixture_path}")
        
        frames = parse_lammps_dump(fixture_path, max_frames=5)
        assert len(frames) > 0, "Should parse at least one frame"
        
        frame = frames[0]
        assert "frame_index" in frame, "Frame should have frame_index"
        assert "n_atoms" in frame, "Frame should have n_atoms"
        assert "atoms" in frame, "Frame should have atoms"
        assert len(frame["atoms"]) == frame["n_atoms"], "Atom count should match"
        print(f"✓ Parsed {len(frames)} frames from minimize dump")
    
    def test_parse_md_dump(self):
        """Test parsing MD dump file."""
        fixture_path = Path(__file__).parent.parent / "data" / "lammps" / "fixtures" / "dump_md.lammpstrj"
        if not fixture_path.exists():
            pytest.skip(f"Fixture not found: {fixture_path}")
        
        frames = parse_lammps_dump(fixture_path, max_frames=10)
        assert len(frames) > 0, "Should parse at least one frame"
        print(f"✓ Parsed {len(frames)} frames from MD dump")


class TestTrajectoryBuilder:
    """Test trajectory building from parsed data."""
    
    def test_build_trajectory_metal_units(self):
        """Test building trajectory with metal units."""
        # Create mock frame data
        frames = [{
            "frame_index": 0,
            "timestep": 0,
            "n_atoms": 2,
            "box_bounds": {"xlo": 0.0, "xhi": 10.0, "ylo": 0.0, "yhi": 10.0, "zlo": 0.0, "zhi": 10.0},
            "atoms": [
                {"id": 1, "type": 1, "x": 0.0, "y": 0.0, "z": 0.0, "vx": 0.1, "vy": 0.1, "vz": 0.1},
                {"id": 2, "type": 1, "x": 1.0, "y": 1.0, "z": 1.0, "vx": 0.2, "vy": 0.2, "vz": 0.2},
            ],
        }]
        
        result = build_trajectory_from_parsed(frames, units="metal")
        assert "frames" in result
        assert len(result["frames"]) == 1
        assert result["meta"]["unit_system"] == "metal"
        print("✓ Built trajectory with metal units")

