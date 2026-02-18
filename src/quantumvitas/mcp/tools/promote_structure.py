"""promote_structure tool — extract relaxed structure and register as project-level."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response

# Step type gens that produce relaxed structures.
_RELAX_GEN_TYPES = frozenset({"relax"})


@mcp.tool
def promote_structure(
    calc_ulid: str,
    step_index: int = -1,
    name: str = "",
) -> dict:
    """Extract a relaxed structure from a completed calculation step and register it as a project-level structure.

    The promoted structure can then be used as input for downstream
    calculations (e.g. band structure, DOS on the relaxed geometry).

    Args:
        calc_ulid: ULID of the calculation containing a relax step.
        step_index: Zero-based index of the relax step (-1 = auto-detect last relax step).
        name: Optional human-readable name for the new structure.
    """
    from quantumvitas.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    # --- get calculation detail ---
    try:
        detail = svc.calculation.get_detail(calc_ulid)
    except Exception as exc:
        return make_error(
            "not_found",
            f"Calculation '{calc_ulid}' not found: {exc}",
        )

    steps = detail.get("steps", [])
    if not steps:
        return make_error(
            "no_steps",
            "Calculation has no steps.",
        )

    # --- resolve step index ---
    if step_index == -1:
        # Auto-detect: find last relax step
        found_idx = None
        for idx, s in enumerate(steps):
            gen = s.get("step_type_gen", "")
            if gen in _RELAX_GEN_TYPES:
                found_idx = idx
        if found_idx is None:
            gen_types = [s.get("step_type_gen", "?") for s in steps]
            return make_error(
                "no_relax_step",
                f"No relax step found in this calculation. "
                f"Steps: {gen_types}. "
                f"promote_structure requires a relax/vc-relax step.",
                context_hint=(
                    "Create a calculation with workflow='relax' and run it first."
                ),
            )
        step_index = found_idx

    if step_index < 0 or step_index >= len(steps):
        return make_error(
            "invalid_step_index",
            f"Step index {step_index} out of range (calculation has {len(steps)} step(s)).",
        )

    target_step = steps[step_index]
    step_ulid = target_step.get("step_ulid") or target_step.get("ulid", "")
    step_gen = target_step.get("step_type_gen", "")

    if step_gen not in _RELAX_GEN_TYPES:
        return make_error(
            "not_relax_step",
            f"Step {step_index} is '{step_gen}', not a relax step. "
            f"promote_structure only works on relax steps.",
        )

    # --- get parent structure ULID ---
    parent_structure_ulid = detail.get("structure_ulid", "")
    if not parent_structure_ulid:
        return make_error(
            "no_structure",
            "Calculation has no associated structure.",
        )

    # --- call save_relax_final_structure ---
    slug_hint = name if name else None
    try:
        result = svc.structure.save_relax_final_structure(
            calculation_selector=calc_ulid,
            step_selector=step_ulid,
            parent_structure_ulid=parent_structure_ulid,
            slug_hint=slug_hint,
        )
    except ValueError as exc:
        return make_error(
            "not_relax_step",
            str(exc),
            context_hint="Only completed relax/vc-relax steps can be promoted.",
        )
    except FileNotFoundError as exc:
        return make_error(
            "no_output",
            str(exc),
            context_hint=(
                f"Run the calculation first: run_calculation(calc_ulid='{calc_ulid}')."
            ),
        )
    except Exception as exc:
        return make_error(
            "promote_failed",
            f"Failed to promote structure: {exc}",
        )

    structure_ulid = result["structure_ulid"]
    already_exists = result.get("already_exists", False)

    # --- build response with structure info ---
    payload: dict = {
        "structure_ulid": structure_ulid,
        "already_exists": already_exists,
        "source_calc_ulid": calc_ulid,
        "source_step_index": step_index,
        "source_step_ulid": step_ulid,
    }

    # Try to get structure metadata
    try:
        dto = svc.structure.get(structure_ulid)
        payload["name"] = dto.name
        payload["formula"] = dto.formula
        payload["n_atoms"] = dto.num_atoms
    except Exception:
        payload["name"] = name or "relaxed"

    hint_parts = [
        f"Structure promoted (ULID: {structure_ulid}).",
    ]
    if already_exists:
        hint_parts.append("This structure was already promoted (idempotent).")
    hint_parts.append(
        f"Use create_calculation(structure_selector='{structure_ulid}', "
        f"engine='...', workflow='...') to start a new calculation."
    )

    return make_response(
        payload,
        context_hint=" ".join(hint_parts),
    )
