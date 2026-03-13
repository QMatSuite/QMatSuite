"""Structure conversion utilities for the input format system.

Converts between pymatgen Structure/Molecule objects and the StructureDoc dict
format used by write_engine_inputs.

Periodic StructureDoc:
    {
        "lattice": [[3x3 floats]],   # Angstrom
        "species": ["Si", "Si"],
        "frac_coords": [[Nx3 floats]],
        "comment": "optional string",
    }

Molecular StructureDoc:
    {
        "species": ["O", "H", "H"],
        "cart_coords": [[Nx3 floats]],  # Angstrom
        "comment": "optional string",
    }
"""

from __future__ import annotations

from typing import Any


def structure_to_dict(structure: Any) -> dict[str, Any]:
    """Convert a pymatgen Structure/Molecule to a StructureDoc dict.

    Args:
        structure: A pymatgen Structure or Molecule object, or an object
            with either periodic (.lattice.matrix, .species, .frac_coords)
            or molecular (.species, .cart_coords) attributes.

    Returns:
        StructureDoc dict with either lattice/species/frac_coords or
        species/cart_coords plus comment.
    """
    species = [str(sp) for sp in structure.species]

    comment = ""
    if hasattr(structure, "comment"):
        comment = structure.comment or ""
    elif hasattr(structure, "formula"):
        comment = structure.formula

    lattice = getattr(structure, "lattice", None)
    if lattice is not None:
        return {
            "lattice": [list(row) for row in lattice.matrix],
            "species": species,
            "frac_coords": [list(fc) for fc in structure.frac_coords],
            "comment": comment,
        }

    return {
        "species": species,
        "cart_coords": [list(cc) for cc in structure.cart_coords],
        "comment": comment,
    }
