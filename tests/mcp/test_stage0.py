"""Stage 0 MCP server tests — envelope, ping tool, and stdio round-trip."""

from __future__ import annotations

import asyncio
import json
import queue
import subprocess
import sys
import threading
import time

import pytest


# ---------------------------------------------------------------------------
# Envelope tests
# ---------------------------------------------------------------------------

def test_envelope_shape():
    from quantumvitas.mcp.envelope import make_response

    result = make_response({"x": 1})
    assert result == {"status": "success", "data": {"x": 1}, "context_hint": None, "warnings": []}


def test_envelope_with_hint():
    from quantumvitas.mcp.envelope import make_response

    result = make_response({"x": 1}, context_hint="some hint")
    assert result["context_hint"] == "some hint"


def test_envelope_with_warnings():
    from quantumvitas.mcp.envelope import make_response

    result = make_response({"x": 1}, warnings=["w1", "w2"])
    assert result["warnings"] == ["w1", "w2"]


# ---------------------------------------------------------------------------
# Ping tool unit test
# ---------------------------------------------------------------------------

def test_ping_tool_returns_envelope():
    from quantumvitas.mcp.tools.ping import ping

    # @mcp.tool wraps the function in a FunctionTool; call .fn() for the raw function
    result = ping.fn()
    assert result["status"] == "success"
    assert "data" in result
    assert result["data"]["version"] == "0.1.0"
    assert result["data"]["status"] == "ok"
    assert result["context_hint"] is None
    assert result["warnings"] == []


# ---------------------------------------------------------------------------
# Server instance test
# ---------------------------------------------------------------------------

def test_mcp_server_has_ping_tool():
    from quantumvitas.mcp.server import mcp

    # FastMCP v2: get_tools() is async and returns dict[str, FunctionTool]
    tools = asyncio.run(mcp._tool_manager.get_tools())
    assert "ping" in tools


# ---------------------------------------------------------------------------
# Stdio round-trip (subprocess integration test)
# ---------------------------------------------------------------------------

def _jsonrpc(method: str, params: dict | None = None, id: int = 1) -> str:
    """Build a JSON-RPC 2.0 request string."""
    msg = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg)


class _StdioClient:
    """Manage a subprocess MCP server with NDJSON (newline-delimited JSON) framing."""

    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "quantumvitas.mcp.server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._reader = threading.Thread(target=self._read_lines, daemon=True)
        self._reader.start()

    def _read_lines(self):
        try:
            for line in self.proc.stdout:
                self._lines.put(line.rstrip("\n"))
        except Exception:
            pass
        finally:
            self._lines.put(None)

    def send(self, message: str) -> None:
        self.proc.stdin.write(message + "\n")
        self.proc.stdin.flush()

    def recv(self, timeout: float = 10.0) -> dict:
        """Read lines until we get a JSON-RPC response (has 'id' field).

        Skips server-initiated notifications (no 'id').
        """
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Timed out waiting for MCP response")
            try:
                line = self._lines.get(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if line is None:
                raise EOFError("Server closed stdout")
            msg = json.loads(line)
            # Skip notifications (no 'id' field)
            if "id" in msg:
                return msg

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


def test_server_stdio_roundtrip():
    """Launch the MCP server as a subprocess and exercise the JSON-RPC protocol."""
    client = _StdioClient()

    try:
        # --- 1. initialize ---
        client.send(_jsonrpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0.1"},
        }))
        init_resp = client.recv()
        assert init_resp.get("result"), f"init failed: {init_resp}"

        # --- 2. initialized notification (required by MCP protocol) ---
        client.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }))

        # --- 3. tools/list ---
        client.send(_jsonrpc("tools/list", {}, id=2))
        list_resp = client.recv()
        tool_names = [t["name"] for t in list_resp["result"]["tools"]]
        assert "ping" in tool_names

        # --- 4. tools/call ping ---
        client.send(_jsonrpc("tools/call", {"name": "ping", "arguments": {}}, id=3))
        call_resp = client.recv()
        content = call_resp["result"]["content"]
        # FastMCP wraps tool return in a text content block
        payload = json.loads(content[0]["text"])
        assert payload["data"]["status"] == "ok"
        assert payload["data"]["version"] == "0.1.0"

    finally:
        client.close()
