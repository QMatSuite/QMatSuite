"""CLI tests for `qms mcp config` command."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qmatsuite.cli.main import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Claude (default)
# ---------------------------------------------------------------------------

def test_mcp_config_claude_default():
    """Default output (Claude, project scope) is valid JSON with mcpServers.qmatsuite."""
    result = runner.invoke(app, ["mcp", "config"])
    assert result.exit_code == 0, f"stderr: {result.output}"
    config = json.loads(result.output)
    assert "mcpServers" in config
    qs = config["mcpServers"]["qmatsuite"]
    assert qs["type"] == "stdio"
    assert "command" in qs
    assert qs["args"] == ["-m", "qmatsuite.mcp.server"]


def test_mcp_config_uses_sys_executable():
    """The command path should be sys.executable."""
    result = runner.invoke(app, ["mcp", "config"])
    assert result.exit_code == 0
    config = json.loads(result.output)
    assert config["mcpServers"]["qmatsuite"]["command"] == sys.executable


# ---------------------------------------------------------------------------
# Codex
# ---------------------------------------------------------------------------

def test_mcp_config_codex():
    """Codex output contains TOML-style [mcp_servers.qmatsuite] section."""
    result = runner.invoke(app, ["mcp", "config", "--agent", "codex"])
    assert result.exit_code == 0, f"output: {result.output}"
    assert "[mcp_servers.qmatsuite]" in result.output
    assert 'command = "' in result.output
    assert '"-m", "qmatsuite.mcp.server"' in result.output


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------

def test_mcp_config_gemini():
    """Gemini output is valid JSON with mcpServers.qmatsuite."""
    result = runner.invoke(app, ["mcp", "config", "--agent", "gemini"])
    assert result.exit_code == 0, f"output: {result.output}"
    config = json.loads(result.output)
    assert "mcpServers" in config
    qs = config["mcpServers"]["qmatsuite"]
    assert "command" in qs
    assert qs["args"] == ["-m", "qmatsuite.mcp.server"]
    # Gemini does not require "type" field
    assert "type" not in qs


# ---------------------------------------------------------------------------
# --project flag
# ---------------------------------------------------------------------------

def test_mcp_config_project_env(tmp_path):
    """--project flag adds QMATSUITE_PROJECT env var to config."""
    result = runner.invoke(app, ["mcp", "config", "--project", str(tmp_path)])
    assert result.exit_code == 0
    config = json.loads(result.output)
    env = config["mcpServers"]["qmatsuite"].get("env", {})
    assert "QMATSUITE_PROJECT" in env


def test_mcp_config_codex_project_env(tmp_path):
    """--project flag adds env section to Codex TOML output."""
    result = runner.invoke(app, ["mcp", "config", "--agent", "codex", "--project", str(tmp_path)])
    assert result.exit_code == 0
    assert "QMATSUITE_PROJECT" in result.output


# ---------------------------------------------------------------------------
# --write flag
# ---------------------------------------------------------------------------

def test_mcp_config_write_creates_file(tmp_path, monkeypatch):
    """--write creates .mcp.json in CWD for Claude."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["mcp", "config", "--write"])
    assert result.exit_code == 0, f"output: {result.output}"
    target = tmp_path / ".mcp.json"
    assert target.exists()
    config = json.loads(target.read_text())
    assert "mcpServers" in config
    assert "qmatsuite" in config["mcpServers"]


def test_mcp_config_write_merges_existing(tmp_path, monkeypatch):
    """--write preserves existing keys in JSON config."""
    monkeypatch.chdir(tmp_path)
    target = tmp_path / ".mcp.json"
    existing = {"mcpServers": {"other_tool": {"command": "other"}}, "extra_key": True}
    target.write_text(json.dumps(existing))

    result = runner.invoke(app, ["mcp", "config", "--write"])
    assert result.exit_code == 0
    merged = json.loads(target.read_text())
    assert "qmatsuite" in merged["mcpServers"]
    assert "other_tool" in merged["mcpServers"]
    assert merged["extra_key"] is True


def test_mcp_config_write_codex(tmp_path, monkeypatch):
    """--write for Codex creates .codex/config.toml."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["mcp", "config", "--agent", "codex", "--write"])
    assert result.exit_code == 0
    target = tmp_path / ".codex" / "config.toml"
    assert target.exists()
    content = target.read_text()
    assert "[mcp_servers.qmatsuite]" in content


def test_mcp_config_write_gemini(tmp_path, monkeypatch):
    """--write for Gemini creates .gemini/settings.json."""
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["mcp", "config", "--agent", "gemini", "--write"])
    assert result.exit_code == 0
    target = tmp_path / ".gemini" / "settings.json"
    assert target.exists()
    config = json.loads(target.read_text())
    assert "mcpServers" in config
    assert "qmatsuite" in config["mcpServers"]
