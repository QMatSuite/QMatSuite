"""Tests for MCP list_engines installed-status wiring."""

from __future__ import annotations

import pytest


def test_mcp_list_engines_uses_api_installed_map(monkeypatch: pytest.MonkeyPatch) -> None:
    from quantumvitas.mcp.tools.list_engines import list_engines

    monkeypatch.setattr(
        "quantumvitas.api.engines.list_engines",
        lambda installed_only=False: [
            {"engine": "qe", "installed": True},
            {"engine": "vasp", "installed": False},
        ],
    )

    result = list_engines.fn()
    engines = {item["engine"]: item for item in result["data"]["engines"]}
    assert engines["qe"]["installed"] is True
    assert engines["vasp"]["installed"] is False


def test_mcp_list_engines_installed_only_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    from quantumvitas.mcp.tools.list_engines import list_engines

    monkeypatch.setattr(
        "quantumvitas.api.engines.list_engines",
        lambda installed_only=False: [
            {"engine": "qe", "installed": True},
            {"engine": "vasp", "installed": False},
        ],
    )

    result = list_engines.fn(installed_only=True)
    engines = result["data"]["engines"]
    assert len(engines) == 1
    assert engines[0]["engine"] == "qe"
    assert engines[0]["installed"] is True
