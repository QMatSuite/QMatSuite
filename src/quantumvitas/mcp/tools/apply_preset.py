"""apply_preset tool — broadcast quality presets to a calculation."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def apply_preset(calc_ulid: str, presets: dict) -> dict:
    """Apply quality presets (magnetism, precision, etc.) to a calculation.

    Presets are broadcast to every step in the calculation.  Dimension keys
    follow the get_presets output, e.g.
    ``{"magnetism": "NM", "precision": "MED"}``.

    Args:
        calc_ulid: ULID of the target calculation.
        presets: Dict of dimension → selected option value.
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # Translate profile names (NM, COL, …) to enum values (nonmagnetic, …)
    # so the compiler's _normalize_option() can resolve them.
    from quantumvitas.presets.variants_registry import PROFILE_TO_ENUM

    normalized: dict = {}
    for dim, value in presets.items():
        mapping = PROFILE_TO_ENUM.get(dim, {})
        if value in mapping:
            normalized[dim] = mapping[value].value  # enum → string value
        else:
            normalized[dim] = value  # pass through (may be enum value already)

    try:
        result = svc.calculation.apply_presets(calc_ulid, normalized)
    except Exception as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            return make_error("not_found", f"Calculation '{calc_ulid}' not found: {msg}")
        return make_error("preset_failed", msg)

    return make_response(
        {
            "calc_ulid": calc_ulid,
            "presets_applied": presets,
            "status": result.get("status", "applied"),
            "steps_updated": result.get("steps_updated", 0),
            "steps_skipped": result.get("steps_skipped", 0),
            "step_results": result.get("step_results", []),
            "dimension_states": result.get("dimension_states", {}),
        },
        context_hint=(
            f"Use set_parameters(calc_ulid='{calc_ulid}', params=...) to override specific values, "
            f"or inspect_calculation(calc_ulid='{calc_ulid}') to review."
        ),
    )
