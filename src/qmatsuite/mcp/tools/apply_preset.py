"""apply_preset tool — broadcast quality presets to a calculation."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


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
    from qmatsuite.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # Translate profile names (NM, COL, …) to enum values (nonmagnetic, …)
    # so the compiler's _normalize_option() can resolve them.
    from qmatsuite.presets.variants_registry import PROFILE_TO_ENUM

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

    steps_updated = result.get("steps_updated", 0)
    step_results = result.get("step_results", [])

    payload = {
        "calc_ulid": calc_ulid,
        "presets_applied": presets,
        "status": result.get("status", "applied"),
        "steps_updated": steps_updated,
        "steps_skipped": result.get("steps_skipped", 0),
        "step_results": step_results,
        "dimension_states": result.get("dimension_states", {}),
    }

    # If no steps were updated and there are actual errors (not just skips),
    # report as error. Skipped non-receiver steps are normal for some dimensions.
    if steps_updated == 0:
        has_errors = any(
            sr.get("status") == "error" for sr in step_results
        )
        if has_errors:
            return make_error(
                "preset_partial_failure",
                f"Presets were not applied to any step. "
                f"{len(step_results)} step(s) processed, 0 updated.",
                context_hint=(
                    f"Check that the preset dimensions are valid for this engine. "
                    f"Use get_presets(engine='...', workflow='...') to see available options."
                ),
                diagnostics=[{"step_results": step_results}],
            )

    warnings = None
    if steps_updated == 0:
        warnings = [
            "No steps were updated by these presets. "
            "The preset dimensions may not apply to this step type."
        ]

    return make_response(
        payload,
        context_hint=(
            f"Use set_parameters(calc_ulid='{calc_ulid}', params=...) to override specific values, "
            f"or inspect_calculation(calc_ulid='{calc_ulid}') to review."
        ),
        warnings=warnings,
    )
