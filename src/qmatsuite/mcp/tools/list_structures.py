"""list_structures tool — list all structures in the current project."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def list_structures() -> dict:
    """List all structures available in the current project.

    Returns a compact summary of each structure including its ULID,
    name, formula, atom count, and space group.  Use
    ``get_structure_detail(structure_ulid=...)`` for full atomic data.
    """
    from qmatsuite.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    try:
        dtos = svc.structure.list()
    except Exception as exc:
        return make_error("list_failed", f"Failed to list structures: {exc}")

    items: list[dict] = []
    for dto in dtos:
        items.append({
            "structure_ulid": dto.structure_ulid,
            "name": dto.name,
            "formula": dto.formula,
            "n_atoms": dto.num_atoms,
            "space_group": dto.space_group,
        })

    if not items:
        hint = "No structures in this project. Use import_structure(...) to add one."
    else:
        hint = (
            "Use get_structure_detail(structure_ulid='...') for full data, "
            "or create_calculation(structure_ulid='...', engine='...', workflow='...') "
            "to start a calculation."
        )

    return make_response(
        {"structures": items, "total": len(items)},
        context_hint=hint,
    )
