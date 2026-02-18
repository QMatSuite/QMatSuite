"""QMatSuite MCP server entry point.

Run via::

    python -m quantumvitas.mcp.server
"""

from __future__ import annotations

from quantumvitas.mcp.app import mcp  # noqa: F401 — re-export for convenience

# Register tools by importing their modules (side-effect registration).
# Stage 0 + 1: read-only discovery tools
import quantumvitas.mcp.tools.ping  # noqa: F401, E402
import quantumvitas.mcp.tools.list_engines  # noqa: F401, E402
import quantumvitas.mcp.tools.list_workflows  # noqa: F401, E402
import quantumvitas.mcp.tools.get_presets  # noqa: F401, E402
import quantumvitas.mcp.tools.search_parameters  # noqa: F401, E402

# Stage 2: configuration tools
import quantumvitas.mcp.tools.create_calculation  # noqa: F401, E402
import quantumvitas.mcp.tools.set_parameters  # noqa: F401, E402
import quantumvitas.mcp.tools.apply_preset  # noqa: F401, E402
import quantumvitas.mcp.tools.inspect_calculation  # noqa: F401, E402
import quantumvitas.mcp.tools.preview_compilation  # noqa: F401, E402

# Stage 3: execution tools
import quantumvitas.mcp.tools.run_calculation  # noqa: F401, E402
import quantumvitas.mcp.tools.get_status  # noqa: F401, E402
import quantumvitas.mcp.tools.get_results_summary  # noqa: F401, E402
import quantumvitas.mcp.tools.quick_run  # noqa: F401, E402

if __name__ == "__main__":
    mcp.run()
