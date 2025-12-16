"""
Integration test: Force alignment between online and project visualization pipelines.

This test ensures that online structures use the EXACT same pipeline as project structures.
It fetches a structure from OPTIMADE, then compares:
- Path A: Online pipeline (direct from OPTIMADE structure)
- Path B: Project pipeline (same structure written to project file)

Both paths must produce identical outputs (within float tolerance).
"""

import pytest
import tempfile
import json
from pathlib import Path
import numpy as np

from quantumvitas.io.online_search import (
    OPTIMADE_BASES,
    fetch_structure_from_optimade,
    search_optimade,
)
from quantumvitas.io.structure_io import write_structure, read_structure
from quantumvitas.api import QVService
from quantumvitas.analysis.structure_viz import DisplayModeParams


@pytest.mark.integration
def test_online_vs_project_pipeline_bit_aligned():
    """
    Force alignment test: online vs project pipeline must produce identical outputs.
    
    Test structure: NbSe2 (12 sites) or MoS2 (3 sites) - stable examples from OPTIMADE.
    
    Test logic:
    1. Fetch structure from OPTIMADE (live HTTP)
    2. Path A: Direct online pipeline (call _build_structure_vis_payload with online structure)
    3. Path B: Write structure to project file, then call project pipeline
    4. Compare outputs: lattice, atoms, bonds must be identical (within tolerance)
    
    This test MUST NOT skip. If OPTIMADE is down, CI should fail.
    """
    # Step 1: Fetch structure from OPTIMADE
    # Try NbSe2 first (12 sites, stable), fallback to MoS2 (3 sites)
    query = "NbSe2"
    base_url, entries = search_optimade(query, max_results=5)
    
    if not base_url or not entries:
        # Fallback to MoS2
        query = "MoS2"
        base_url, entries = search_optimade(query, max_results=5)
    
    if not base_url or not entries:
        pytest.fail(
            f"Could not fetch structure from OPTIMADE. "
            f"Tried: NbSe2, MoS2. "
            f"Bases: {OPTIMADE_BASES}. "
            f"This test must not be skipped. If OPTIMADE is down, CI should fail."
        )
    
    # Get first entry
    entry = entries[0]
    entry_id = entry.get("id")
    if not entry_id:
        pytest.fail(
            f"Entry has no 'id' field. Entry keys: {list(entry.keys())}. "
            f"This test must not be skipped."
        )
    
    # Fetch full structure
    structure_online, optimade_raw = fetch_structure_from_optimade(base_url, entry_id)
    if structure_online is None:
        pytest.fail(
            f"Could not fetch structure {entry_id} from OPTIMADE base {base_url}. "
            f"This test must not be skipped. If OPTIMADE is down, CI should fail."
        )
    
    # Step 2: Convert to primitive (online path does this)
    structure_online = structure_online.get_primitive_structure()
    
    # Step 3: Test with same viewer params (supercell + boundary repeat)
    params = DisplayModeParams(
        mode="supercell",
        supercell=(2, 2, 2),
        repeat_boundary=True,
        box_bounds=None,
    )
    
    # Path A: Online pipeline (direct call to shared builder)
    payload_online = QVService._build_structure_vis_payload(
        structure_online,
        params,
        structure_meta={"structure_id": f"online:{entry_id}"},
        trace_id="test_online_alignment",
    )
    
    # Path B: Project pipeline (write to file, then load and call shared builder)
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        structures_dir = project_root / "structures"
        structures_dir.mkdir(parents=True, exist_ok=True)
        
        # Write structure as project file
        structure_file = structures_dir / "test_structure.json"
        write_structure(structure_online, structure_file)
        
        # Load as project structure
        structure_project = read_structure(structure_file)
        
        # Call shared builder (same as project path)
        payload_project = QVService._build_structure_vis_payload(
            structure_project,
            params,
            structure_meta={"structure_id": "test_project"},
            trace_id="test_project_alignment",
        )
    
    # Step 4: Compare outputs (must be identical within tolerance)
    
    # 4.1: Lattice comparison
    lattice_online = np.array(payload_online["lattice"]["matrix"])
    lattice_project = np.array(payload_project["lattice"]["matrix"])
    lattice_diff = np.abs(lattice_online - lattice_project)
    max_lattice_diff = lattice_diff.max()
    assert max_lattice_diff < 1e-8, (
        f"Lattice mismatch: max diff = {max_lattice_diff:.2e}\n"
        f"Online:\n{lattice_online}\n"
        f"Project:\n{lattice_project}"
    )
    
    # 4.2: Display atoms count
    n_atoms_online = len(payload_online["atoms"])
    n_atoms_project = len(payload_project["atoms"])
    assert n_atoms_online == n_atoms_project, (
        f"Atom count mismatch: online={n_atoms_online}, project={n_atoms_project}"
    )
    
    # 4.3: Element sequence consistency
    elements_online = [atom["element"] for atom in payload_online["atoms"]]
    elements_project = [atom["element"] for atom in payload_project["atoms"]]
    assert elements_online == elements_project, (
        f"Element sequence mismatch:\n"
        f"Online: {elements_online[:20]}...\n"
        f"Project: {elements_project[:20]}..."
    )
    
    # 4.4: Cartesian coordinates consistency
    for i, (atom_online, atom_project) in enumerate(zip(
        payload_online["atoms"], payload_project["atoms"]
    )):
        cart_online = np.array(atom_online["cart_coords"])
        cart_project = np.array(atom_project["cart_coords"])
        cart_diff = np.abs(cart_online - cart_project)
        max_cart_diff = cart_diff.max()
        assert max_cart_diff < 1e-6, (
            f"Cartesian coords mismatch at atom {i} ({atom_online['element']}): "
            f"max diff = {max_cart_diff:.2e}\n"
            f"Online: {cart_online}\n"
            f"Project: {cart_project}"
        )
    
    # 4.5: Boundary atoms count
    n_boundary_online = len(payload_online.get("boundary_atoms", []))
    n_boundary_project = len(payload_project.get("boundary_atoms", []))
    assert n_boundary_online == n_boundary_project, (
        f"Boundary atom count mismatch: online={n_boundary_online}, project={n_boundary_project}"
    )
    
    # 4.6: Bonds comparison (unordered set of (i,j) pairs)
    def get_bond_pairs(bonds):
        """Extract (i,j) pairs from bonds list, normalized to i < j."""
        pairs = set()
        for bond in bonds:
            i, j = bond["idx1"], bond["idx2"]
            pairs.add((min(i, j), max(i, j)))
        return pairs
    
    def get_bond_signatures(bonds, atoms):
        """Get bond signatures: (i, j, distance, elem_i, elem_j) for comparison."""
        signatures = []
        for bond in bonds:
            i, j = bond["idx1"], bond["idx2"]
            elem_i = atoms[i]["element"] if i < len(atoms) else "?"
            elem_j = atoms[j]["element"] if j < len(atoms) else "?"
            signatures.append((min(i, j), max(i, j), bond["distance"], elem_i, elem_j))
        return set(signatures)
    
    # Compare bond pairs
    bonds_online_pairs = get_bond_pairs(payload_online["bonds"])
    bonds_project_pairs = get_bond_pairs(payload_project["bonds"])
    
    if bonds_online_pairs != bonds_project_pairs:
        # Try signature-based comparison (allows small distance differences)
        all_atoms_online = payload_online["atoms"] + payload_online.get("boundary_atoms", [])
        all_atoms_project = payload_project["atoms"] + payload_project.get("boundary_atoms", [])
        
        sigs_online = get_bond_signatures(payload_online["bonds"], all_atoms_online)
        sigs_project = get_bond_signatures(payload_project["bonds"], all_atoms_project)
        
        missing_in_project = sigs_online - sigs_project
        extra_in_project = sigs_project - sigs_online
        
        if missing_in_project or extra_in_project:
            pytest.fail(
                f"Bond set mismatch:\n"
                f"Missing in project: {list(missing_in_project)[:10]}\n"
                f"Extra in project: {list(extra_in_project)[:10]}\n"
                f"Online bonds: {len(payload_online['bonds'])}\n"
                f"Project bonds: {len(payload_project['bonds'])}"
            )
    
    # 4.7: Max bond length and max degree consistency
    if payload_online["bonds"] and payload_project["bonds"]:
        max_bond_online = max(b["distance"] for b in payload_online["bonds"])
        max_bond_project = max(b["distance"] for b in payload_project["bonds"])
        max_bond_diff = abs(max_bond_online - max_bond_project)
        assert max_bond_diff < 1e-6, (
            f"Max bond length mismatch: online={max_bond_online:.6f}Å, "
            f"project={max_bond_project:.6f}Å, diff={max_bond_diff:.2e}Å"
        )
        
        # Compute max degree
        def compute_max_degree(bonds, payload):
            n_total = len(payload["atoms"]) + len(payload.get("boundary_atoms", []))
            degrees = [0] * n_total
            for bond in bonds:
                i, j = bond["idx1"], bond["idx2"]
                if i < n_total:
                    degrees[i] += 1
                if j < n_total:
                    degrees[j] += 1
            return max(degrees) if degrees else 0
        
        max_degree_online = compute_max_degree(payload_online["bonds"], payload_online)
        max_degree_project = compute_max_degree(payload_project["bonds"], payload_project)
        assert max_degree_online == max_degree_project, (
            f"Max degree mismatch: online={max_degree_online}, project={max_degree_project}"
        )
        
        # No long-bond spikes
        assert max_bond_online < 6.0, (
            f"Online max bond ({max_bond_online:.3f}Å) should be < 6.0Å"
        )
        assert max_degree_online < 24, (
            f"Online max degree ({max_degree_online}) should be < 24"
        )
    
    # Test passes if all assertions pass
    print(f"\n✓ Pipeline alignment test passed for {query}")
    print(f"  Structure: {entry_id}")
    print(f"  Atoms: {n_atoms_online}")
    print(f"  Bonds: {len(payload_online['bonds'])}")
    print(f"  Max bond: {max_bond_online:.3f}Å" if payload_online["bonds"] else "  No bonds")
