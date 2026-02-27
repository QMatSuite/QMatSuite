"""QMatSuite MCP server entry point.

Run via::

    python -m qmatsuite.mcp.server
"""

from __future__ import annotations

import os as _os
from pathlib import Path as _Path
from qmatsuite.mcp.app import mcp  # noqa: F401 — re-export for convenience

_TOOLS_REGISTERED = False


def _register_tools() -> None:
    """Register MCP tools exactly once via module import side effects."""
    global _TOOLS_REGISTERED
    if _TOOLS_REGISTERED:
        return

    # Register tools by importing their modules (side-effect registration).
    # Stage P1: project management
    import qmatsuite.mcp.tools.init_project  # noqa: F401

    # Stage 0 + 1: read-only discovery tools
    import qmatsuite.mcp.tools.ping  # noqa: F401
    import qmatsuite.mcp.tools.list_engines  # noqa: F401
    import qmatsuite.mcp.tools.list_workflows  # noqa: F401
    import qmatsuite.mcp.tools.get_presets  # noqa: F401
    import qmatsuite.mcp.tools.search_parameters  # noqa: F401

    # Stage 2: configuration tools
    import qmatsuite.mcp.tools.create_calculation  # noqa: F401
    import qmatsuite.mcp.tools.set_species_map  # noqa: F401
    import qmatsuite.mcp.tools.set_parameters  # noqa: F401
    import qmatsuite.mcp.tools.apply_preset  # noqa: F401
    import qmatsuite.mcp.tools.inspect_calculation  # noqa: F401
    import qmatsuite.mcp.tools.list_calculations  # noqa: F401
    import qmatsuite.mcp.tools.preview_compilation  # noqa: F401

    # Stage 3: execution tools
    import qmatsuite.mcp.tools.run_calculation  # noqa: F401
    import qmatsuite.mcp.tools.get_status  # noqa: F401
    import qmatsuite.mcp.tools.get_results_summary  # noqa: F401
    import qmatsuite.mcp.tools.quick_run  # noqa: F401

    # Stage 4: knowledge infrastructure
    import qmatsuite.mcp.tools.search_knowledge  # noqa: F401
    import qmatsuite.mcp.tools.record_insight  # noqa: F401
    import qmatsuite.mcp.tools.record_intent  # noqa: F401

    # Stage 7: structure tools
    import qmatsuite.mcp.tools.list_structures  # noqa: F401
    import qmatsuite.mcp.tools.import_structure  # noqa: F401
    import qmatsuite.mcp.tools.get_structure_detail  # noqa: F401

    # Stage 9: promote structure
    import qmatsuite.mcp.tools.promote_structure  # noqa: F401

    # Stage 10: demo store
    import qmatsuite.mcp.tools.demo_store  # noqa: F401

    # Stage P2: resource management
    import qmatsuite.mcp.tools.list_resources  # noqa: F401
    import qmatsuite.mcp.tools.resolve_species_map  # noqa: F401

    # Stage P4: pseudo download
    import qmatsuite.mcp.tools.download_pseudo_library  # noqa: F401

    # Stage P1b: project health
    import qmatsuite.mcp.tools.cleanup_project  # noqa: F401

    # Engine management tools
    import qmatsuite.mcp.tools.install_engine  # noqa: F401
    import qmatsuite.mcp.tools.list_installable_engines  # noqa: F401
    import qmatsuite.mcp.tools.verify_engine  # noqa: F401
    import qmatsuite.mcp.tools.register_engine_path  # noqa: F401
    import qmatsuite.mcp.tools.uninstall_engine  # noqa: F401
    import qmatsuite.mcp.tools.set_active_engine  # noqa: F401

    # Stage 2A: analysis & visualization tools
    import qmatsuite.mcp.tools.list_analyses  # noqa: F401
    import qmatsuite.mcp.tools.plot_analysis  # noqa: F401
    import qmatsuite.mcp.tools.generate_kpath  # noqa: F401

    _TOOLS_REGISTERED = True


def _autoload_project() -> None:
    """Best-effort project auto-detection for first tool call."""
    project_dir = _Path(_os.environ.get("QMATSUITE_PROJECT", ".")).resolve()
    try:
        from qmatsuite.core.project_utils import find_project_root as _find_project_root
        from qmatsuite.mcp.project import set_project_root as _set_project_root

        found = _find_project_root(start=project_dir) if project_dir.exists() else None
        if found is not None:
            _set_project_root(found)
    except Exception:
        pass  # Do not block server startup on best-effort project detection


def create_server():
    """
    Return the configured MCP server instance.

    Returns:
        The configured FastMCP application singleton.
    """
    _register_tools()
    _autoload_project()
    return mcp


# Preserve existing import-time behavior (tools available immediately on import).
_register_tools()
_autoload_project()

if __name__ == "__main__":
    create_server().run()
