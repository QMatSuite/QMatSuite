"""VASP POSCAR pure text <-> dict mapping.

Maps between StructureDoc dict (SSOT-compatible) and VASP POSCAR text.
Stdlib only — no pymatgen, no qmatsuite core imports.

StructureDoc dict schema::

    {
        "lattice": [[a1x, a1y, a1z], [a2x, a2y, a2z], [a3x, a3y, a3z]],
        "species": ["Si", "O", ...],       # per-atom species labels
        "frac_coords": [[fx, fy, fz], ...], # fractional coordinates
        "comment": "optional title",
    }

Writer always produces Direct (fractional) coordinates.
Parser accepts both Direct and Cartesian (converting Cartesian to fractional).
Comments are stripped. Selective dynamics lines are parsed but not round-tripped
into the SSOT dict (they are a VASP-specific formatting concern).
"""

from __future__ import annotations

import math
from typing import Any


def write_poscar_text(structure: dict[str, Any]) -> str:
    """Write POSCAR text from a StructureDoc dict.

    Args:
        structure: Dict with keys ``lattice``, ``species``, ``frac_coords``,
            and optionally ``comment``.

    Returns:
        POSCAR file content as a string.
    """
    lattice = structure["lattice"]
    species = structure["species"]
    frac_coords = structure["frac_coords"]
    comment = structure.get("comment", "structure")

    # Build species order: unique species in first-occurrence order
    species_order: list[str] = []
    for sp in species:
        if sp not in species_order:
            species_order.append(sp)

    # Count atoms per species and reorder atoms by species
    counts: list[int] = []
    ordered_coords: list[list[float]] = []
    for sp in species_order:
        sp_coords = [
            frac_coords[i] for i, s in enumerate(species) if s == sp
        ]
        counts.append(len(sp_coords))
        ordered_coords.extend(sp_coords)

    lines: list[str] = []
    lines.append(comment)
    lines.append("1.0")

    # Lattice vectors
    for vec in lattice:
        lines.append(f"  {vec[0]:21.16f}  {vec[1]:21.16f}  {vec[2]:21.16f}")

    # Species labels and counts
    lines.append("  ".join(species_order))
    lines.append("  ".join(str(c) for c in counts))

    # Coordinate type
    lines.append("Direct")

    # Atomic positions
    for coord in ordered_coords:
        lines.append(f"  {coord[0]:19.16f}  {coord[1]:19.16f}  {coord[2]:19.16f}")

    return "\n".join(lines) + "\n"


def parse_poscar_text(text: str) -> dict[str, Any]:
    """Parse POSCAR text into a StructureDoc dict.

    Handles VASP 5+ format (species labels on line 6). Accepts both
    Direct (fractional) and Cartesian coordinates — Cartesian are
    converted to fractional via lattice inverse.

    Comments, blank lines, and selective dynamics flags are stripped.
    Unknown content produces no error — the parser is lenient for the
    fields it doesn't use.

    Args:
        text: POSCAR file content.

    Returns:
        Dict with keys ``lattice``, ``species``, ``frac_coords``,
        ``comment``.

    Raises:
        ValueError: If the file is too short or has unparseable structure.
    """
    raw_lines = text.strip().splitlines()
    if len(raw_lines) < 8:
        raise ValueError(
            f"POSCAR too short: {len(raw_lines)} lines (need >= 8)"
        )

    comment = raw_lines[0].strip()
    scale = float(raw_lines[1].strip())

    # Lattice vectors (lines 3-5, 0-indexed 2-4)
    lattice: list[list[float]] = []
    for i in range(2, 5):
        parts = raw_lines[i].split()
        vec = [float(x) * scale for x in parts[:3]]
        lattice.append(vec)

    # Line 6: species labels (VASP 5+) or counts (VASP 4)
    line6_parts = raw_lines[5].split()
    line_idx = 5

    # Detect whether line 6 is species labels or counts
    try:
        int(line6_parts[0])
        # Line 6 is counts — VASP 4 format (no species labels)
        species_labels = [f"Type{i+1}" for i in range(len(line6_parts))]
        counts = [int(x) for x in line6_parts]
        line_idx = 6
    except ValueError:
        # Line 6 is species labels — VASP 5+ format
        species_labels = line6_parts
        line_idx = 6
        count_parts = raw_lines[line_idx].split()
        counts = [int(x) for x in count_parts]
        line_idx = 7

    total_atoms = sum(counts)

    # Optional: Selective dynamics line
    next_line = raw_lines[line_idx].strip()
    if next_line and next_line[0].lower() == "s":
        # Selective dynamics — skip
        line_idx += 1
        next_line = raw_lines[line_idx].strip()

    # Coordinate type
    is_cartesian = next_line[0].lower() in ("c", "k")
    line_idx += 1

    # Read atomic positions
    raw_coords: list[list[float]] = []
    for i in range(total_atoms):
        parts = raw_lines[line_idx + i].split()
        raw_coords.append([float(parts[0]), float(parts[1]), float(parts[2])])

    # Convert Cartesian to fractional if needed
    if is_cartesian:
        # Scale Cartesian coords by the universal scaling factor
        # (already applied to lattice above)
        inv = _invert_3x3(lattice)
        frac_coords = [_mat_vec_mul(inv, c) for c in raw_coords]
    else:
        frac_coords = raw_coords

    # Expand species labels to per-atom list
    species: list[str] = []
    for label, count in zip(species_labels, counts):
        species.extend([label] * count)

    return {
        "lattice": lattice,
        "species": species,
        "frac_coords": frac_coords,
        "comment": comment,
    }


# ---------------------------------------------------------------------------
# Private helpers (3x3 linear algebra, no numpy)
# ---------------------------------------------------------------------------


def _invert_3x3(m: list[list[float]]) -> list[list[float]]:
    """Invert a 3x3 matrix (row-major)."""
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, k = m[2]

    det = a * (e * k - f * h) - b * (d * k - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-30:
        raise ValueError("Singular lattice matrix — cannot invert")

    inv_det = 1.0 / det
    return [
        [
            (e * k - f * h) * inv_det,
            (c * h - b * k) * inv_det,
            (b * f - c * e) * inv_det,
        ],
        [
            (f * g - d * k) * inv_det,
            (a * k - c * g) * inv_det,
            (c * d - a * f) * inv_det,
        ],
        [
            (d * h - e * g) * inv_det,
            (b * g - a * h) * inv_det,
            (a * e - b * d) * inv_det,
        ],
    ]


def _mat_vec_mul(m: list[list[float]], v: list[float]) -> list[float]:
    """Multiply 3x3 matrix by 3-vector."""
    return [
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    ]
