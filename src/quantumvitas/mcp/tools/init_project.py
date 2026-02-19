"""init_project tool — initialise or load a QMatSuite project."""

from __future__ import annotations

import os
from pathlib import Path

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def init_project(name: str = "") -> dict:
    """Initialize or load a QMatSuite project in the current directory.

    Resolves the project directory from the ``QMATSUITE_PROJECT`` environment
    variable (or CWD as fallback).  If a project already exists at or above
    that directory it is loaded (idempotent).  Otherwise a new project is
    created.

    Args:
        name: Optional human-readable project name (defaults to directory name).
    """
    from quantumvitas.core.project_utils import find_project_root
    from quantumvitas.mcp.project import set_project_root

    project_dir = Path(os.environ.get("QMATSUITE_PROJECT", ".")).resolve()

    # Try to find an existing project at or above project_dir
    existing = find_project_root(start=project_dir) if project_dir.exists() else None

    if existing is not None:
        # Load existing project (idempotent)
        set_project_root(existing)
        return make_response(
            {
                "project_root": str(existing),
                "name": name or existing.name,
                "loaded": True,
            },
            context_hint=(
                "Existing project loaded. Use list_structures() to see structures, "
                "or search_demos() to find ready-made calculations."
            ),
        )

    # Create new project
    from quantumvitas.api import QVService

    try:
        project_root = QVService.init_project(project_dir, name=name or None)
    except Exception as exc:
        return make_error("init_failed", f"Failed to create project: {exc}")

    set_project_root(project_root)

    return make_response(
        {
            "project_root": str(project_root),
            "name": name or project_dir.name,
            "loaded": False,
        },
        context_hint=(
            "Project created. Use import_structure() to add a structure, "
            "or search_demos() to find ready-made calculations."
        ),
    )
