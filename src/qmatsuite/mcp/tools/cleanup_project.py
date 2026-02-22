"""cleanup_project tool — remove orphaned references from a project."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def cleanup_project(dry_run: bool = True) -> dict:
    """Remove orphaned references from the project.

    Scans project.qms.yml for calculation and structure entries whose
    directories/files no longer exist on disk.  With ``dry_run=True``
    (default), only reports what would be cleaned.  With ``dry_run=False``,
    removes orphaned entries and saves the updated config.

    Args:
        dry_run: If True (default), only report orphans without removing them.
    """
    from qmatsuite.mcp.project import ProjectNotFoundError, get_service

    try:
        svc = get_service()
    except ProjectNotFoundError as exc:
        return make_error("no_project", str(exc))

    project_root = svc.project_root

    try:
        from qmatsuite.core.project_utils import (
            load_project_config,
            save_project_config,
        )

        config = load_project_config(project_root)
    except Exception as exc:
        return make_error("config_error", f"Cannot load project config: {exc}")

    orphaned_calcs: list[dict] = []
    orphaned_structs: list[dict] = []

    # Check calculations
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
                orphaned_calcs.append({
                    "name": calc_name,
                    "path": calc_path,
                    "ulid": meta.get("ulid", ""),
                })

    # Check structures
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
                orphaned_structs.append({
                    "name": struct_name,
                    "path": struct_path,
                    "ulid": meta.get("ulid", ""),
                })

    total_orphans = len(orphaned_calcs) + len(orphaned_structs)

    if total_orphans == 0:
        return make_response(
            {
                "orphaned_calculations": [],
                "orphaned_structures": [],
                "total_orphans": 0,
                "cleaned": False,
            },
            context_hint="No orphaned references found. Project is clean.",
        )

    if dry_run:
        return make_response(
            {
                "orphaned_calculations": orphaned_calcs,
                "orphaned_structures": orphaned_structs,
                "total_orphans": total_orphans,
                "cleaned": False,
            },
            context_hint=(
                f"Found {total_orphans} orphaned reference(s). "
                "Run cleanup_project(dry_run=False) to remove them."
            ),
        )

    # Remove orphaned entries
    orphan_calc_paths = {o["path"] for o in orphaned_calcs}
    orphan_struct_paths = {o["path"] for o in orphaned_structs}

    config["calculations"] = [
        e
        for e in config.get("calculations", [])
        if (e.get("path") or (e.get("meta") or {}).get("path", ""))
        not in orphan_calc_paths
    ]
    config["structures"] = [
        e
        for e in config.get("structures", [])
        if (e.get("file") or (e.get("meta") or {}).get("path", ""))
        not in orphan_struct_paths
    ]

    try:
        save_project_config(project_root, config)
    except Exception as exc:
        return make_error(
            "save_failed",
            f"Failed to save cleaned config: {exc}",
        )

    return make_response(
        {
            "orphaned_calculations": orphaned_calcs,
            "orphaned_structures": orphaned_structs,
            "total_orphans": total_orphans,
            "cleaned": True,
        },
        context_hint=(
            f"Removed {total_orphans} orphaned reference(s) from project.qms.yml."
        ),
    )
