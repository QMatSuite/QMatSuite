"""generate_kpath tool — generate high-symmetry k-path for band structure."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def generate_kpath(
    structure_selector: str,
    points_per_segment: int = 20,
    path_type: str = "hinuma",
) -> dict:
    """Generate a high-symmetry k-path for band structure calculations.

    Uses pymatgen's symmetry analysis to automatically determine the Brillouin
    zone path.  Returns the path in QE ``K_POINTS {crystal_b}`` format ready
    to be applied via ``set_parameters``.

    Args:
        structure_selector: Name or ULID of an already-imported structure.
        points_per_segment: Number of k-points per path segment (default 20).
        path_type: Path convention — ``"hinuma"`` (default) or
            ``"setyawan_curtarolo"``.
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # Resolve structure selector → pymatgen Structure
    try:
        from quantumvitas.core.resolution import require_structure
        from quantumvitas.io.structure_io import read_structure

        struct_resolved = require_structure(svc.project_root, structure_selector)
        pmg_structure = read_structure(struct_resolved.absolute_path)
    except Exception as exc:
        return make_error(
            "structure_error",
            f"Could not resolve structure '{structure_selector}': {exc}",
        )

    # Generate k-path
    try:
        from quantumvitas.analysis.kpath import generate_kpath as _generate_kpath

        kpath_result = _generate_kpath(
            pmg_structure,
            points_per_segment=points_per_segment,
            path_type=path_type,
        )
    except Exception as exc:
        return make_error("kpath_error", f"K-path generation failed: {exc}")

    kpoints_card = kpath_result.to_qe_kpoints_crystal_b()

    return make_response(
        {
            "lattice_type": kpath_result.lattice_type,
            "spacegroup_symbol": kpath_result.spacegroup_symbol,
            "spacegroup_number": kpath_result.spacegroup_number,
            "path_string": kpath_result.path_string(),
            "path_type": path_type,
            "n_kpoints": len(kpoints_card["data"]),
            "n_segments": len(kpath_result.segments),
            "kpoints_card": kpoints_card,
            "labels": kpath_result.labels,
            "coords": [list(c) for c in kpath_result.coords],
        },
        context_hint=(
            "Use set_parameters(..., params={'K_POINTS': data['kpoints_card']}) "
            "to apply this k-path to a bands calculation step."
        ),
    )
