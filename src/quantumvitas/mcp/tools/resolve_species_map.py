"""auto_resolve_species_map tool — automatically resolve pseudopotentials."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def auto_resolve_species_map(
    calc_ulid: str,
    library: str = "sssp",
    variant: str = "precision",
) -> dict:
    """Automatically resolve and set the species_map for a calculation.

    Uses the project's pseudopotential library to find the best matching
    pseudopotentials for each element in the calculation's structure.
    The resolved mapping is immediately applied to the calculation.

    Supported engines: QE, ABINIT, Siesta (pseudo-based engines).
    For VASP, use set_species_map() manually with POTCAR variant names.

    Args:
        calc_ulid: ULID of the target calculation.
        library: Pseudo library to use (default: 'sssp').
        variant: Library variant (default: 'precision').
            Use 'efficiency' for smaller cutoffs.
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # Validate calc exists and get engine info
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception as exc:
        return make_error(
            "not_found",
            f"Calculation '{calc_ulid}' not found: {exc}",
        )

    engine = detail.get("engine_family", "")
    from quantumvitas.mcp.tools._resource_utils import PSEUDO_ENGINES

    if engine not in PSEUDO_ENGINES:
        return make_error(
            "unsupported_engine",
            f"Engine '{engine}' does not use pseudopotentials managed by auto-resolve.",
            context_hint=(
                "For VASP, use set_species_map() with POTCAR variant names. "
                "For molecular codes (ORCA, Gaussian, etc.), no species_map is needed."
            ),
        )

    # Attempt auto-resolution
    from quantumvitas.mcp.tools._resource_utils import auto_resolve_species_map_internal

    resolved = auto_resolve_species_map_internal(calc_ulid, svc, library, variant)

    if resolved is None:
        elements = detail.get("structure_elements", [])
        return make_error(
            "resolution_failed",
            (
                f"Could not auto-resolve pseudopotentials for elements: "
                f"{', '.join(elements) if elements else '(none)'}."
            ),
            context_hint=(
                "Ensure the SSSP pseudo library is installed. "
                "Use download_pseudo_library(variant='precision') to install SSSP. "
                "Internal pseudos are available for: Si, Al, C, H, O, Fe, Cu, Li, He. "
                f"Or use set_species_map(calc_ulid='{calc_ulid}', ...) to set manually."
            ),
        )

    # Apply resolved map
    try:
        svc.calculation.update_species_map(calc_ulid, resolved)
    except Exception as exc:
        return make_error(
            "update_failed",
            f"Resolved pseudopotentials but failed to set species_map: {exc}",
        )

    return make_response(
        {
            "calc_ulid": calc_ulid,
            "species_map": resolved,
            "library": library,
            "variant": variant,
        },
        context_hint=(
            f"Species map auto-resolved and applied. "
            f"Use inspect_calculation(calc_ulid='{calc_ulid}') to review, "
            f"then run_calculation(calc_ulid='{calc_ulid}') to execute."
        ),
    )
