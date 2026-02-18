"""get_structure_detail tool — full atomic data for a structure."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response

_MAX_SITES = 50


@mcp.tool
def get_structure_detail(structure_ulid: str) -> dict:
    """Get detailed structure information including atomic positions.

    Combines summary metadata (lattice parameters, space group, volume)
    with full atomic data (species, fractional and Cartesian coordinates).

    For large structures (>50 atoms) the sites list is truncated.

    Args:
        structure_ulid: ULID of the structure to inspect.
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- get DTO for summary fields ---
    try:
        dto = svc.structure.get(structure_ulid)
    except Exception as exc:
        return make_error(
            "not_found",
            f"Structure '{structure_ulid}' not found: {exc}",
        )

    # --- get atoms for full coordinate data ---
    try:
        atoms = svc.structure.get_atoms(structure_ulid)
    except Exception as exc:
        return make_error(
            "atoms_failed",
            f"Failed to load atomic data: {exc}",
        )

    # Build sites list: combine species + positions
    species = atoms.get("species", [])
    positions = atoms.get("positions", [])  # Cartesian, Angstrom
    lattice_matrix = atoms.get("lattice")   # 3x3 or None

    sites: list[dict] = []
    for i, (sp, cart) in enumerate(zip(species, positions)):
        site: dict = {
            "index": i,
            "species": sp,
            "cart_coords": [round(c, 6) for c in cart],
        }
        sites.append(site)

    truncated = False
    if len(sites) > _MAX_SITES:
        sites = sites[:_MAX_SITES]
        truncated = True

    warnings: list[str] = []
    if truncated:
        warnings.append(
            f"Sites truncated to {_MAX_SITES} of {dto.num_atoms} atoms. "
            "Use get_atoms() API for full data."
        )

    data: dict = {
        "structure_ulid": dto.structure_ulid,
        "name": dto.name,
        "formula": dto.formula,
        "n_atoms": dto.num_atoms,
        "space_group": dto.space_group,
        "point_group": dto.point_group,
        "cell_volume_ang3": dto.cell_volume_ang3,
        "lattice_parameters": {
            "a": dto.lattice_abc[0] if dto.lattice_abc else None,
            "b": dto.lattice_abc[1] if dto.lattice_abc else None,
            "c": dto.lattice_abc[2] if dto.lattice_abc else None,
            "alpha": dto.lattice_angles[0] if dto.lattice_angles else None,
            "beta": dto.lattice_angles[1] if dto.lattice_angles else None,
            "gamma": dto.lattice_angles[2] if dto.lattice_angles else None,
        },
        "lattice_vectors": lattice_matrix,
        "species": species,
        "sites": sites,
        "sites_truncated": truncated,
    }

    ulid = dto.structure_ulid
    return make_response(
        data,
        context_hint=(
            f"Use create_calculation(structure_ulid='{ulid}', "
            f"engine='...', workflow='...') to start a calculation."
        ),
        warnings=warnings or None,
    )
