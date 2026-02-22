"""LAMMPS data file parser and writer.

Pure stdlib module — no kernel imports. Handles LAMMPS data file format
with support for atomic/charge/full atom styles and triclinic tilt factors.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Data file parser
# ---------------------------------------------------------------------------

def parse_lammps_data_text(text: str) -> dict[str, Any]:
    """Parse LAMMPS data file text into a structure dict.

    Returns a StructureDoc-compatible dict with:
      lattice, species, frac_coords, cart_coords, comment,
      _masses, _n_types, _n_atoms
    """
    if not text or not text.strip():
        return {}

    lines = text.splitlines()
    comment = ""
    n_atoms = 0
    n_types = 0
    xlo, xhi = 0.0, 0.0
    ylo, yhi = 0.0, 0.0
    zlo, zhi = 0.0, 0.0
    xy, xz, yz = 0.0, 0.0, 0.0
    has_tilt = False
    masses: dict[int, float] = {}
    atoms_raw: list[list[str]] = []

    # Track current section
    section = "header"
    i = 0

    # First non-blank non-comment line is the comment/title
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            comment = stripped
            break
        if stripped.startswith("#"):
            comment = stripped.lstrip("# ")
            break

    while i < len(lines):
        line = lines[i].strip()

        # Empty line or comment in header
        if not line:
            i += 1
            continue

        # --- Header parsing ---
        if section == "header":
            # N atoms
            m = re.match(r"(\d+)\s+atoms\b", line)
            if m:
                n_atoms = int(m.group(1))
                i += 1
                continue
            # N atom types
            m = re.match(r"(\d+)\s+atom types\b", line)
            if m:
                n_types = int(m.group(1))
                i += 1
                continue
            # xlo xhi
            m = re.match(
                r"([\d.eE+-]+)\s+([\d.eE+-]+)\s+xlo\s+xhi", line
            )
            if m:
                xlo, xhi = float(m.group(1)), float(m.group(2))
                i += 1
                continue
            # ylo yhi
            m = re.match(
                r"([\d.eE+-]+)\s+([\d.eE+-]+)\s+ylo\s+yhi", line
            )
            if m:
                ylo, yhi = float(m.group(1)), float(m.group(2))
                i += 1
                continue
            # zlo zhi
            m = re.match(
                r"([\d.eE+-]+)\s+([\d.eE+-]+)\s+zlo\s+zhi", line
            )
            if m:
                zlo, zhi = float(m.group(1)), float(m.group(2))
                i += 1
                continue
            # xy xz yz tilt factors
            m = re.match(
                r"([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+xy\s+xz\s+yz",
                line,
            )
            if m:
                xy = float(m.group(1))
                xz = float(m.group(2))
                yz = float(m.group(3))
                has_tilt = True
                i += 1
                continue

        # --- Section headers ---
        if line == "Masses":
            section = "masses"
            i += 1
            continue
        if line.startswith("Atoms"):
            section = "atoms"
            i += 1
            continue
        # Other sections we skip
        if line in (
            "Velocities", "Bonds", "Angles", "Dihedrals", "Impropers",
            "Pair Coeffs", "Bond Coeffs", "Angle Coeffs",
            "Dihedral Coeffs", "Improper Coeffs",
        ):
            section = "skip"
            i += 1
            continue

        # --- Masses section ---
        if section == "masses":
            parts = line.split()
            if len(parts) >= 2:
                try:
                    type_id = int(parts[0])
                    mass_val = float(parts[1])
                    masses[type_id] = mass_val
                except ValueError:
                    # Not a mass line; must be a new section header
                    section = "header"
                    continue
            i += 1
            continue

        # --- Atoms section ---
        if section == "atoms":
            # Skip comment lines within Atoms
            if line.startswith("#"):
                i += 1
                continue
            parts = line.split()
            if len(parts) >= 5:
                try:
                    int(parts[0])  # atom ID check
                    atoms_raw.append(parts)
                except ValueError:
                    # New section header
                    section = "header"
                    continue
            i += 1
            continue

        # --- Skip section ---
        if section == "skip":
            parts = line.split()
            if parts:
                try:
                    int(parts[0])
                    i += 1
                    continue
                except ValueError:
                    section = "header"
                    continue

        i += 1

    # Build lattice from box bounds
    lx = xhi - xlo
    ly = yhi - ylo
    lz = zhi - zlo
    if has_tilt:
        lattice = [[lx, 0.0, 0.0], [xy, ly, 0.0], [xz, yz, lz]]
    else:
        lattice = [[lx, 0.0, 0.0], [0.0, ly, 0.0], [0.0, 0.0, lz]]

    # Parse atom coordinates
    species: list[str] = []
    cart_coords: list[list[float]] = []

    for parts in atoms_raw:
        ncols = len(parts)
        if ncols >= 5:
            # Determine format: atomic (5), charge (6), full (7+)
            if ncols == 5:
                # id type x y z
                type_id = parts[1]
                x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
            elif ncols == 6:
                # id type q x y z
                type_id = parts[1]
                x, y, z = float(parts[3]), float(parts[4]), float(parts[5])
            else:
                # id mol type q x y z (full style, 7+ cols)
                type_id = parts[2]
                x, y, z = float(parts[4]), float(parts[5]), float(parts[6])
            species.append(type_id)
            cart_coords.append([x, y, z])

    # Compute fractional coordinates (Cartesian -> fractional via lattice inverse)
    frac_coords: list[list[float]] = []
    if lattice and cart_coords:
        frac_coords = cart_to_frac(cart_coords, lattice)

    result: dict[str, Any] = {
        "comment": comment,
    }
    if lattice and any(v != 0 for row in lattice for v in row):
        result["lattice"] = lattice
    if species:
        result["species"] = species
    if frac_coords:
        result["frac_coords"] = frac_coords
    if cart_coords:
        result["cart_coords"] = cart_coords
    if masses:
        result["_masses"] = masses
    if n_types:
        result["_n_types"] = n_types

    return result


def cart_to_frac(
    cart_coords: list[list[float]], lattice: list[list[float]]
) -> list[list[float]]:
    """Convert Cartesian to fractional coordinates via 3x3 lattice inverse."""
    # Lattice matrix L where rows are lattice vectors
    a = lattice[0]
    b = lattice[1]
    c = lattice[2]

    # Determinant
    det = (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )
    if abs(det) < 1e-30:
        return [[0.0, 0.0, 0.0]] * len(cart_coords)

    inv_det = 1.0 / det

    # Inverse matrix (transposed cofactors / det)
    inv = [
        [
            (b[1] * c[2] - b[2] * c[1]) * inv_det,
            (a[2] * c[1] - a[1] * c[2]) * inv_det,
            (a[1] * b[2] - a[2] * b[1]) * inv_det,
        ],
        [
            (b[2] * c[0] - b[0] * c[2]) * inv_det,
            (a[0] * c[2] - a[2] * c[0]) * inv_det,
            (a[2] * b[0] - a[0] * b[2]) * inv_det,
        ],
        [
            (b[0] * c[1] - b[1] * c[0]) * inv_det,
            (a[1] * c[0] - a[0] * c[1]) * inv_det,
            (a[0] * b[1] - a[1] * b[0]) * inv_det,
        ],
    ]

    fracs = []
    for xyz in cart_coords:
        fx = inv[0][0] * xyz[0] + inv[0][1] * xyz[1] + inv[0][2] * xyz[2]
        fy = inv[1][0] * xyz[0] + inv[1][1] * xyz[1] + inv[1][2] * xyz[2]
        fz = inv[2][0] * xyz[0] + inv[2][1] * xyz[1] + inv[2][2] * xyz[2]
        fracs.append([fx, fy, fz])

    return fracs


# ---------------------------------------------------------------------------
# Data file writer
# ---------------------------------------------------------------------------

def write_lammps_data_text(structure: dict[str, Any] | None) -> str:
    """Write LAMMPS data file text from structure dict.

    Generates a basic LAMMPS data file in 'atomic' style.
    """
    if not structure:
        return ""

    species = structure.get("species", [])
    frac_coords = structure.get("frac_coords", [])
    cart_coords = structure.get("cart_coords", [])
    lattice = structure.get("lattice", [])
    comment = structure.get("comment", "LAMMPS data file")

    unique_species: list[str] = []
    for sp in species:
        if sp not in unique_species:
            unique_species.append(sp)

    n_atoms = len(species)
    n_types = len(unique_species)

    lines: list[str] = []
    lines.append(f"# {comment}")
    lines.append("")
    lines.append(f"{n_atoms} atoms")
    lines.append(f"{n_types} atom types")
    lines.append("")

    # Box bounds
    if lattice:
        ax = lattice[0][0]
        by = lattice[1][1]
        cz = lattice[2][2]
        bx = lattice[1][0]
        cx = lattice[2][0]
        cy = lattice[2][1]
        lines.append(f"0.0 {ax:.10f} xlo xhi")
        lines.append(f"0.0 {by:.10f} ylo yhi")
        lines.append(f"0.0 {cz:.10f} zlo zhi")
        if abs(bx) > 1e-10 or abs(cx) > 1e-10 or abs(cy) > 1e-10:
            lines.append(f"{bx:.10f} {cx:.10f} {cy:.10f} xy xz yz")
    lines.append("")

    # Masses (if available)
    mass_map = structure.get("_masses", {})
    if mass_map:
        lines.append("Masses")
        lines.append("")
        for tid in sorted(mass_map.keys()):
            lines.append(f"{tid} {mass_map[tid]}")
        lines.append("")

    # Atoms section (atomic style: id type x y z)
    lines.append("Atoms")
    lines.append("")

    # Prefer cart_coords if available; otherwise convert from frac_coords
    if cart_coords:
        for i, (sym, cc) in enumerate(zip(species, cart_coords), 1):
            type_id = unique_species.index(sym) + 1
            lines.append(
                f"{i} {type_id} {cc[0]:.10f} {cc[1]:.10f} {cc[2]:.10f}"
            )
    elif frac_coords and lattice:
        for i, (sym, fc) in enumerate(zip(species, frac_coords), 1):
            type_id = unique_species.index(sym) + 1
            x = (
                fc[0] * lattice[0][0]
                + fc[1] * lattice[1][0]
                + fc[2] * lattice[2][0]
            )
            y = (
                fc[0] * lattice[0][1]
                + fc[1] * lattice[1][1]
                + fc[2] * lattice[2][1]
            )
            z = (
                fc[0] * lattice[0][2]
                + fc[1] * lattice[1][2]
                + fc[2] * lattice[2][2]
            )
            lines.append(f"{i} {type_id} {x:.10f} {y:.10f} {z:.10f}")

    return "\n".join(lines) + "\n"
