"""
Integration tests for OPTIMADE online structure fetching.

D1: Online integration tests (real OPTIMADE, network required).

These tests verify:
- OPTIMADE provider is accessible
- Structure fetching works
- Basic structure fields are present

These tests WILL FAIL if:
- Network is unavailable
- OPTIMADE provider is down
- OPTIMADE schema changes

This is intentional - these are "external dependency health checks".
"""

import pytest
from quantumvitas.io.online_search import (
    search_optimade,
    fetch_structure_from_optimade,
    OPTIMADE_BASES,
    OPTIMADE_DEFAULT_BASE,
)


@pytest.mark.integration
@pytest.mark.network
def test_optimade_search_basic():
    """
    Test basic OPTIMADE search functionality.
    
    This test requires network access and will fail if OPTIMADE is down.
    """
    # Use Materials Cloud OPTIMADE endpoint
    base_url = OPTIMADE_DEFAULT_BASE
    
    # Search for a common material (Si)
    # Note: search_optimade returns (base_url, entries) tuple
    base_url, results = search_optimade(
        query="Si",
        max_results=5,
    )
    
    # Verify results structure
    assert base_url is not None, "OPTIMADE search should return a base_url"
    assert results is not None
    assert len(results) > 0
    
    # Verify candidate has required fields
    candidate = results[0]
    assert "id" in candidate
    assert "attributes" in candidate
    attrs = candidate["attributes"]
    assert "chemical_formula_reduced" in attrs or "chemical_formula_descriptive" in attrs
    assert "nsites" in attrs
    assert "lattice_vectors" in attrs or "elements" in attrs


@pytest.mark.integration
@pytest.mark.network
def test_optimade_fetch_structure():
    """
    Test fetching structure from OPTIMADE.
    
    This test requires network access and will fail if OPTIMADE is down.
    """
    # Use Materials Cloud OPTIMADE endpoint
    base_url = OPTIMADE_DEFAULT_BASE
    
    # Search for Si first
    base_url, results = search_optimade(
        query="Si",
        max_results=1,
    )

    assert base_url is not None, "OPTIMADE search failed (network or provider issue)"
    assert results and len(results) > 0, "No search results available"
    
    candidate_id = results[0]["id"]
    
    # Fetch structure
    structure, raw_data = fetch_structure_from_optimade(base_url, candidate_id)
    
    # Verify structure
    assert structure is not None
    assert len(structure) > 0  # Has sites
    assert structure.lattice is not None  # Has lattice
    
    # Verify raw data
    assert raw_data is not None
    assert "data" in raw_data
    assert "attributes" in raw_data["data"]


@pytest.mark.integration
@pytest.mark.network
def test_optimade_structure_has_required_fields():
    """
    Test that fetched OPTIMADE structure has required fields for visualization.
    
    Required fields:
    - nsites
    - lattice_vectors or elements + cartesian_site_positions
    - species information
    """
    # Use Materials Cloud OPTIMADE endpoint
    base_url = OPTIMADE_DEFAULT_BASE
    
    # Search for a simple material
    base_url, results = search_optimade(
        query="Si",
        max_results=1,
    )

    assert base_url is not None, "OPTIMADE search failed (network or provider issue)"
    assert results and len(results) > 0, "No search results available"
    
    candidate_id = results[0]["id"]
    structure, raw_data = fetch_structure_from_optimade(base_url, candidate_id)
    
    # Verify structure has required fields
    assert len(structure) > 0, "Structure must have sites"
    assert structure.lattice is not None, "Structure must have lattice"
    assert len(structure.species) > 0, "Structure must have species"
    
    # Verify raw data has attributes
    attrs = raw_data["data"]["attributes"]
    assert "nsites" in attrs or len(structure) > 0, "Must have nsites or sites"
    assert "lattice_vectors" in attrs or "elements" in attrs, "Must have lattice info"

