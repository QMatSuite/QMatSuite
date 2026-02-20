"""init_project tool — initialise or load a QMatSuite project."""

from __future__ import annotations

import os
from pathlib import Path

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_error, make_response


def _quick_health_check(project_root: Path) -> list[str]:
    """Quick scan for common project integrity issues. Returns warnings."""
    warnings: list[str] = []

    # 1. Can we parse project.qv.yml?
    try:
        from quantumvitas.core.project_utils import load_project_config

        config = load_project_config(project_root)
    except Exception as e:
        warnings.append(f"project.qv.yml is unreadable: {e}")
        return warnings  # Can't check further

    # 2. Check standard directories exist
    for dirname in ("calculations", "structures"):
        d = project_root / dirname
        if not d.exists():
            warnings.append(f"Standard directory '{dirname}/' is missing")

    # 3. Check calculation references → dirs exist
    for entry in config.get("calculations", []):
        meta = entry.get("meta") or {}
        calc_name = (
            entry.get("name")
            or meta.get("name")
            or meta.get("ulid", "")[:8]
            or "unknown"
        )
        calc_path = entry.get("path") or meta.get("path", "")
        if calc_path:
            full = project_root / calc_path
            if not full.exists():
                warnings.append(
                    f"Calculation '{calc_name}' references missing directory: {calc_path}"
                )

    # 4. Check structure references → files exist
    for entry in config.get("structures", []):
        meta = entry.get("meta") or {}
        struct_name = (
            entry.get("name")
            or meta.get("name")
            or meta.get("ulid", "")[:8]
            or "unknown"
        )
        struct_path = entry.get("file") or meta.get("path", "")
        if struct_path:
            full = project_root / struct_path
            if not full.exists():
                warnings.append(
                    f"Structure '{struct_name}' references missing file: {struct_path}"
                )

    # 5. Check resource index for corrupt files
    try:
        from quantumvitas.core.resolution import (
            build_resource_index,
            get_last_index_warnings,
        )

        build_resource_index(project_root)
        warnings.extend(get_last_index_warnings())
    except Exception:
        pass  # Index build itself failing is not fatal

    return warnings


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
        health_warnings = _quick_health_check(existing)
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
            warnings=health_warnings or None,
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
