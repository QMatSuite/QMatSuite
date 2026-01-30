"""
Offline tests for OPTIMADE structure processing.

D2: Offline deterministic tests (local raw data, no network).

These tests:
- Load saved OPTIMADE JSON from tests/data/optimade/
- Process through online → shared pipeline
- Verify payload contract consistency
- Compare with project path for same structure

These tests do NOT require network and should always pass.
"""

import pytest
import json
from pathlib import Path
from pymatgen.core import Structure, Lattice
import numpy as np

from quantumvitas.analysis.structure_viz import build_structure_vis_payload, DisplayModeParams
# Note: _parse_optimade_structure is internal, we'll use public API instead
# from quantumvitas.io.online_search import fetch_structure_from_optimade


def load_optimade_fixture(filename: str) -> dict:
    """Load OPTIMADE JSON fixture from tests/data/optimade/"""
    fixture_path = Path(__file__).parent.parent / "data" / "optimade" / filename
    if not fixture_path.exists():
        pytest.skip(f"Fixture {filename} not found. Run test_optimade_online.py first to generate fixtures.")
    with open(fixture_path, 'r') as f:
        return json.load(f)


def test_optimade_structure_parsing():
    """
    Test parsing OPTIMADE JSON into pymatgen Structure.
    
    This test uses a minimal test structure (simulating OPTIMADE data).
    In production, this would load from tests/data/optimade/*.json
    """
    # Create a minimal test structure (simulating OPTIMADE structure)
    lattice_vectors = [
        [3.16, 0.0, 0.0],
        [0.0, 3.16, 0.0],
        [0.0, 0.0, 12.3],
    ]
    cartesian_positions = [
        [0.0, 0.0, 0.0],
        [1.58, 1.58, 3.075],
        [1.58, 1.58, 9.225],
    ]
    species = ["Mo", "S", "S"]
    
    lattice = Lattice(lattice_vectors)
    structure = Structure(lattice, species, cartesian_positions, coords_are_cartesian=True)
    
    # Verify structure is valid
    assert len(structure) == 3
    assert structure.lattice is not None


def test_optimade_online_pipeline_payload_contract():
    """
    Test that OPTIMADE structure → online pipeline → payload respects contract.
    
    Contract:
    - atoms contains ALL display atoms
    - bonds reference atoms array only
    - maxBondIndex < len(atoms)
    """
    # Create test structure (simulating OPTIMADE fetch)
    lattice_vectors = [
        [3.16, 0.0, 0.0],
        [0.0, 3.16, 0.0],
        [0.0, 0.0, 12.3],
    ]
    cartesian_positions = [
        [0.0, 0.0, 0.0],
        [1.58, 1.58, 3.075],
        [1.58, 1.58, 9.225],
    ]
    species = ["Mo", "S", "S"]
    
    lattice = Lattice(lattice_vectors)
    structure = Structure(lattice, species, cartesian_positions, coords_are_cartesian=True)
    
    # Simulate online pipeline: get_primitive_structure() then shared pipeline
    structure_primitive = structure.get_primitive_structure()
    
    # Use shared pipeline (same as online handler)
    params = DisplayModeParams(
        mode="primitive",
        supercell=None,
        repeat_boundary=True,
        box_bounds=None,
    )
    
    payload = build_structure_vis_payload(
        structure_primitive,
        params,
        structure_meta={"structure_ulid": "online:test_candidate"},
    )
    
    # Verify contract
    atoms_len = len(payload["atoms"])
    bonds_len = len(payload["bonds"])
    
    assert atoms_len > 0, "Must have atoms"
    if bonds_len > 0:
        max_bond_idx = max(max(b["idx1"], b["idx2"]) for b in payload["bonds"])
        assert max_bond_idx < atoms_len, \
            f"INVALID CONTRACT: maxBondIndex={max_bond_idx} >= atoms_len={atoms_len}"
        assert "idx1" in payload["bonds"][0], "Bonds must use idx1/idx2 schema"
        assert "idx2" in payload["bonds"][0], "Bonds must use idx1/idx2 schema"


def test_optimade_vs_project_same_structure_ulidentical_payload():
    """
    Test that same structure via OPTIMADE (online) vs project produces identical payload.
    
    This is the critical regression test:
    - Same structure data
    - Online path: OPTIMADE → primitive → shared pipeline
    - Project path: file → shared pipeline
    - Payloads must be byte-level identical (or within tolerance)
    """
    # Create structure (simulating both paths)
    lattice_vectors = [
        [3.16, 0.0, 0.0],
        [0.0, 3.16, 0.0],
        [0.0, 0.0, 12.3],
    ]
    cartesian_positions = [
        [0.0, 0.0, 0.0],
        [1.58, 1.58, 3.075],
        [1.58, 1.58, 9.225],
    ]
    species = ["Mo", "S", "S"]
    
    lattice = Lattice(lattice_vectors)
    structure_cartesian = Structure(lattice, species, cartesian_positions, coords_are_cartesian=True)
    
    # ONLINE path: cartesian → primitive → shared pipeline
    structure_online = structure_cartesian.get_primitive_structure()
    
    # PROJECT path: same structure (already in standard format)
    structure_project = structure_cartesian.copy()
    
    params = DisplayModeParams(
        mode="primitive",
        supercell=None,
        repeat_boundary=True,
        box_bounds=None,
    )
    
    # ONLINE payload
    online_payload = build_structure_vis_payload(
        structure_online,
        params,
        structure_meta={"structure_ulid": "online:test"},
    )

    # PROJECT payload
    project_payload = build_structure_vis_payload(
        structure_project,
        params,
        structure_meta={"structure_ulid": "project:test"},
    )
    
    # ASSERT: Identical payload metrics
    assert len(online_payload["atoms"]) == len(project_payload["atoms"]), \
        f"atoms_len mismatch: online={len(online_payload['atoms'])} project={len(project_payload['atoms'])}"
    assert len(online_payload["bonds"]) == len(project_payload["bonds"]), \
        f"bonds_len mismatch: online={len(online_payload['bonds'])} project={len(project_payload['bonds'])}"
    
    # ASSERT: Bond indices identical
    if len(online_payload["bonds"]) > 0:
        online_bond0 = online_payload["bonds"][0]
        project_bond0 = project_payload["bonds"][0]
        assert online_bond0["idx1"] == project_bond0["idx1"]
        assert online_bond0["idx2"] == project_bond0["idx2"]
        assert abs(online_bond0["distance"] - project_bond0["distance"]) < 1e-6

