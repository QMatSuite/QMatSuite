"""register_engine_path tool — register a manually installed engine."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def register_engine_path(engine: str, path: str, source: str = "user_path") -> dict:
    """Register a manually installed engine by providing its installation path.

    Use this for commercial engines (VASP, ORCA, Gaussian) or any engine
    installed outside of QMatSuite's automatic installer.

    Args:
        engine: Engine family key (e.g. 'vasp', 'orca', 'gaussian').
        path: Absolute path to the engine installation directory or binary.
        source: Installation source label (default 'user_path').
    """
    from pathlib import Path as _Path

    from qmatsuite.core.engines.engine_meta import ENGINE_META

    family = (engine or "").strip().lower()
    if family not in ENGINE_META:
        return make_error(
            "unknown_engine",
            f"Unknown engine '{engine}'. Use list_engines() to see available engines.",
            context_hint="Use list_engines() to see all supported engine families.",
        )

    resolved = _Path(path).expanduser().resolve()
    if not resolved.exists():
        return make_error(
            "path_not_found",
            f"Path does not exist: {path}",
            context_hint="Provide the absolute path to the engine installation directory or binary.",
        )

    from qmatsuite.api.engines import register_engine as api_register

    try:
        installation = api_register(family, path=resolved, source=source)
    except ValueError as exc:
        return make_error(
            "register_failed",
            str(exc),
            context_hint="Check the path and ensure it contains the engine binaries.",
        )

    return make_response(
        {"engine": family, "installation": installation},
        context_hint=f"Use verify_engine(engine='{family}') to validate the installation.",
    )
