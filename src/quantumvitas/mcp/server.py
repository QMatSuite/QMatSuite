"""QMatSuite MCP server entry point.

Run via::

    python -m quantumvitas.mcp.server
"""

from __future__ import annotations

from quantumvitas.mcp.app import mcp  # noqa: F401 — re-export for convenience

# Register tools by importing their modules (side-effect registration).
import quantumvitas.mcp.tools.ping  # noqa: F401, E402
import quantumvitas.mcp.tools.list_engines  # noqa: F401, E402
import quantumvitas.mcp.tools.list_workflows  # noqa: F401, E402
import quantumvitas.mcp.tools.get_presets  # noqa: F401, E402
import quantumvitas.mcp.tools.search_parameters  # noqa: F401, E402

if __name__ == "__main__":
    mcp.run()
