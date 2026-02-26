"""uninstall_engine tool — remove an engine installation."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def uninstall_engine(engine: str, installation_id: str = "") -> dict:
    """Uninstall an engine installation.

    If installation_id is empty, the currently active installation is removed.

    Args:
        engine: Engine family key (e.g. 'xtb', 'qe').
        installation_id: Specific installation ID to remove. Empty means active installation.
    """
    from qmatsuite.core.engines.engine_meta import ENGINE_META

    family = (engine or "").strip().lower()
    if family not in ENGINE_META:
        return make_error(
            "unknown_engine",
            f"Unknown engine '{engine}'. Use list_engines() to see available engines.",
            context_hint="Use list_engines() to see all supported engine families.",
        )

    from qmatsuite.api.engines import (
        get_active_engine as api_get_active,
        uninstall_engine as api_uninstall,
    )

    iid = (installation_id or "").strip()
    if not iid:
        # Auto-detect active installation
        active = api_get_active(family)
        if not active:
            return make_error(
                "no_active_installation",
                f"No active installation found for '{family}'. Nothing to uninstall.",
                context_hint="Use list_engines(installed_only=True) to check installed engines.",
            )
        iid = active.get("id", "")
        if not iid:
            return make_error(
                "no_installation_id",
                f"Active installation for '{family}' has no ID.",
                context_hint="Use list_engines() to inspect installation details.",
            )

    try:
        result = api_uninstall(family, iid)
    except ValueError as exc:
        return make_error(
            "uninstall_failed",
            str(exc),
            context_hint="Check the engine name and installation ID. Use list_engines() to see details.",
        )

    return make_response(
        {"engine": family, "installation_id": iid, "removed": result.get("removed", True)},
        context_hint=f"Use list_engines(installed_only=True) to confirm '{family}' was removed.",
    )
