"""list_calculations tool — list all calculations in the current project."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def list_calculations() -> dict:
    """List all calculations in the current project.

    Returns a compact summary of each calculation including its ULID,
    name, engine, status, step count, and structure ULID. Use
    ``inspect_calculation(calc_ulid=...)`` for full parameter detail.
    """
    from qmatsuite.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    try:
        dtos = svc.calculation.list()
    except Exception as exc:
        return make_error("list_failed", f"Failed to list calculations: {exc}")

    items: list[dict] = []
    for dto in dtos:
        meta = dto.meta
        name = (meta.name if meta else None) or (meta.slug if meta else None) or ""
        items.append({
            "calc_ulid": dto.calc_ulid,
            "name": name,
            "engine": dto.engine,
            "status": dto.status,
            "n_steps": dto.step_count or 0,
            "structure_ulid": dto.structure_ulid,
        })

    if not items:
        hint = (
            "No calculations in this project. Use create_calculation(...) to create one, "
            "or load_demo(...) to load a pre-configured demo."
        )
    else:
        hint = (
            "Use inspect_calculation(calc_ulid='...') for parameter details, "
            "or run_calculation(calc_ulid='...') to execute."
        )

    return make_response(
        {"calculations": items, "total": len(items)},
        context_hint=hint,
    )
