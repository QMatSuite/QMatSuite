"""list_installable_engines tool — discover engines with automatic install methods."""

from __future__ import annotations

from qmatsuite.mcp.app import mcp
from qmatsuite.mcp.envelope import make_response


@mcp.tool
def list_installable_engines() -> dict:
    """List engines that can be auto-installed, with their install methods and manual-only flags.

    Returns a list of engines indicating which can be installed automatically
    (via conda or GitHub release) and which require manual installation.
    """
    from qmatsuite.api.engines import list_installable_engines as api_list_installable
    from qmatsuite.core.engines.engine_meta import ENGINE_META

    installable = api_list_installable()

    # Enrich with manual_only flag
    engines_out: list[dict] = []
    for entry in installable:
        family = entry.get("engine", "")
        meta = ENGINE_META.get(family, {})
        has_conda = bool(meta.get("conda_package"))
        has_github = family == "qe"
        engines_out.append({
            **entry,
            "manual_only": not has_conda and not has_github,
        })

    # Also include manual-only engines not in the installable list
    installable_families = {e.get("engine") for e in installable}
    for family, meta in sorted(ENGINE_META.items()):
        if family in installable_families:
            continue
        has_conda = bool(meta.get("conda_package"))
        has_github = family == "qe"
        if not has_conda and not has_github:
            engines_out.append({
                "engine": family,
                "display_name": meta.get("display_name", family),
                "manual_only": True,
            })

    return make_response(
        {"engines": engines_out, "total": len(engines_out)},
        context_hint=(
            "Use install_engine(engine='...') for auto-installable engines, "
            "or register_engine_path(engine='...', path='...') for manual-only engines."
        ),
    )
