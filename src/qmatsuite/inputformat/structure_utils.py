"""Structure conversion utilities for the input format system.

Converts between pymatgen Structure objects and the StructureDoc dict
format used by write_engine_inputs.

StructureDoc dict format:
    {
        "lattice": [[3x3 floats]],   # Angstrom
        "species": ["Si", "Si"],
        "frac_coords": [[Nx3 floats]],
        "comment": "optional string",
    }
"""

from __future__ import annotations

from typing import Any


def structure_to_dict(structure: Any) -> dict[str, Any]:
    """Convert a pymatgen Structure/Molecule to a StructureDoc dict.

    Args:
        structure: A pymatgen Structure or Molecule object, or an object
            with .lattice.matrix, .species, and .frac_coords attributes.

    Returns:
        StructureDoc dict with lattice, species, frac_coords, comment.
    """
    lattice = [list(row) for row in structure.lattice.matrix]
    species = [str(sp) for sp in structure.species]
    frac_coords = [list(fc) for fc in structure.frac_coords]

    comment = ""
    if hasattr(structure, "comment"):
        comment = structure.comment or ""
    elif hasattr(structure, "formula"):
        comment = structure.formula

    return {
        "lattice": lattice,
        "species": species,
        "frac_coords": frac_coords,
        "comment": comment,
    }
