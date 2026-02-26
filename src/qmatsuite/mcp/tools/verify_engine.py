"""verify_engine tool — check that an engine installation is functional."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_error, make_response


@mcp.tool
def verify_engine(engine: str) -> dict:
    """Verify that an engine's active installation is functional.

    Runs the engine's version/health check and reports success or failure.

    Args:
        engine: Engine family key (e.g. 'xtb', 'qe', 'vasp').
    """
    from qmatsuite.core.engines.engine_meta import ENGINE_META

    family = (engine or "").strip().lower()
    if family not in ENGINE_META:
        return make_error(
            "unknown_engine",
            f"Unknown engine '{engine}'. Use list_engines() to see available engines.",
            context_hint="Use list_engines() to see all supported engine families.",
        )

    from qmatsuite.api.engines import verify_engine as api_verify

    try:
        ok, message = api_verify(family)
    except Exception as exc:
        return make_error(
            "verify_failed",
            f"Verification error for '{family}': {exc}",
            context_hint="The engine may not be installed. Use list_engines(installed_only=True) to check.",
        )

    data = {"engine": family, "ok": ok, "message": message}
    if ok:
        return make_response(data)
    return make_response(
        data,
        warnings=[message],
        context_hint=(
            f"Engine '{family}' verification failed. "
            "Use install_engine() or register_engine_path() to set up a working installation."
        ),
    )
