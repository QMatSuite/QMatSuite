"""set_species_map tool — set pseudopotential mapping for a calculation."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def set_species_map(
    calc_ulid: str,
    species_map: dict,
) -> dict:
    """Set the species-to-pseudopotential mapping for a calculation.

    Required before running QE, ABINIT, Siesta, or VASP calculations.

    Example species_map::

        {"Si": {"pseudopot": "Si.pbe-n-rrkjus_psl.1.0.0.UPF"}}

    Args:
        calc_ulid: Calculation ULID returned by create_calculation.
        species_map: Mapping of element symbol to pseudopotential config.
            Each entry MUST have at least a ``pseudopot`` key.
    """
    # --- validate species_map ---
    if not species_map:
        return make_error(
            "invalid_species_map",
            "species_map must be a non-empty dict.",
            context_hint="Provide a mapping like {\"Si\": {\"pseudopot\": \"Si.UPF\"}}.",
        )

    for element, cfg in species_map.items():
        if not isinstance(cfg, dict) or "pseudopot" not in cfg:
            return make_error(
                "invalid_species_map",
                f"Entry for '{element}' must be a dict with a 'pseudopot' key. Got: {cfg}",
                context_hint="Each species entry needs at least {\"pseudopot\": \"filename\"}.",
            )

    # --- get service ---
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- update species_map ---
    try:
        result = svc.calculation.update_species_map(calc_ulid, species_map)
    except Exception as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            return make_error(
                "calc_not_found",
                f"Calculation '{calc_ulid}' not found: {msg}",
            )
        return make_error("update_failed", f"Failed to set species_map: {msg}")

    old_map = result.get("old_species_map", {}) if isinstance(result, dict) else {}
    return make_response(
        {
            "calc_ulid": calc_ulid,
            "species_map": species_map,
            "old_species_map": old_map,
        },
        context_hint=(
            f"Species map set. Use inspect_calculation(calc_ulid='{calc_ulid}') "
            "to review, then run_calculation() or apply_preset() to continue."
        ),
    )
