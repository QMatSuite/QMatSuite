"""QMatSuite MCP server entry point.

Run via::

    python -m quantumvitas.mcp.server
"""

from __future__ import annotations

from quantumvitas.mcp.app import mcp  # noqa: F401 — re-export for convenience

# Register tools by importing their modules (side-effect registration).
# Stage P1: project management
import quantumvitas.mcp.tools.init_project  # noqa: F401, E402

# Stage 0 + 1: read-only discovery tools
import quantumvitas.mcp.tools.ping  # noqa: F401, E402
import quantumvitas.mcp.tools.list_engines  # noqa: F401, E402
import quantumvitas.mcp.tools.list_workflows  # noqa: F401, E402
import quantumvitas.mcp.tools.get_presets  # noqa: F401, E402
import quantumvitas.mcp.tools.search_parameters  # noqa: F401, E402

# Stage 2: configuration tools
import quantumvitas.mcp.tools.create_calculation  # noqa: F401, E402
import quantumvitas.mcp.tools.set_species_map  # noqa: F401, E402
import quantumvitas.mcp.tools.set_parameters  # noqa: F401, E402
import quantumvitas.mcp.tools.apply_preset  # noqa: F401, E402
import quantumvitas.mcp.tools.inspect_calculation  # noqa: F401, E402
import quantumvitas.mcp.tools.preview_compilation  # noqa: F401, E402

# Stage 3: execution tools
import quantumvitas.mcp.tools.run_calculation  # noqa: F401, E402
import quantumvitas.mcp.tools.get_status  # noqa: F401, E402
import quantumvitas.mcp.tools.get_results_summary  # noqa: F401, E402
import quantumvitas.mcp.tools.quick_run  # noqa: F401, E402

# Stage 4: knowledge infrastructure
import quantumvitas.mcp.tools.search_knowledge  # noqa: F401, E402

# Stage 7: structure tools
import quantumvitas.mcp.tools.list_structures       # noqa: F401, E402
import quantumvitas.mcp.tools.import_structure       # noqa: F401, E402
import quantumvitas.mcp.tools.get_structure_detail   # noqa: F401, E402

# Stage 9: promote structure
import quantumvitas.mcp.tools.promote_structure      # noqa: F401, E402

# Stage 10: demo store
import quantumvitas.mcp.tools.demo_store             # noqa: F401, E402

# Stage P2: resource management
import quantumvitas.mcp.tools.list_resources          # noqa: F401, E402
import quantumvitas.mcp.tools.resolve_species_map     # noqa: F401, E402

# Stage P4: pseudo download
import quantumvitas.mcp.tools.download_pseudo_library  # noqa: F401, E402

# ---------------------------------------------------------------------------
# Startup auto-load: try to locate an existing project before the first tool
# call so that tools don't fail with "no_project" when CWD is inside one.
# ---------------------------------------------------------------------------
import os as _os
from pathlib import Path as _Path

_project_dir = _Path(_os.environ.get("QMATSUITE_PROJECT", ".")).resolve()
try:
    from quantumvitas.core.project_utils import find_project_root as _find_project_root
    from quantumvitas.mcp.project import set_project_root as _set_project_root

    _found = _find_project_root(start=_project_dir) if _project_dir.exists() else None
    if _found is not None:
        _set_project_root(_found)
except Exception:
    pass  # Best-effort: don't prevent server from starting

if __name__ == "__main__":
    mcp.run()
