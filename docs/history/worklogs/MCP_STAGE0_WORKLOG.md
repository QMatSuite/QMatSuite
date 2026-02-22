# MCP Stage 0: Server Skeleton — Worklog

## Plan

### Context
The AGENT_INTEGRATION_DESIGN.md design doc is frozen. Stage 0 stands up the MCP server
infrastructure so that Claude Code (or any MCP client) can connect via stdio and call a
single `ping` tool, proving the full round-trip works. Pure plumbing — no QMSService
integration yet.

### Key Decisions
- **FastMCP v2** (`fastmcp>=2,<3`) as the MCP SDK — simple `@mcp.tool` decorator API
- **Separate `app.py`** for the `FastMCP("QMatSuite")` singleton to avoid the `python -m`
  dual-import problem (server.py as `__main__` vs tools importing `qmatsuite.mcp.server`)
- **NDJSON framing** on stdio (newline-delimited JSON, not Content-Length) — confirmed by
  testing against FastMCP 2.14.5
- **Standard envelope** `{"data": ..., "context_hint": ..., "warnings": [...]}` for all
  tool responses

### Files Created (8 files)
1. `src/qmatsuite/mcp/__init__.py` — package init
2. `src/qmatsuite/mcp/app.py` — `mcp = FastMCP("QMatSuite")` singleton
3. `src/qmatsuite/mcp/envelope.py` — `make_response()` envelope helper
4. `src/qmatsuite/mcp/server.py` — entry point, tool registration, `mcp.run()`
5. `src/qmatsuite/mcp/tools/__init__.py` — tools sub-package init
6. `src/qmatsuite/mcp/tools/ping.py` — `@mcp.tool ping()` health check
7. `.mcp.json` — Claude Code MCP server configuration
8. `tests/mcp/test_stage0.py` (+ `tests/mcp/__init__.py`) — 6 tests

### File Modified (1 file)
- `pyproject.toml` — added `mcp = ["fastmcp>=2,<3"]` optional dep + added to `all` extras

### What Was NOT Done (by design)
- No QMSService integration
- No daemon modifications
- No `__main__.py`
- No complex logging setup
- No resource definitions

---

## Execution Log

### 2026-02-18 — Implementation

1. Created all package directories and source files
2. Installed `fastmcp>=2,<3` via `pip install -e ".[mcp]"` — pulled in FastMCP 2.14.5
3. Initial test run: 3 envelope tests pass, 3 failures:
   - `test_ping_tool_returns_envelope`: `@mcp.tool` returns `FunctionTool`, not callable → fixed by calling `.fn()`
   - `test_mcp_server_has_ping_tool`: `list_tools()` doesn't exist → fixed to `get_tools()` (async, returns dict)
   - `test_server_stdio_roundtrip`: Content-Length framing doesn't work → switched to NDJSON
4. Second run: 5 pass, 1 fail — `tools/list` returns empty tools. Root cause: `python -m` dual-import problem — `server.py` as `__main__` creates one `FastMCP` instance, `ping.py` importing `qmatsuite.mcp.server` creates another.
5. Fix: extracted `mcp = FastMCP("QMatSuite")` into `app.py`; both `server.py` and `ping.py` import from `app.py`.
6. All 6 tests pass.

### Verification
- `python -c "from qmatsuite.mcp.server import mcp; print(mcp)"` → `FastMCP('QMatSuite')`
- `python -m pytest tests/mcp/ -v` → 6 passed
