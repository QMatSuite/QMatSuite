"""set_parameters tool — update step parameters on a calculation."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response

# QE card keys that should be routed to the ``cards`` namespace, not ``parameters``.
_QE_CARD_KEYS = frozenset({
    "K_POINTS", "ATOMIC_SPECIES", "ATOMIC_POSITIONS",
    "CELL_PARAMETERS", "CONSTRAINTS", "OCCUPATIONS", "ATOMIC_FORCES",
})


@mcp.tool
def set_parameters(calc_ulid: str, params: dict, step: int = 0) -> dict:
    """Set engine-native parameters on a calculation step.

    Parameters are written into the step's ``parameters`` namespace in the
    step YAML.  For QE this means namelist keys like
    ``{"SYSTEM": {"ecutwfc": 40}}``.  For VASP: ``{"INCAR": {"ENCUT": 520}}``.

    QE card keys (K_POINTS, ATOMIC_SPECIES, etc.) are auto-routed to the
    ``cards`` namespace.  You can also use explicit namespaces::

        {"cards": {"K_POINTS": {...}}, "parameters": {"SYSTEM": {...}}}

    Args:
        calc_ulid: ULID of the target calculation.
        params: Engine-native parameter dict to merge into the step.
        step: Zero-based step index within the workflow (default 0).
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- resolve step ULID from index ---
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception as exc:
        return make_error(
            "not_found",
            f"Calculation '{calc_ulid}' not found: {exc}",
        )

    steps = detail.get("steps", [])
    if step < 0 or step >= len(steps):
        return make_error(
            "invalid_step_index",
            f"Step index {step} out of range (calculation has {len(steps)} step(s)).",
            context_hint=f"Valid step indices: 0..{len(steps) - 1}." if steps else None,
        )

    step_ulid = steps[step].get("step_ulid") or steps[step].get("ulid", "")

    # --- classify top-level keys into parameters vs cards ---
    params_dict: dict = {}
    cards_dict: dict = {}
    for key, value in params.items():
        if key == "cards":
            cards_dict.update(value)       # explicit cards namespace
        elif key == "parameters":
            params_dict.update(value)      # explicit parameters namespace
        elif key in _QE_CARD_KEYS:
            cards_dict[key] = value        # auto-route to cards
        else:
            params_dict[key] = value       # default to parameters (covers namelists + non-QE)

    patch: dict = {}
    if params_dict:
        patch["parameters"] = params_dict
    if cards_dict:
        patch["cards"] = cards_dict
    if not patch:
        patch = {"parameters": params}    # backward compat: empty dict → parameters

    # --- apply parameters ---
    try:
        svc.calculation.update_step_params(
            calc_selector=calc_ulid,
            step_selector=step_ulid,
            params=patch,
        )
    except Exception as exc:
        return make_error("update_failed", str(exc))

    return make_response(
        {
            "calc_ulid": calc_ulid,
            "step": step,
            "step_ulid": step_ulid,
            "params_set": params,
        },
        context_hint=(
            f"Use inspect_calculation(calc_ulid='{calc_ulid}') to review, "
            f"or run_calculation(calc_ulid='{calc_ulid}') to execute."
        ),
    )
