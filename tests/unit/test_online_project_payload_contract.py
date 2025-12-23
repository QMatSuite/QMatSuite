"""
Test online vs project payload contract consistency.

This test verifies that:
1. Online and project paths produce identical payload schemas
2. Payload contract is enforced (atoms contains ALL display atoms, bonds reference atoms only)
3. Same structure produces identical atoms_len, bonds_len, and bond indices
"""

import pytest
import numpy as np
from pymatgen.core import Structure, Lattice

from quantumvitas.api import QVService
from quantumvitas.analysis.structure_viz import DisplayModeParams


def test_online_project_payload_contract_identical():
    """
    Test that online and project payloads have identical contract.
    
    Contract:
    - payload.atoms contains ALL display atoms (canonical + supercell + boundary)
    - payload.boundary_atoms is UI metadata only
    - payload.bonds.idx1/idx2 reference payload.atoms[0..len(atoms)-1]
    - maxBondIndex < len(atoms)
    """
    # Build test structure (simulating OPTIMADE structure)
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
    
    # Test with repeat_boundary=True to include boundary atoms
    params = DisplayModeParams(
        mode="primitive",
        supercell=None,
        repeat_boundary=True,  # This adds boundary atoms
        box_bounds=None,
    )
    
    # ONLINE path payload
    online_payload = QVService._build_structure_vis_payload(
        structure,
        params,
        structure_meta={"structure_id": "online:test_candidate"},
        trace_id="test_trace_online",
    )
    
    # PROJECT path payload
    project_payload = QVService._build_structure_vis_payload(
        structure,
        params,
        structure_meta={"structure_id": "project:test_structure"},
        trace_id="test_trace_project",
    )
    
    # Extract payload metrics
    online_atoms_len = len(online_payload["atoms"])
    online_boundary_atoms_len = len(online_payload["boundary_atoms"])
    online_bonds_len = len(online_payload["bonds"])
    
    project_atoms_len = len(project_payload["atoms"])
    project_boundary_atoms_len = len(project_payload["boundary_atoms"])
    project_bonds_len = len(project_payload["bonds"])
    
    # Extract bond schema
    online_first_bond_keys = list(online_payload["bonds"][0].keys()) if online_bonds_len > 0 else []
    project_first_bond_keys = list(project_payload["bonds"][0].keys()) if project_bonds_len > 0 else []
    
    # Compute max bond indices
    online_max_bond_idx = -1
    if online_bonds_len > 0:
        for bond in online_payload["bonds"]:
            online_max_bond_idx = max(online_max_bond_idx, bond["idx1"], bond["idx2"])
    
    project_max_bond_idx = -1
    if project_bonds_len > 0:
        for bond in project_payload["bonds"]:
            project_max_bond_idx = max(project_max_bond_idx, bond["idx1"], bond["idx2"])
    
    # ASSERT: Payloads must have identical structure
    assert online_atoms_len == project_atoms_len, \
        f"atoms_len mismatch: online={online_atoms_len} project={project_atoms_len}"
    assert online_boundary_atoms_len == project_boundary_atoms_len, \
        f"boundary_atoms_len mismatch: online={online_boundary_atoms_len} project={project_boundary_atoms_len}"
    assert online_bonds_len == project_bonds_len, \
        f"bonds_len mismatch: online={online_bonds_len} project={project_bonds_len}"
    assert online_first_bond_keys == project_first_bond_keys, \
        f"bond schema mismatch: online keys={online_first_bond_keys} project keys={project_first_bond_keys}"
    assert online_max_bond_idx == project_max_bond_idx, \
        f"maxBondIndex mismatch: online={online_max_bond_idx} project={project_max_bond_idx}"
    
    # ASSERT: Contract enforcement - bonds must reference atoms array
    assert online_max_bond_idx < online_atoms_len, \
        f"INVALID CONTRACT: online maxBondIndex={online_max_bond_idx} >= atoms_len={online_atoms_len}"
    assert project_max_bond_idx < project_atoms_len, \
        f"INVALID CONTRACT: project maxBondIndex={project_max_bond_idx} >= atoms_len={project_atoms_len}"
    
    # ASSERT: Bond schema uses idx1/idx2 (not atom1/atom2)
    if online_bonds_len > 0:
        assert "idx1" in online_first_bond_keys, \
            f"online bonds must use idx1/idx2, found keys: {online_first_bond_keys}"
        assert "idx2" in online_first_bond_keys, \
            f"online bonds must use idx1/idx2, found keys: {online_first_bond_keys}"
        assert "atom1" not in online_first_bond_keys, \
            f"online bonds must NOT use atom1/atom2, found keys: {online_first_bond_keys}"
    
    # ASSERT: Sample bonds are identical
    if online_bonds_len > 0 and project_bonds_len > 0:
        # Compare first two bonds
        online_bond0 = online_payload["bonds"][0]
        project_bond0 = project_payload["bonds"][0]
        assert online_bond0["idx1"] == project_bond0["idx1"], \
            f"bond[0].idx1 mismatch: online={online_bond0['idx1']} project={project_bond0['idx1']}"
        assert online_bond0["idx2"] == project_bond0["idx2"], \
            f"bond[0].idx2 mismatch: online={online_bond0['idx2']} project={project_bond0['idx2']}"
        assert abs(online_bond0["distance"] - project_bond0["distance"]) < 1e-6, \
            f"bond[0].distance mismatch: online={online_bond0['distance']} project={project_bond0['distance']}"
        
        if online_bonds_len > 1 and project_bonds_len > 1:
            online_bond1 = online_payload["bonds"][1]
            project_bond1 = project_payload["bonds"][1]
            assert online_bond1["idx1"] == project_bond1["idx1"], \
                f"bond[1].idx1 mismatch: online={online_bond1['idx1']} project={project_bond1['idx1']}"
            assert online_bond1["idx2"] == project_bond1["idx2"], \
                f"bond[1].idx2 mismatch: online={online_bond1['idx2']} project={project_bond1['idx2']}"


def test_payload_contract_atoms_contains_all_display_atoms():
    """
    Test that payload.atoms contains ALL display atoms (including boundary).
    
    This is the critical contract: atoms must equal display_atoms_total,
    not just canonical atoms.
    """
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
    
    # Test with repeat_boundary=True
    params = DisplayModeParams(
        mode="primitive",
        supercell=None,
        repeat_boundary=True,
        box_bounds=None,
    )
    
    payload = QVService._build_structure_vis_payload(
        structure,
        params,
        structure_meta={"structure_id": "test"},
        trace_id="test",
    )
    
    atoms_len = len(payload["atoms"])
    bonds_len = len(payload["bonds"])
    
    # ASSERT: atoms contains ALL display atoms (canonical + boundary)
    # In this case with repeat_boundary=True, we should have more atoms than canonical
    canonical_nsites = len(structure)
    assert atoms_len >= canonical_nsites, \
        f"atoms_len={atoms_len} must be >= canonical_nsites={canonical_nsites}"
    
    # NEW CONTRACT (2024): boundary atoms are indicated by is_boundary flag in atoms array
    # The separate boundary_atoms array is DEPRECATED (always empty)
    boundary_in_atoms = sum(1 for atom in payload["atoms"] if atom.get("is_boundary", False))
    # With repeat_boundary=True, there should be boundary atoms marked in the atoms array
    assert boundary_in_atoms > 0, \
        f"With repeat_boundary=True, atoms should contain boundary atoms (is_boundary=True). Got {boundary_in_atoms}"
    
    # ASSERT: Bonds reference atoms array correctly
    if bonds_len > 0:
        max_bond_idx = max(max(b["idx1"], b["idx2"]) for b in payload["bonds"])
        assert max_bond_idx < atoms_len, \
            f"INVALID CONTRACT: maxBondIndex={max_bond_idx} >= atoms_len={atoms_len}"

