"""
Tests for preset inference robustness with ScanRefs.

This test verifies that preset inference naturally mismatches (returns None -> custom)
when encountering ScanRef dicts, without crashing.
"""

import pytest

from qmatsuite.presets.paramspace import (
    ParamSpace,
    ParamKey,
    Cell,
    match_profile,
    ParamSpaceContext,
)


def test_match_profile_with_scan_ref_naturally_mismatches():
    """Preset inference naturally mismatches when encountering ScanRef dicts."""
    # Create a simple ParamSpace
    key = ParamKey(
        section="SYSTEM",
        key="ecutwfc",
        parser=lambda x: float(x),
        canonicalizer=lambda x: float(x),
        default=50.0,
    )
    
    space = ParamSpace(
        name="test_space",
        keys=[key],
        profiles={
            "profile1": {
                key: Cell.VALUE(50.0),
            }
        },
    )
    
    # YAML with ScanRef (should naturally mismatch)
    yaml_tree = {
        "SYSTEM": {
            "ecutwfc": "@scan:scan001",  # ScanRef dict
        }
    }
    
    # Match should return None (naturally mismatch -> custom)
    with ParamSpaceContext(space):
        result = match_profile(space, yaml_tree)
    
    assert result is None  # No match (naturally custom)
    
    # YAML with concrete value (should match)
    yaml_tree_concrete = {
        "SYSTEM": {
            "ecutwfc": 50.0,
        }
    }
    
    with ParamSpaceContext(space):
        result_concrete = match_profile(space, yaml_tree_concrete)
    
    assert result_concrete == "profile1"  # Matches


def test_match_profile_with_scan_ref_does_not_crash():
    """Preset inference does not crash when encountering ScanRef dicts."""
    # Create a ParamSpace with multiple keys
    key1 = ParamKey(
        section="SYSTEM",
        key="ecutwfc",
        parser=lambda x: float(x),
        canonicalizer=lambda x: float(x),
        default=50.0,
    )
    key2 = ParamKey(
        section="SYSTEM",
        key="ecutrho",
        parser=lambda x: float(x),
        canonicalizer=lambda x: float(x),
        default=400.0,
    )
    
    space = ParamSpace(
        name="test_space",
        keys=[key1, key2],
        profiles={
            "profile1": {
                key1: Cell.VALUE(50.0),
                key2: Cell.VALUE(400.0),
            }
        },
    )
    
    # YAML with ScanRef in one key (should naturally mismatch, not crash)
    yaml_tree = {
        "SYSTEM": {
            "ecutwfc": "@scan:scan001",  # ScanRef
            "ecutrho": 400.0,  # Concrete value
        }
    }
    
    # Should not crash, should return None
    with ParamSpaceContext(space):
        result = match_profile(space, yaml_tree)
    
    assert result is None  # No match (naturally custom)

