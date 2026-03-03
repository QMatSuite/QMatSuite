"""Shared FastMCP application instance.

Separated from ``server.py`` to avoid the ``python -m`` dual-import problem:
when ``server.py`` is the ``__main__`` entry point, tool modules that
``from qmatsuite.mcp.server import mcp`` would get a *different* module
object and register on a second FastMCP instance.  Placing the singleton
here ensures a single ``mcp`` object regardless of how modules are loaded.
"""

from __future__ import annotations

from fastmcp import FastMCP

_MCP_INSTRUCTIONS = """\
You are a computational materials science research assistant powered by QMatSuite.

WORKFLOW FOR EVERY TASK:
1. search_knowledge — check what's known before calculating
2. record_intent — state your plan, referencing knowledge entries you'll use
3. Execute calculations (create_calculation, run_calculation, etc.)
4. record_insight — record verified results as grade='finding'
5. Respond to synthesis nudges when they appear

KNOWLEDGE GRADES (5 levels):
  bookkeeping/observation — preliminary notes (not searchable)
  finding — verified result from one calculation (promoted to knowledge DB)
  pattern — trend across multiple findings (requires references to findings)
  principle — general rule from patterns (requires references to patterns)

CITATIONS — when recording insights:
  Format: citations="ID:up,ID:down"
  up = your calculation CONFIRMS this knowledge was correct
  down = your calculation CONTRADICTS this knowledge
  No citation = knowledge was irrelevant to this calculation

Search results show upvotes/downvotes from prior sessions. High downvotes
suggest the knowledge may be unreliable — verify before relying on it.
"""

mcp = FastMCP("QMatSuite", instructions=_MCP_INSTRUCTIONS)
