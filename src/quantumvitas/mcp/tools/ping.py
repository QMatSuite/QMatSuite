"""Ping tool — lightweight health check for the MCP server."""

from __future__ import annotations

from quantumvitas.mcp.app import mcp
from quantumvitas.mcp.envelope import make_response


@mcp.tool
def ping() -> dict:
    """Return server version and status. Use this to verify connectivity."""
    return make_response({"version": "0.1.0", "status": "ok"})
