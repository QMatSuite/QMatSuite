"""
Unit tests for atomic radii module.
"""

import pytest
from quantumvitas.analysis.atomic_radii import (
    get_radii_map,
    get_element_radius,
    DEFAULT_COVALENT_RADII,
)


def test_get_radii_map_returns_dict():
    """Test that get_radii_map returns a dictionary."""
    radii_map = get_radii_map()
    assert isinstance(radii_map, dict)
    assert len(radii_map) > 0


def test_radii_map_contains_common_elements():
    """Test that radii map contains common elements."""
    radii_map = get_radii_map()
    
    # Check for required elements
    required_elements = ["H", "C", "N", "O", "Si", "Mo", "S"]
    for elem in required_elements:
        assert elem in radii_map, f"Element {elem} not found in radii map"
        assert isinstance(radii_map[elem], (int, float))
        assert radii_map[elem] > 0


def test_get_element_radius_returns_float():
    """Test that get_element_radius returns a float."""
    radius = get_element_radius("Si")
    assert isinstance(radius, (int, float))
    assert radius > 0


def test_get_element_radius_fallback():
    """Test that get_element_radius uses fallback for unknown elements."""
    radius = get_element_radius("Xx", fallback_radius=1.5)
    assert radius == 1.5


def test_radii_map_values_are_positive():
    """Test that all radii values are positive."""
    radii_map = get_radii_map()
    for elem, radius in radii_map.items():
        assert radius > 0, f"Radius for {elem} is not positive: {radius}"
