"""Siesta FDF input writer (driver-facing compatibility wrapper)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qmatsuite.drivers.siesta.io.fdf import write_fdf_text


def _to_lattice_ang(lattice_constant: float, lattice_vectors: list[list[float]]) -> list[list[float]]:
    return [
        [float(lattice_constant) * float(v[0]), float(lattice_constant) * float(v[1]), float(lattice_constant) * float(v[2])]
        for v in lattice_vectors
    ]


def write_fdf(
    output_path: Path,
    system_name: str,
    system_label: str,
    species: list[dict[str, Any]],
    lattice_constant: float,
    lattice_vectors: list[list[float]],
    atoms: list[dict[str, Any]],
    coord_format: str = "Ang",
    params: dict[str, Any] | None = None,
) -> str:
    """Write a Siesta FDF input file from legacy handler arguments.

    This wrapper preserves the historic ``write_fdf(...)`` API while delegating
    rendering to ``drivers/siesta/io/fdf.py``.
    """
    p = dict(params or {})

    # Convert species/atoms records into StructureDoc-like representation.
    species_by_idx: dict[int, str] = {}
    znucl: dict[str, int] = {}
    for rec in species:
        idx = int(rec.get("index", 0))
        label = str(rec.get("label", f"Type{idx}"))
        z = int(rec.get("atomic_number", 0))
        species_by_idx[idx] = label
        znucl[label] = z

    struct_species: list[str] = []
    coords: list[list[float]] = []
    for atom in atoms:
        sp_idx = int(atom.get("species_index", 1))
        struct_species.append(species_by_idx.get(sp_idx, f"Type{sp_idx}"))
        coords.append([float(atom.get("x", 0.0)), float(atom.get("y", 0.0)), float(atom.get("z", 0.0))])

    structure: dict[str, Any] = {
        "species": struct_species,
        "lattice": _to_lattice_ang(lattice_constant, lattice_vectors),
    }

    fmt = coord_format.strip().lower()
    if fmt in {"fractional", "scaledcartesian", "scaled"}:
        structure["frac_coords"] = coords
    else:
        structure["cart_coords"] = coords

    merged_params = {
        "system_name": system_name,
        "system_label": system_label,
        # Keep the original lattice scaling so ScaledCartesian coordinates
        # preserve their physical meaning in the emitted FDF.
        "LatticeConstant": f"{float(lattice_constant):.12g} Ang",
        "AtomicCoordinatesFormat": coord_format,
        "znucl": znucl,
    }
    merged_params.update(p)

    text = write_fdf_text({"params": merged_params, "structure": structure})
    output_path.write_text(text)
    return text


__all__ = ["write_fdf"]
