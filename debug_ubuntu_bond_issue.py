#!/usr/bin/env python3
"""Debug script to investigate Ubuntu bond count issue."""

import numpy as np
from pymatgen.core import Lattice, Structure
from quantumvitas.analysis.structure_viz import (
    canonicalize_structure_in_place,
    make_supercell,
    detect_bonds,
    build_bonds_bruteforce,
    get_element_radius,
    BOUNDARY_FRAC_TOL,
)

# Create Si diamond structure
a = 5.431
a1 = a / 2 * np.array([-1, 0, 1])
a2 = a / 2 * np.array([0, 1, 1])
a3 = a / 2 * np.array([-1, 1, 0])
lattice = Lattice([a1, a2, a3])

structure = Structure(
    lattice,
    ["Si", "Si"],
    [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]],
    coords_are_cartesian=False,
)

print("=== Initial Structure ===")
print(f"Num atoms: {len(structure)}")
for i, site in enumerate(structure):
    print(f"Atom {i}: frac={site.frac_coords}, cart={site.coords}")

# Canonicalize
structure_canon = structure.copy()
canonicalize_structure_in_place(structure_canon, eps=BOUNDARY_FRAC_TOL)

print("\n=== After Canonicalization ===")
for i, site in enumerate(structure_canon):
    print(f"Atom {i}: frac={site.frac_coords}, cart={site.coords}")

# Create supercell
supercell = make_supercell(structure_canon, (2, 2, 2))

print(f"\n=== Supercell (2x2x2) ===")
print(f"Num atoms: {len(supercell)}")
print(f"BOUNDARY_FRAC_TOL: {BOUNDARY_FRAC_TOL}")

# Check for duplicate positions (within tolerance)
atoms_cart = np.array([site.coords for site in supercell])
print(f"\n=== Checking for duplicate positions ===")
tolerance = 1e-6
duplicates = []
for i in range(len(atoms_cart)):
    for j in range(i + 1, len(atoms_cart)):
        dist = np.linalg.norm(atoms_cart[i] - atoms_cart[j])
        if dist < tolerance:
            duplicates.append((i, j, dist))
            print(f"Duplicate positions: atom {i} and {j}, distance={dist:.2e}")

if not duplicates:
    print("No duplicate positions found")

# Check fractional coordinates
print(f"\n=== Fractional coordinates in supercell ===")
for i, site in enumerate(supercell):
    frac = site.frac_coords
    # Check if any coordinate is very close to an integer
    for dim in range(3):
        f = frac[dim]
        k = np.round(f)
        diff = abs(f - k)
        if diff < BOUNDARY_FRAC_TOL:
            print(f"Atom {i}, dim {dim}: {f} is close to integer {k} (diff={diff:.2e})")

# Detect bonds
bonds = detect_bonds(supercell, include_periodic_images=False)
print(f"\n=== Bond Detection ===")
print(f"Number of bonds: {len(bonds)}")

# Check bond distances
print(f"\n=== Bond distances ===")
distances = [b.distance for b in bonds]
print(f"Min distance: {min(distances):.6f}")
print(f"Max distance: {max(distances):.6f}")
print(f"Mean distance: {np.mean(distances):.6f}")

# Check for bonds with very similar distances (potential duplicates)
print(f"\n=== Checking for bonds with similar distances ===")
distance_tolerance = 1e-5
similar_bonds = []
for i, b1 in enumerate(bonds):
    for j, b2 in enumerate(bonds[i+1:], start=i+1):
        if abs(b1.distance - b2.distance) < distance_tolerance:
            # Check if they connect the same pair of atoms (accounting for order)
            pair1 = (min(b1.idx1, b1.idx2), max(b1.idx1, b1.idx2))
            pair2 = (min(b2.idx1, b2.idx2), max(b2.idx1, b2.idx2))
            if pair1 == pair2:
                similar_bonds.append((i, j, b1, b2))
                print(f"Duplicate bond: bond {i} and {j} both connect {pair1}, "
                      f"distances={b1.distance:.6f} and {b2.distance:.6f}")

if not similar_bonds:
    print("No duplicate bonds found")

# Check atom positions more carefully
print(f"\n=== Detailed atom position analysis ===")
print("Checking if any atoms are at exactly the same position (within 1e-10):")
for i in range(len(atoms_cart)):
    for j in range(i + 1, len(atoms_cart)):
        dist = np.linalg.norm(atoms_cart[i] - atoms_cart[j])
        if dist < 1e-10:
            print(f"  Atoms {i} and {j} are at the same position (dist={dist:.2e})")
            print(f"    Atom {i}: cart={atoms_cart[i]}, frac={supercell[i].frac_coords}")
            print(f"    Atom {j}: cart={atoms_cart[j]}, frac={supercell[j].frac_coords}")

# Check if canonicalization is working correctly
print(f"\n=== Canonicalization check ===")
print("Checking if canonicalization snaps values correctly:")
for i, site in enumerate(structure_canon):
    frac = site.frac_coords
    for dim in range(3):
        f = frac[dim]
        # Check if it should have been snapped
        k = np.round(f)
        if abs(f - k) < BOUNDARY_FRAC_TOL:
            if f != k:
                print(f"  WARNING: Atom {i}, dim {dim}: {f} should be snapped to {k} "
                      f"(diff={abs(f-k):.2e} < {BOUNDARY_FRAC_TOL})")
        
        # Check boundary snapping
        if f < 0.0101 and f != 0.0:
            print(f"  WARNING: Atom {i}, dim {dim}: {f} is near 0 but not snapped to 0.0")
        if f > 0.9899 and f < 1.0:
            print(f"  WARNING: Atom {i}, dim {dim}: {f} is near 1 but not snapped to 0.0")

