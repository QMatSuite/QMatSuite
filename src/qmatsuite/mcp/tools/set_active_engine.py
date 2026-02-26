"""set_active_engine tool — switch the active installation for an engine."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def set_active_engine(engine: str, installation_id: str) -> dict:
    """Set which installation is active for an engine family.

    Use this when multiple installations exist and you want to switch
    between them (e.g. different versions or builds).

    Args:
        engine: Engine family key (e.g. 'qe', 'vasp').
        installation_id: The installation ID to activate.
    """
    from qmatsuite.core.engines.engine_meta import ENGINE_META

    family = (engine or "").strip().lower()
    if family not in ENGINE_META:
        return make_error(
            "unknown_engine",
            f"Unknown engine '{engine}'. Use list_engines() to see available engines.",
            context_hint="Use list_engines() to see all supported engine families.",
        )

    from qmatsuite.api.engines import set_active_engine as api_set_active

    try:
        ok = api_set_active(family, installation_id)
    except Exception as exc:
        return make_error(
            "set_active_failed",
            str(exc),
            context_hint="Use list_engines() to see available installations and their IDs.",
        )

    if not ok:
        return make_error(
            "set_active_failed",
            f"Could not set installation '{installation_id}' as active for '{family}'.",
            context_hint="Use list_engines() to verify the installation ID exists.",
        )

    return make_response(
        {"engine": family, "installation_id": installation_id, "active": True},
        context_hint=f"Use verify_engine(engine='{family}') to confirm the installation works.",
    )
