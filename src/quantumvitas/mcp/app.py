"""Shared FastMCP application instance.

Separated from ``server.py`` to avoid the ``python -m`` dual-import problem:
when ``server.py`` is the ``__main__`` entry point, tool modules that
``from quantumvitas.mcp.server import mcp`` would get a *different* module
object and register on a second FastMCP instance.  Placing the singleton
here ensures a single ``mcp`` object regardless of how modules are loaded.
"""

from __future__ import annotations

from fastmcp import FastMCP

mcp = FastMCP("QMatSuite")
