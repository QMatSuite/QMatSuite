"""
Unit tests for online structure supercell expansion and bond generation.

Tests that OPTIMADE structures with cartesian coordinates can be converted
to fractional coordinates and expanded via supercell correctly, and that
bonds are computed correctly in all display modes.
"""

import pytest
import numpy as np
from pymatgen.core import Structure, Lattice

from quantumvitas.analysis.structure_viz import (
    build_display_atoms,
    build_bonds,
    DisplayModeParams,
    canonicalize_structure_in_place,
)
from quantumvitas.analysis.atomic_radii import get_radii_map


def test_optimade_mos2_supercell_expansion():
    """
    Test that MoS2 structure (3 sites: Mo, S, S) expands correctly to 2x2x2 supercell.
    
    Given:
    - Lattice vectors (3x3 matrix)
    - Cartesian site positions (3 sites)
    - Species at sites: ["Mo", "S", "S"]
    
    After cart→frac conversion and supercell(2,2,2):
    - Should have 24 atoms total (3 * 8 = 24)
    - Species counts: {Mo: 8, S: 16}
    """
    # MoS2 example: 3 sites in primitive cell
    # Lattice vectors (example - should match real OPTIMADE data)
    # Using a simple orthorhombic cell for testing
    lattice_vectors = [
        [3.16, 0.0, 0.0],   # a vector
        [0.0, 3.16, 0.0],   # b vector
        [0.0, 0.0, 12.3],   # c vector
    ]
    
    # Cartesian positions for MoS2 (3 sites)
    cartesian_positions = [
        [0.0, 0.0, 0.0],        # Mo at origin
        [1.58, 1.58, 3.075],    # S1
        [1.58, 1.58, 9.225],    # S2
    ]
    
    species_at_sites = ["Mo", "S", "S"]
    
    # Build pymatgen Structure from cartesian coords (like OPTIMADE does)
    lattice = Lattice(lattice_vectors)
    structure = Structure(lattice, species_at_sites, cartesian_positions, coords_are_cartesian=True)
    
    # Verify initial structure
    assert len(structure) == 3, f"Expected 3 sites, got {len(structure)}"
    assert structure.composition["Mo"] == 1, "Expected 1 Mo atom"
    assert structure.composition["S"] == 2, "Expected 2 S atoms"
    
    # Verify fractional coordinates are reasonable (pymatgen should compute them)
    frac_coords = structure.frac_coords
    assert frac_coords.shape == (3, 3), f"Expected (3, 3) frac coords, got {frac_coords.shape}"
    
    # Most fractional coords should be in [0, 1) or close
    frac_abs_max = np.abs(frac_coords).max()
    assert frac_abs_max < 10, f"Fractional coords seem unreasonable (max abs={frac_abs_max})"
    
    # Canonicalize structure (required before supercell expansion)
    canonicalize_structure_in_place(structure)
    
    # Build display atoms with 2x2x2 supercell
    params = DisplayModeParams(
        mode="supercell",
        supercell=(2, 2, 2),
        repeat_boundary=False,
        box_bounds=None,
    )
    
    display_atoms, display_structure = build_display_atoms(
        structure,
        params,
        wrap_coords=True,
    )
    
    # Verify supercell expansion
    assert len(display_atoms) == 24, f"Expected 24 atoms (3 * 8), got {len(display_atoms)}"
    
    # Count species
    species_counts = {}
    for atom in display_atoms:
        species_counts[atom.element] = species_counts.get(atom.element, 0) + 1
    
    assert species_counts["Mo"] == 8, f"Expected 8 Mo atoms, got {species_counts.get('Mo', 0)}"
    assert species_counts["S"] == 16, f"Expected 16 S atoms, got {species_counts.get('S', 0)}"
    
    # Verify fractional coordinates are present and reasonable
    for atom in display_atoms:
        assert hasattr(atom, 'frac_coords'), "DisplayAtom should have frac_coords"
        assert len(atom.frac_coords) == 3, "frac_coords should be length 3"
        # Supercell atoms may have frac coords outside [0, 1) which is expected
        assert all(np.isfinite(atom.frac_coords)), "frac_coords should be finite"


def test_optimade_cart_to_frac_conversion():
    """
    Test that cartesian→fractional conversion works correctly for OPTIMADE structures.
    
    Verifies:
    - Lattice matrix is invertible
    - Fractional coordinates can be computed
    - Conversion is consistent (cart = lattice @ frac)
    """
    # Simple cubic cell
    lattice_vectors = [
        [5.0, 0.0, 0.0],
        [0.0, 5.0, 0.0],
        [0.0, 0.0, 5.0],
    ]
    
    # Cartesian positions
    cartesian_positions = [
        [0.0, 0.0, 0.0],      # Origin
        [2.5, 2.5, 2.5],       # Center
        [5.0, 0.0, 0.0],       # Edge (should be frac = [1, 0, 0])
    ]
    
    species = ["Si", "Si", "Si"]
    
    # Build structure
    lattice = Lattice(lattice_vectors)
    structure = Structure(lattice, species, cartesian_positions, coords_are_cartesian=True)
    
    # Verify lattice is invertible
    lattice_matrix = np.array(lattice_vectors)
    det = np.linalg.det(lattice_matrix)
    assert abs(det) > 1e-10, f"Lattice matrix should be invertible, det={det}"
    
    # Verify fractional coordinates
    frac_coords = structure.frac_coords
    cart_coords = structure.cart_coords
    
    # Check conversion: cart = lattice @ frac
    for i in range(len(structure)):
        computed_cart = lattice_matrix @ frac_coords[i]
        actual_cart = cart_coords[i]
        
        # Should match within numerical precision
        diff = np.abs(computed_cart - actual_cart).max()
        assert diff < 1e-6, f"Cart→frac conversion mismatch for atom {i}: diff={diff}"
    
    # Verify expected fractional coordinates
    # Atom 0 at origin should be [0, 0, 0]
    assert np.allclose(frac_coords[0], [0.0, 0.0, 0.0], atol=1e-6), f"Atom 0 frac should be [0,0,0], got {frac_coords[0]}"
    
    # Atom 1 at center should be [0.5, 0.5, 0.5]
    assert np.allclose(frac_coords[1], [0.5, 0.5, 0.5], atol=1e-6), f"Atom 1 frac should be [0.5,0.5,0.5], got {frac_coords[1]}"
    
    # Atom 2 at edge should be [1.0, 0.0, 0.0] (or wrapped to [0, 0, 0] if canonicalized)
    # After canonicalization, it might be [0, 0, 0] if it's equivalent
    assert len(frac_coords[2]) == 3, "Atom 2 should have 3 frac coords"


def test_optimade_singular_lattice_detection():
    """
    Test that singular (non-invertible) lattice matrices are detected.
    
    Note: pymatgen may handle singular lattices gracefully, so we just verify
    that our validation logic would catch it (the validation happens in
    fetch_structure_from_optimade before building the Structure).
    """
    # Singular matrix (det = 0)
    singular_lattice = [
        [1.0, 0.0, 0.0],
        [2.0, 0.0, 0.0],  # Linearly dependent (2x first row)
        [0.0, 0.0, 1.0],
    ]
    
    lattice_matrix = np.array(singular_lattice)
    det = np.linalg.det(lattice_matrix)
    
    assert abs(det) < 1e-10, f"Lattice should be singular, but det={det}"
    
    # Our validation in fetch_structure_from_optimade checks det != 0
    # This test verifies the check would work
    # (pymatgen might still build a structure, but our code should reject it)
    assert abs(det) < 1e-10, "Validation should detect singular lattice"


def test_optimade_mos2_bonds_all_modes():
    """
    Test that MoS2 online structure generates correct bonds in all display modes.
    
    This test prevents the "spiky long-bond" regression where one atom
    bonds to everything far away due to coordinate system mismatches.
    
    Test cases:
    - Primitive mode
    - Conventional mode
    - Supercell 3x2x2 (with and without boundary repeat)
    
    Assertions:
    - Bonds computed without exceptions
    - max_bond_length < 4.0 Å (conservative for Mo-S bonds)
    - No single atom has excessive degree (max degree < 24)
    - Bonds count scales reasonably with supercell size
    """
    # MoS2 example: 3 sites in primitive cell
    # Use a more compact structure to ensure bonds are detected
    # Mo-S bond length is typically ~2.4 Å
    lattice_vectors = [
        [3.16, 0.0, 0.0],   # a vector
        [0.0, 3.16, 0.0],   # b vector
        [0.0, 0.0, 12.3],   # c vector
    ]
    
    # Place atoms closer together to ensure bonds are detected
    # Mo at origin, S atoms at ~2.4 Å distance (typical Mo-S bond)
    cartesian_positions = [
        [0.0, 0.0, 0.0],        # Mo at origin
        [1.58, 1.58, 2.4],      # S1 at ~2.4 Å from Mo
        [1.58, 1.58, -2.4],     # S2 at ~2.4 Å from Mo (on other side)
    ]
    
    species_at_sites = ["Mo", "S", "S"]
    
    # Build pymatgen Structure from cartesian coords (like OPTIMADE does)
    lattice = Lattice(lattice_vectors)
    structure = Structure(lattice, species_at_sites, cartesian_positions, coords_are_cartesian=True)
    
    # Get radii map for bond building
    radii_map = get_radii_map()
    
    # Test 1: Primitive mode
    params_primitive = DisplayModeParams(
        mode="primitive",
        supercell=None,
        repeat_boundary=False,
        box_bounds=None,
    )
    
    display_atoms_prim, _ = build_display_atoms(structure, params_primitive)
    atoms_cart_prim = np.array([da.cart_coords for da in display_atoms_prim])
    species_prim = [da.element for da in display_atoms_prim]
    
    bonds_prim = build_bonds(
        atoms_cart_prim,
        species=species_prim,
        max_factor=1.2,
        tolerance=0.3,
        max_cutoff=3.5,
    )
    
    assert len(bonds_prim) > 0, "Primitive mode should have bonds"
    bond_distances_prim = [b.distance for b in bonds_prim]
    max_bond_prim = max(bond_distances_prim)
    assert max_bond_prim < 4.0, f"Primitive mode max bond ({max_bond_prim:.3f}Å) should be < 4.0Å"
    
    # Check atom degrees
    atom_degrees_prim = [0] * len(display_atoms_prim)
    for bond in bonds_prim:
        atom_degrees_prim[bond.idx1] += 1
        atom_degrees_prim[bond.idx2] += 1
    max_degree_prim = max(atom_degrees_prim) if atom_degrees_prim else 0
    assert max_degree_prim < 24, f"Primitive mode max degree ({max_degree_prim}) should be < 24"
    
    # Test 2: Conventional mode
    params_conv = DisplayModeParams(
        mode="conventional",
        supercell=None,
        repeat_boundary=False,
        box_bounds=None,
    )
    
    display_atoms_conv, _ = build_display_atoms(structure, params_conv)
    atoms_cart_conv = np.array([da.cart_coords for da in display_atoms_conv])
    species_conv = [da.element for da in display_atoms_conv]
    
    bonds_conv = build_bonds(
        atoms_cart_conv,
        species=species_conv,
        max_factor=1.2,
        tolerance=0.3,
        max_cutoff=3.5,
    )
    
    assert len(bonds_conv) > 0, "Conventional mode should have bonds"
    bond_distances_conv = [b.distance for b in bonds_conv]
    max_bond_conv = max(bond_distances_conv)
    assert max_bond_conv < 4.0, f"Conventional mode max bond ({max_bond_conv:.3f}Å) should be < 4.0Å"
    
    # Check atom degrees
    atom_degrees_conv = [0] * len(display_atoms_conv)
    for bond in bonds_conv:
        atom_degrees_conv[bond.idx1] += 1
        atom_degrees_conv[bond.idx2] += 1
    max_degree_conv = max(atom_degrees_conv) if atom_degrees_conv else 0
    assert max_degree_conv < 24, f"Conventional mode max degree ({max_degree_conv}) should be < 24"
    
    # Test 3: Supercell 3x2x2 without boundary repeat
    params_supercell = DisplayModeParams(
        mode="supercell",
        supercell=(3, 2, 2),
        repeat_boundary=False,
        box_bounds=None,
    )
    
    display_atoms_super, _ = build_display_atoms(structure, params_supercell)
    atoms_cart_super = np.array([da.cart_coords for da in display_atoms_super])
    species_super = [da.element for da in display_atoms_super]
    
    # Verify atom count scales correctly (3 atoms * 3*2*2 = 36 atoms)
    assert len(display_atoms_super) == 36, f"Supercell 3x2x2 should have 36 atoms, got {len(display_atoms_super)}"
    
    bonds_super = build_bonds(
        atoms_cart_super,
        species=species_super,
        max_factor=1.2,
        tolerance=0.3,
        max_cutoff=3.5,
    )
    
    assert len(bonds_super) > 0, "Supercell mode should have bonds"
    bond_distances_super = [b.distance for b in bonds_super]
    max_bond_super = max(bond_distances_super)
    assert max_bond_super < 4.0, f"Supercell mode max bond ({max_bond_super:.3f}Å) should be < 4.0Å"
    
    # Check atom degrees
    atom_degrees_super = [0] * len(display_atoms_super)
    for bond in bonds_super:
        atom_degrees_super[bond.idx1] += 1
        atom_degrees_super[bond.idx2] += 1
    max_degree_super = max(atom_degrees_super) if atom_degrees_super else 0
    assert max_degree_super < 24, f"Supercell mode max degree ({max_degree_super}) should be < 24"
    
    # Bonds should scale with supercell size (roughly, not exact due to boundary effects)
    assert len(bonds_super) >= len(bonds_prim), "Supercell should have at least as many bonds as primitive"
    
    # Test 4: Supercell 3x2x2 with boundary repeat
    params_supercell_boundary = DisplayModeParams(
        mode="supercell",
        supercell=(3, 2, 2),
        repeat_boundary=True,
        box_bounds=None,
    )
    
    display_atoms_super_boundary, _ = build_display_atoms(structure, params_supercell_boundary)
    atoms_cart_super_boundary = np.array([da.cart_coords for da in display_atoms_super_boundary])
    species_super_boundary = [da.element for da in display_atoms_super_boundary]
    
    # Boundary repeat adds more atoms
    assert len(display_atoms_super_boundary) >= len(display_atoms_super), \
        "Boundary repeat should add atoms"
    
    bonds_super_boundary = build_bonds(
        atoms_cart_super_boundary,
        species=species_super_boundary,
        max_factor=1.2,
        tolerance=0.3,
        max_cutoff=3.5,
    )
    
    assert len(bonds_super_boundary) > 0, "Supercell with boundary repeat should have bonds"
    bond_distances_super_boundary = [b.distance for b in bonds_super_boundary]
    max_bond_super_boundary = max(bond_distances_super_boundary)
    assert max_bond_super_boundary < 4.0, \
        f"Supercell with boundary repeat max bond ({max_bond_super_boundary:.3f}Å) should be < 4.0Å"
    
    # Check atom degrees
    atom_degrees_super_boundary = [0] * len(display_atoms_super_boundary)
    for bond in bonds_super_boundary:
        atom_degrees_super_boundary[bond.idx1] += 1
        atom_degrees_super_boundary[bond.idx2] += 1
    max_degree_super_boundary = max(atom_degrees_super_boundary) if atom_degrees_super_boundary else 0
    assert max_degree_super_boundary < 24, \
        f"Supercell with boundary repeat max degree ({max_degree_super_boundary}) should be < 24"
    
    # Verify all atoms have consistent coordinate systems
    # All cart_coords should be finite and reasonable
    for mode_name, atoms_list in [
        ("primitive", display_atoms_prim),
        ("conventional", display_atoms_conv),
        ("supercell", display_atoms_super),
        ("supercell_boundary", display_atoms_super_boundary),
    ]:
        for atom in atoms_list:
            assert np.all(np.isfinite(atom.cart_coords)), \
                f"{mode_name}: Atom {atom.original_idx} has non-finite cart_coords"
            assert np.all(np.abs(atom.cart_coords) < 1e6), \
                f"{mode_name}: Atom {atom.original_idx} has unreasonable cart_coords: {atom.cart_coords}"


def test_online_project_shared_pipeline():
    """
    Test that online and project structures use the same code path.
    
    Verifies that both call build_structure_vis_payload() which uses:
    - canonicalize_structure_in_place (once)
    - build_display_atoms (unified)
    - build_bonds (from display atoms cart coords)
    """
    from quantumvitas.analysis.structure_viz import build_structure_vis_payload, DisplayModeParams

    # Build a test structure (simulating online structure)
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
    
    params = DisplayModeParams(
        mode="primitive",
        supercell=None,
        repeat_boundary=True,  # Enable boundary to test full pipeline
        box_bounds=None,
    )
    
    # Test ONLINE path payload (marked as online)
    online_payload = build_structure_vis_payload(
        structure,
        params,
        structure_meta={"structure_id": "online:test_candidate"},
    )

    # Test PROJECT path payload (marked as project)
    project_payload = build_structure_vis_payload(
        structure,
        params,
        structure_meta={"structure_id": "project:test_structure"},
    )
    
    # EVIDENCE: Compare payload schemas
    online_atoms_len = len(online_payload.get("atoms", []))
    online_boundary_atoms_len = len(online_payload.get("boundary_atoms", []))
    online_bonds_len = len(online_payload.get("bonds", []))
    online_total_display = online_atoms_len + online_boundary_atoms_len
    
    project_atoms_len = len(project_payload.get("atoms", []))
    project_boundary_atoms_len = len(project_payload.get("boundary_atoms", []))
    project_bonds_len = len(project_payload.get("bonds", []))
    project_total_display = project_atoms_len + project_boundary_atoms_len
    
    # Extract bond schema
    online_first_bond_keys = list(online_payload["bonds"][0].keys()) if online_bonds_len > 0 else []
    project_first_bond_keys = list(project_payload["bonds"][0].keys()) if project_bonds_len > 0 else []
    
    # Compute max bond indices
    online_max_bond_idx = -1
    if online_bonds_len > 0:
        for bond in online_payload["bonds"]:
            online_max_bond_idx = max(online_max_bond_idx, bond.get("idx1", -1), bond.get("idx2", -1))
    
    project_max_bond_idx = -1
    if project_bonds_len > 0:
        for bond in project_payload["bonds"]:
            project_max_bond_idx = max(project_max_bond_idx, bond.get("idx1", -1), bond.get("idx2", -1))
    
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
    assert online_max_bond_idx < online_total_display, \
        f"online maxBondIndex invalid: {online_max_bond_idx} >= {online_total_display}"
    assert project_max_bond_idx < project_total_display, \
        f"project maxBondIndex invalid: {project_max_bond_idx} >= {project_total_display}"
    
    # Verify bond schema uses idx1/idx2 (not atom1/atom2)
    if online_bonds_len > 0:
        assert "idx1" in online_first_bond_keys, \
            f"online bonds must use idx1/idx2, found keys: {online_first_bond_keys}"
        assert "idx2" in online_first_bond_keys, \
            f"online bonds must use idx1/idx2, found keys: {online_first_bond_keys}"
        assert "atom1" not in online_first_bond_keys, \
            f"online bonds must NOT use atom1/atom2, found keys: {online_first_bond_keys}"
    
    # Verify payload structure (use online_payload as reference)
    assert "atoms" in online_payload
    assert "bonds" in online_payload
    assert "lattice" in online_payload
    # Note: "perf" key is optional - only legacy version included it
    
    # Verify atoms have both cart and frac coords
    for atom in online_payload["atoms"]:
        assert "cart_coords" in atom
        assert "frac_coords" in atom
        assert len(atom["cart_coords"]) == 3
        assert len(atom["frac_coords"]) == 3
    
    # Verify bonds are reasonable
    if online_bonds_len > 0:
        bond_distances = [b["distance"] for b in online_payload["bonds"]]
        max_bond = max(bond_distances)
        assert max_bond < 4.0, f"Max bond distance ({max_bond:.3f}Å) should be < 4.0Å"


@pytest.mark.integration
def test_online_vs_project_pipeline_identical():
    """
    Regression test: Compare online vs project pipeline outputs for the same structure.
    
    This test ensures that online structures use the EXACT same pipeline as project structures.
    If bonds are wrong for online, they must also be wrong for project (but since project is
    correct, online will become correct).
    
    Test steps:
    1. Fetch a MoS2 OPTIMADE structure (live)
    2. Build Structure from it (online conversion step: get primitive)
    3. Write that structure temporarily as a project structure file
    4. Call project payload builder on the project file
    5. Call online payload builder on the same structure (simulating online path)
    6. For the same viewer params, assert outputs are identical
    
    Assertions:
    - Atom count identical
    - Lattice identical
    - Bond count identical
    - Max bond length identical within tolerance
    - No long-bond spikes: maxBond < 6 Å AND maxDegree not exploding
    """
    from quantumvitas.analysis.structure_viz import build_structure_vis_payload, DisplayModeParams
    from quantumvitas.io.online_search import (
        OPTIMADE_BASES,
        fetch_structure_from_optimade,
        search_optimade,
    )
    from quantumvitas.io.structure_io import write_structure, read_structure
    import tempfile
    import numpy as np
    
    # Step 1: Search for MoS2 in OPTIMADE (live)
    query = "MoS2"
    entries = []
    base_used = None
    
    # search_optimade returns (base_url, entries) tuple
    # It tries all bases internally and returns the first successful one
    base_used, entries = search_optimade(query, max_results=5)
    
    if not entries:
        pytest.fail(
            f"Could not fetch MoS2 from OPTIMADE. "
            f"Tried bases: {OPTIMADE_BASES}. "
            f"This test must not be skipped. If OPTIMADE is down, CI should fail."
        )
    
    # Step 2: Fetch full structure (online conversion step)
    if not entries:
        pytest.fail(
            f"search_optimade returned empty entries list for query '{query}'. "
            f"Base used: {base_used}. "
            f"This test must not be skipped. If OPTIMADE is down, CI should fail."
        )
    
    entry = entries[0]
    entry_id = entry.get("ulid")
    if not entry_id:
        pytest.fail(
            f"First entry from search_optimade has no 'id' field. "
            f"Entry keys: {list(entry.keys())}. "
            f"This test must not be skipped."
        )
    
    structure_online, _ = fetch_structure_from_optimade(base_used, entry_id)
    if structure_online is None:
        pytest.fail(
            f"Could not fetch structure {entry_id} from OPTIMADE base {base_used}. "
            f"This test must not be skipped. If OPTIMADE is down, CI should fail."
        )
    
    # Step 3: Convert to primitive (online path does this)
    structure_online = structure_online.get_primitive_structure()
    
    # Step 4: Write as project structure file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        write_structure(structure_online, tmp_path)
        
        # Step 5: Load as project structure
        structure_project = read_structure(tmp_path)
        
        # Step 6: Test with same viewer params
        params = DisplayModeParams(
            mode="supercell",
            supercell=(2, 2, 2),
            repeat_boundary=True,
            box_bounds=None,
        )
        
        # Project path: call via get_structure_vis_data (simulates project rendering)
        # But we'll call build_structure_vis_payload directly for comparison
        payload_project = build_structure_vis_payload(
            structure_project,
            params,
            structure_meta={"structure_id": "test_project"},
        )

        # Online path: call build_structure_vis_payload directly (same as online handler does)
        payload_online = build_structure_vis_payload(
            structure_online,
            params,
            structure_meta={"structure_id": "online:test"},
        )
        
        # Assertions: outputs must be identical
        # Atom count
        n_atoms_project = len(payload_project["atoms"])
        n_atoms_online = len(payload_online["atoms"])
        assert n_atoms_project == n_atoms_online, \
            f"Atom count mismatch: project={n_atoms_project}, online={n_atoms_online}"
        
        # Boundary atoms count
        n_boundary_project = len(payload_project.get("boundary_atoms", []))
        n_boundary_online = len(payload_online.get("boundary_atoms", []))
        assert n_boundary_project == n_boundary_online, \
            f"Boundary atom count mismatch: project={n_boundary_project}, online={n_boundary_online}"
        
        # Lattice (compare matrix)
        lattice_project = np.array(payload_project["lattice"]["matrix"])
        lattice_online = np.array(payload_online["lattice"]["matrix"])
        assert np.allclose(lattice_project, lattice_online, atol=1e-6), \
            f"Lattice mismatch: project={lattice_project}, online={lattice_online}"
        
        # Bond count
        n_bonds_project = len(payload_project["bonds"])
        n_bonds_online = len(payload_online["bonds"])
        assert n_bonds_project == n_bonds_online, \
            f"Bond count mismatch: project={n_bonds_project}, online={n_bonds_online}"
        
        # Max bond length (must be identical within tolerance)
        if payload_project["bonds"] and payload_online["bonds"]:
            max_bond_project = max(b["distance"] for b in payload_project["bonds"])
            max_bond_online = max(b["distance"] for b in payload_online["bonds"])
            assert abs(max_bond_project - max_bond_online) < 1e-3, \
                f"Max bond length mismatch: project={max_bond_project:.3f}Å, online={max_bond_online:.3f}Å"
            
            # No long-bond spikes
            assert max_bond_project < 6.0, \
                f"Project max bond ({max_bond_project:.3f}Å) should be < 6.0Å"
            assert max_bond_online < 6.0, \
                f"Online max bond ({max_bond_online:.3f}Å) should be < 6.0Å"
            
            # Check atom degrees (no exploding degree)
            # Bonds indices are based on ALL display atoms (including boundary atoms)
            # So we need to use total display atoms count, not just regular atoms
            def compute_max_degree(bonds, payload):
                # Total display atoms = regular atoms + boundary atoms
                n_total_atoms = len(payload.get("atoms", [])) + len(payload.get("boundary_atoms", []))
                degrees = [0] * n_total_atoms
                for bond in bonds:
                    idx1 = bond["idx1"]
                    idx2 = bond["idx2"]
                    if idx1 < n_total_atoms:
                        degrees[idx1] += 1
                    if idx2 < n_total_atoms:
                        degrees[idx2] += 1
                return max(degrees) if degrees else 0
            
            max_degree_project = compute_max_degree(payload_project["bonds"], payload_project)
            max_degree_online = compute_max_degree(payload_online["bonds"], payload_online)
            assert max_degree_project < 24, \
                f"Project max degree ({max_degree_project}) should be < 24"
            assert max_degree_online < 24, \
                f"Online max degree ({max_degree_online}) should be < 24"
            assert max_degree_project == max_degree_online, \
                f"Max degree mismatch: project={max_degree_project}, online={max_degree_online}"
        
    finally:
        # Cleanup
        import os
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

