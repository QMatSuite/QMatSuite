"""
Unit tests for canonical pseudo_set_sha computation.

This test ensures:
1. There is exactly ONE canonical function for computing pseudo_set_sha
2. The function uses pseudo_sha256 from species_map (atomic records), not file reads
3. The function ignores filename and sha_family
4. The function has stable ordering by element
"""

import hashlib
import inspect
from pathlib import Path

import pytest

from quantumvitas.calculation.hash_utils import compute_pseudo_set_sha


def test_canonical_function_exists():
    """Ensure compute_pseudo_set_sha is the canonical function."""
    # Import the function
    from quantumvitas.calculation.hash_utils import compute_pseudo_set_sha
    
    # Verify it's a function
    assert callable(compute_pseudo_set_sha)
    
    # Verify signature: should accept project_pseudo_dir and species_map
    sig = inspect.signature(compute_pseudo_set_sha)
    params = list(sig.parameters.keys())
    assert "project_pseudo_dir" in params
    assert "species_map" in params


def test_no_duplicate_functions():
    """Ensure there is only one function definition for compute_pseudo_set_sha."""
    import ast
    import os
    
    # Find all Python files in src/quantumvitas
    src_dir = Path(__file__).parent.parent.parent / "src" / "quantumvitas"
    
    function_defs = []
    for py_file in src_dir.rglob("*.py"):
        try:
            with open(py_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=str(py_file))
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "compute_pseudo_set_sha":
                    function_defs.append((py_file, node.lineno))
        except Exception:
            # Skip files that can't be parsed
            continue
    
    # Should have exactly one definition
    assert len(function_defs) == 1, f"Found {len(function_defs)} definitions of compute_pseudo_set_sha: {function_defs}"


def test_uses_pseudo_sha256_from_species_map():
    """Test that function uses pseudo_sha256 from species_map, not file reads."""
    # Create a species_map with pseudo_sha256 (atomic record)
    species_map = {
        "Si": {
            "pseudopot": "Si.UPF",  # filename (should be ignored)
            "pseudo_basename": "Si.UPF",  # basename (should be ignored)
            "pseudo_sha256": "abc123def456",  # This is what should be used
            "pseudo_sha_family": "xyz789",  # sha_family (should be ignored)
            "mass": 28.0855,
        },
        "O": {
            "pseudopot": "O.UPF",
            "pseudo_sha256": "def456ghi789",
            "mass": 15.999,
        },
    }
    
    # Create a fake pseudo_dir (should not be used)
    fake_pseudo_dir = Path("/nonexistent/path")
    
    # Compute SHA - should work even though fake_pseudo_dir doesn't exist
    sha = compute_pseudo_set_sha(fake_pseudo_dir, species_map)
    
    # Verify it's a valid SHA256 hex string (64 chars)
    assert len(sha) == 64
    assert all(c in "0123456789abcdef" for c in sha)
    
    # Verify it's deterministic
    sha2 = compute_pseudo_set_sha(fake_pseudo_dir, species_map)
    assert sha == sha2


def test_ignores_filename_and_sha_family():
    """Test that filename and sha_family are ignored in computation."""
    # Same pseudo_sha256, different filenames
    species_map1 = {
        "Si": {
            "pseudopot": "Si.UPF",
            "pseudo_basename": "Si.UPF",
            "pseudo_sha256": "abc123def456",
            "pseudo_sha_family": "xyz789",
        },
    }
    
    species_map2 = {
        "Si": {
            "pseudopot": "Si_new.UPF",  # Different filename
            "pseudo_basename": "Si_new.UPF",
            "pseudo_sha256": "abc123def456",  # Same SHA
            "pseudo_sha_family": "different_family",  # Different sha_family
        },
    }
    
    fake_pseudo_dir = Path("/nonexistent")
    
    sha1 = compute_pseudo_set_sha(fake_pseudo_dir, species_map1)
    sha2 = compute_pseudo_set_sha(fake_pseudo_dir, species_map2)
    
    # Should be identical (filename and sha_family ignored)
    assert sha1 == sha2


def test_stable_ordering_by_element():
    """Test that ordering is stable by element symbol."""
    # Create species_map with elements in different order
    species_map1 = {
        "Si": {"pseudo_sha256": "abc123"},
        "O": {"pseudo_sha256": "def456"},
    }
    
    species_map2 = {
        "O": {"pseudo_sha256": "def456"},
        "Si": {"pseudo_sha256": "abc123"},
    }
    
    fake_pseudo_dir = Path("/nonexistent")
    
    sha1 = compute_pseudo_set_sha(fake_pseudo_dir, species_map1)
    sha2 = compute_pseudo_set_sha(fake_pseudo_dir, species_map2)
    
    # Should be identical (sorted by element)
    assert sha1 == sha2


def test_includes_only_element_and_sha():
    """Test that only (element, pseudo_sha256) pairs are included."""
    # Create species_map with various fields
    species_map = {
        "Si": {
            "pseudopot": "Si.UPF",
            "pseudo_basename": "Si.UPF",
            "pseudo_sha256": "abc123def456",
            "pseudo_sha_family": "xyz789",
            "mass": 28.0855,
            "other_field": "ignored",
        },
    }
    
    fake_pseudo_dir = Path("/nonexistent")
    sha = compute_pseudo_set_sha(fake_pseudo_dir, species_map)
    
    # Manually compute expected SHA to verify algorithm
    # Token should be "Si:abc123def456" (element:sha256 only)
    expected_token = "Si:abc123def456"
    expected_sha = hashlib.sha256(expected_token.encode('utf-8')).hexdigest()
    
    assert sha == expected_sha


def test_handles_missing_pseudo_sha256():
    """Test that elements without pseudo_sha256 are skipped."""
    species_map = {
        "Si": {
            "pseudopot": "Si.UPF",
            # Missing pseudo_sha256
        },
        "O": {
            "pseudo_sha256": "def456ghi789",
        },
    }
    
    fake_pseudo_dir = Path("/nonexistent")
    sha = compute_pseudo_set_sha(fake_pseudo_dir, species_map)
    
    # Should only include O (Si is skipped)
    expected_token = "O:def456ghi789"
    expected_sha = hashlib.sha256(expected_token.encode('utf-8')).hexdigest()
    
    assert sha == expected_sha


def test_handles_empty_species_map():
    """Test that empty species_map returns hash of empty string."""
    fake_pseudo_dir = Path("/nonexistent")
    sha = compute_pseudo_set_sha(fake_pseudo_dir, {})
    
    expected_sha = hashlib.sha256(b"").hexdigest()
    assert sha == expected_sha


def test_multiple_elements_canonical_format():
    """Test canonical format for multiple elements."""
    species_map = {
        "O": {"pseudo_sha256": "def456"},
        "Si": {"pseudo_sha256": "abc123"},
    }
    
    fake_pseudo_dir = Path("/nonexistent")
    sha = compute_pseudo_set_sha(fake_pseudo_dir, species_map)
    
    # Should be sorted by element: O first, then Si
    # Token: "O:def456|Si:abc123"
    expected_token = "O:def456|Si:abc123"
    expected_sha = hashlib.sha256(expected_token.encode('utf-8')).hexdigest()
    
    assert sha == expected_sha






