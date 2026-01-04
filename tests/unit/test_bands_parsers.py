"""
Unit tests for bands.x stdout parser (high-symmetry k-point labels).
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from quantumvitas.analysis.parsers import _parse_bands_symmetry_output


def test_parse_bands_symmetry_output_basic():
    """Test parsing high-symmetry points from bands.x output."""
    # Sample data matching real QE bands.x output format
    sample_output = """
  high-symmetry point:  0.3536 0.3536 0.3536   x coordinate   0.0000
  high-symmetry point:  0.0000 0.0000 0.0000   x coordinate   0.6124
  high-symmetry point:  0.7071 0.0000 0.0000   x coordinate   1.3195
  high-symmetry point:  0.7071 0.1768 0.1768   x coordinate   1.5695
  high-symmetry point:  0.0000 0.0000 0.0000   x coordinate   2.3195
"""
    
    with TemporaryDirectory() as tmpdir:
        bands_out = Path(tmpdir) / "bands.out"
        bands_out.write_text(sample_output)
        
        points = _parse_bands_symmetry_output(bands_out)
        
        # Should parse 5 points (with deduplication, might be 4 if x coordinates match)
        assert len(points) >= 4  # At least 4 unique x coordinates
        assert len(points) <= 5  # At most 5 if all unique
        
        # Verify specific points
        x_coords = [pt.k_distance for pt in points]
        assert 0.0000 in x_coords
        assert 0.6124 in x_coords
        assert 1.3195 in x_coords
        assert 1.5695 in x_coords
        assert 2.3195 in x_coords
        
        # Check that k-coordinates are parsed correctly
        points_by_x = {pt.k_distance: pt for pt in points}
        pt_0 = points_by_x[0.0000]
        assert pt_0.k_coords == (0.3536, 0.3536, 0.3536)
        
        pt_6124 = points_by_x[0.6124]
        assert pt_6124.k_coords == (0.0000, 0.0000, 0.0000)
        
        pt_13195 = points_by_x[1.3195]
        assert pt_13195.k_coords == (0.7071, 0.0000, 0.0000)
        
        # Points should be sorted by x coordinate
        assert x_coords == sorted(x_coords)


def test_parse_bands_symmetry_output_deduplication():
    """Test that duplicate x coordinates are deduplicated."""
    sample_output = """
  high-symmetry point:  0.5000 0.5000 0.5000   x coordinate   1.0000
  high-symmetry point:  0.2500 0.2500 0.2500   x coordinate   1.0000
"""
    
    with TemporaryDirectory() as tmpdir:
        bands_out = Path(tmpdir) / "bands.out"
        bands_out.write_text(sample_output)
        
        points = _parse_bands_symmetry_output(bands_out)
        
        # Should deduplicate to 1 point (same x coordinate within epsilon)
        assert len(points) == 1
        assert points[0].k_distance == pytest.approx(1.0000, abs=1e-6)
        # Should keep the first one (by file order)
        assert points[0].k_coords == (0.5000, 0.5000, 0.5000)


def test_parse_bands_symmetry_output_flexible_spacing():
    """Test that parser handles variations in spacing."""
    # Test with minimal spacing
    sample_output1 = """
high-symmetry point:0.5 0.5 0.5 x coordinate 1.0
"""
    
    # Test with extra spacing
    sample_output2 = """
  high-symmetry point:    0.5    0.5    0.5     x coordinate    1.0
"""
    
    with TemporaryDirectory() as tmpdir:
        for i, sample in enumerate([sample_output1, sample_output2]):
            bands_out = Path(tmpdir) / f"bands{i}.out"
            bands_out.write_text(sample)
            
            points = _parse_bands_symmetry_output(bands_out)
            
            assert len(points) == 1
            assert points[0].k_distance == pytest.approx(1.0)
            assert points[0].k_coords == (0.5, 0.5, 0.5)


def test_parse_bands_symmetry_output_empty_file():
    """Test parsing empty file returns empty list."""
    with TemporaryDirectory() as tmpdir:
        bands_out = Path(tmpdir) / "bands.out"
        bands_out.write_text("")
        
        points = _parse_bands_symmetry_output(bands_out)
        assert len(points) == 0


def test_parse_bands_symmetry_output_no_matches():
    """Test parsing file with no matching lines returns empty list."""
    sample_output = """
Some other text
Not a high-symmetry point line
Random data here
"""
    
    with TemporaryDirectory() as tmpdir:
        bands_out = Path(tmpdir) / "bands.out"
        bands_out.write_text(sample_output)
        
        points = _parse_bands_symmetry_output(bands_out)
        assert len(points) == 0


def test_parse_bands_symmetry_output_negative_coords():
    """Test parser handles negative coordinates."""
    sample_output = """
  high-symmetry point:  -0.5  0.5  -0.5   x coordinate   -1.0
  high-symmetry point:   0.5 -0.5   0.5   x coordinate    2.0
"""
    
    with TemporaryDirectory() as tmpdir:
        bands_out = Path(tmpdir) / "bands.out"
        bands_out.write_text(sample_output)
        
        points = _parse_bands_symmetry_output(bands_out)
        
        assert len(points) == 2
        x_coords = sorted([pt.k_distance for pt in points])
        assert x_coords == [-1.0, 2.0]
        
        points_by_x = {pt.k_distance: pt for pt in points}
        assert points_by_x[-1.0].k_coords == (-0.5, 0.5, -0.5)
        assert points_by_x[2.0].k_coords == (0.5, -0.5, 0.5)

