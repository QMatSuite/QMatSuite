"""init_project tool — create a new QMatSuite project directory."""

from __future__ import annotations

from pathlib import Path

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


@mcp.tool
def init_project(
    path: str,
    name: str = "",
) -> dict:
    """Create a new QMatSuite project directory.

    Initialises the project structure (project.qv.yml, standard subdirectories)
    and sets the MCP session to use the new project.

    Args:
        path: Absolute path where the project directory will be created.
        name: Optional human-readable project name (defaults to directory name).
    """
    from quantumvitas.api import QVService

    target = Path(path)

    # Reject if target is inside an existing project
    from quantumvitas.core.project_utils import find_project_root

    existing = find_project_root(start=target if target.exists() else target.parent)
    if existing is not None:
        return make_error(
            "invalid_path",
            f"Path is inside an existing project at {existing}.",
            context_hint="Choose a path outside any existing QMatSuite project.",
        )

    try:
        project_root = QVService.init_project(target, name=name or None)
    except Exception as exc:
        return make_error("init_failed", f"Failed to create project: {exc}")

    # Point MCP session at new project
    from quantumvitas.mcp.project import set_project_root

    set_project_root(project_root)

    return make_response(
        {
            "project_root": str(project_root),
            "name": name or target.name,
        },
        context_hint=(
            "Project created. Use import_structure() to add a structure, "
            "then create_calculation() to start computing."
        ),
    )
