"""Real xTB install/uninstall lifecycle test via MCP tool wrappers.

Markers: @pytest.mark.network, @pytest.mark.integration
Requires actual network access and conda/micromamba availability.
"""

from __future__ import annotations

import pytest


@pytest.mark.network
@pytest.mark.integration
def test_xtb_mcp_install_lifecycle(tmp_path, monkeypatch):
    """Full xTB install lifecycle via MCP tools: list → install → verify → uninstall."""
    monkeypatch.setenv("QMATSUITE_HOME", str(tmp_path))

    from qmatsuite.mcp.tools.list_engines import list_engines
    from qmatsuite.mcp.tools.list_installable_engines import list_installable_engines
    from qmatsuite.mcp.tools.install_engine import install_engine
    from qmatsuite.mcp.tools.verify_engine import verify_engine
    from qmatsuite.mcp.tools.uninstall_engine import uninstall_engine

    # 1. list_engines(installed_only=True) — xTB should NOT be present
    result = list_engines.fn(installed_only=True)
    assert result["status"] == "success"
    installed_names = [e["engine"] for e in result["data"]["engines"]]
    # xTB might be on PATH, so we just note its status
    xtb_was_installed = "xtb" in installed_names

    # 2. list_installable_engines() — xTB should appear with conda method
    result = list_installable_engines.fn()
    assert result["status"] == "success"
    engine_names = [e["engine"] for e in result["data"]["engines"]]
    assert "xtb" in engine_names
    xtb_entry = next(e for e in result["data"]["engines"] if e["engine"] == "xtb")
    assert xtb_entry["manual_only"] is False

    # 3. install_engine(engine="xtb") — real conda install
    result = install_engine.fn(engine="xtb")
    assert result["status"] == "success", f"Install failed: {result}"
    assert result["data"]["engine"] == "xtb"
    installation = result["data"]["installation"]
    install_id = installation.get("id") or installation.get("installation_id")
    assert install_id, f"No installation id: {installation}"

    # 4. list_engines(installed_only=True) — xTB should now be present
    result = list_engines.fn(installed_only=True)
    assert result["status"] == "success"
    installed_names = [e["engine"] for e in result["data"]["engines"]]
    assert "xtb" in installed_names

    # 5. verify_engine(engine="xtb") — should be ok
    result = verify_engine.fn(engine="xtb")
    assert result["status"] == "success"
    assert result["data"]["ok"] is True

    # 6. uninstall_engine(engine="xtb") — remove it
    result = uninstall_engine.fn(engine="xtb", installation_id=install_id)
    assert result["status"] == "success"
    assert result["data"]["removed"] is True

    # 7. list_engines(installed_only=True) — xTB should be gone (unless was on PATH)
    result = list_engines.fn(installed_only=True)
    assert result["status"] == "success"
    installed_names = [e["engine"] for e in result["data"]["engines"]]
    if not xtb_was_installed:
        assert "xtb" not in installed_names
