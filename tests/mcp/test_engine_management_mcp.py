"""Unit tests for MCP engine management tools."""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# list_installable_engines
# ---------------------------------------------------------------------------

def test_list_installable_engines_schema():
    from qmatsuite.mcp.tools.list_installable_engines import list_installable_engines

    result = list_installable_engines.fn()
    assert result["status"] == "success"
    data = result["data"]
    assert "engines" in data
    assert "total" in data
    assert isinstance(data["engines"], list)
    assert data["total"] == len(data["engines"])

    # Each entry should have engine key and manual_only flag
    for entry in data["engines"]:
        assert "engine" in entry
        assert "manual_only" in entry
        assert isinstance(entry["manual_only"], bool)


# ---------------------------------------------------------------------------
# install_engine
# ---------------------------------------------------------------------------

def test_install_engine_unknown_error():
    from qmatsuite.mcp.tools.install_engine import install_engine

    result = install_engine.fn(engine="nonexistent_engine_xyz")
    assert result["status"] == "error"
    assert result["error_type"] == "unknown_engine"


def test_install_engine_commercial_rejects():
    """Commercial engines (VASP, ORCA, Gaussian) should return manual_only_engine error."""
    from qmatsuite.mcp.tools.install_engine import install_engine

    for engine in ("vasp", "orca", "gaussian"):
        result = install_engine.fn(engine=engine)
        assert result["status"] == "error", f"{engine} should fail"
        assert result["error_type"] == "manual_only_engine", f"{engine}: {result}"
        assert "register_engine_path" in (result.get("context_hint") or "")


def test_install_engine_success_mock(monkeypatch):
    """Mock a successful install and verify response envelope."""
    from qmatsuite.mcp.tools import install_engine as install_mod

    fake_installation = {
        "id": "conda-abc123",
        "source": "conda",
        "path": "/tmp/fake/envs/xtb/bin",
    }

    def mock_install(family, version=None, source="auto", on_progress=None):
        if on_progress:
            on_progress(stage="download")
            on_progress(stage="install")
        return {"engine": family, "source": "conda", "installation": fake_installation}

    monkeypatch.setattr("qmatsuite.api.engines.install_engine", mock_install)

    from qmatsuite.mcp.tools.install_engine import install_engine

    result = install_engine.fn(engine="xtb")
    assert result["status"] == "success"
    assert result["data"]["engine"] == "xtb"
    assert result["data"]["installation"] == fake_installation
    assert result["data"]["last_stage"] == "install"


# ---------------------------------------------------------------------------
# verify_engine
# ---------------------------------------------------------------------------

def test_verify_engine_unknown():
    from qmatsuite.mcp.tools.verify_engine import verify_engine

    result = verify_engine.fn(engine="nonexistent_xyz")
    assert result["status"] == "error"
    assert result["error_type"] == "unknown_engine"


def test_verify_engine_not_installed(monkeypatch):
    monkeypatch.setattr(
        "qmatsuite.api.engines.verify_engine",
        lambda family: (False, f"{family} not found"),
    )
    from qmatsuite.mcp.tools.verify_engine import verify_engine

    result = verify_engine.fn(engine="xtb")
    assert result["status"] == "success"
    assert result["data"]["ok"] is False
    assert result["data"]["engine"] == "xtb"
    assert len(result["warnings"]) > 0


def test_verify_engine_success(monkeypatch):
    monkeypatch.setattr(
        "qmatsuite.api.engines.verify_engine",
        lambda family: (True, "OK"),
    )
    from qmatsuite.mcp.tools.verify_engine import verify_engine

    result = verify_engine.fn(engine="qe")
    assert result["status"] == "success"
    assert result["data"]["ok"] is True
    assert result["data"]["engine"] == "qe"
    assert result["warnings"] == []


# ---------------------------------------------------------------------------
# register_engine_path
# ---------------------------------------------------------------------------

def test_register_engine_path_unknown():
    from qmatsuite.mcp.tools.register_engine_path import register_engine_path

    result = register_engine_path.fn(engine="nonexistent_xyz", path="/tmp")
    assert result["status"] == "error"
    assert result["error_type"] == "unknown_engine"


def test_register_engine_path_missing_path():
    from qmatsuite.mcp.tools.register_engine_path import register_engine_path

    result = register_engine_path.fn(engine="vasp", path="/nonexistent/path/xyz")
    assert result["status"] == "error"
    assert result["error_type"] == "path_not_found"


def test_register_engine_path_schema(monkeypatch, tmp_path):
    fake_installation = {"id": "user-abc", "source": "user_path", "path": str(tmp_path)}
    monkeypatch.setattr(
        "qmatsuite.api.engines.register_engine",
        lambda family, path, source: fake_installation,
    )
    from qmatsuite.mcp.tools.register_engine_path import register_engine_path

    result = register_engine_path.fn(engine="vasp", path=str(tmp_path))
    assert result["status"] == "success"
    assert result["data"]["engine"] == "vasp"
    assert result["data"]["installation"] == fake_installation


# ---------------------------------------------------------------------------
# uninstall_engine
# ---------------------------------------------------------------------------

def test_uninstall_engine_unknown():
    from qmatsuite.mcp.tools.uninstall_engine import uninstall_engine

    result = uninstall_engine.fn(engine="nonexistent_xyz")
    assert result["status"] == "error"
    assert result["error_type"] == "unknown_engine"


def test_uninstall_engine_not_found(monkeypatch):
    """ValueError from api → error envelope."""
    monkeypatch.setattr(
        "qmatsuite.api.engines.get_active_engine",
        lambda family: {"id": "inst-1"},
    )
    monkeypatch.setattr(
        "qmatsuite.api.engines.uninstall_engine",
        lambda family, iid: (_ for _ in ()).throw(ValueError("not found")),
    )
    from qmatsuite.mcp.tools.uninstall_engine import uninstall_engine

    result = uninstall_engine.fn(engine="xtb")
    assert result["status"] == "error"
    assert result["error_type"] == "uninstall_failed"


def test_uninstall_engine_auto_active(monkeypatch):
    """Empty installation_id should auto-detect active installation."""
    monkeypatch.setattr(
        "qmatsuite.api.engines.get_active_engine",
        lambda family: {"id": "conda-abc123"},
    )
    monkeypatch.setattr(
        "qmatsuite.api.engines.uninstall_engine",
        lambda family, iid: {"engine": family, "installation_id": iid, "removed": True},
    )
    from qmatsuite.mcp.tools.uninstall_engine import uninstall_engine

    result = uninstall_engine.fn(engine="xtb", installation_id="")
    assert result["status"] == "success"
    assert result["data"]["installation_id"] == "conda-abc123"
    assert result["data"]["removed"] is True


# ---------------------------------------------------------------------------
# set_active_engine
# ---------------------------------------------------------------------------

def test_set_active_engine_unknown():
    from qmatsuite.mcp.tools.set_active_engine import set_active_engine

    result = set_active_engine.fn(engine="nonexistent_xyz", installation_id="x")
    assert result["status"] == "error"
    assert result["error_type"] == "unknown_engine"


def test_set_active_engine_schema(monkeypatch):
    monkeypatch.setattr(
        "qmatsuite.api.engines.set_active_engine",
        lambda family, iid: True,
    )
    from qmatsuite.mcp.tools.set_active_engine import set_active_engine

    result = set_active_engine.fn(engine="qe", installation_id="conda-abc")
    assert result["status"] == "success"
    assert result["data"]["engine"] == "qe"
    assert result["data"]["installation_id"] == "conda-abc"
    assert result["data"]["active"] is True


def test_set_active_engine_failure(monkeypatch):
    monkeypatch.setattr(
        "qmatsuite.api.engines.set_active_engine",
        lambda family, iid: False,
    )
    from qmatsuite.mcp.tools.set_active_engine import set_active_engine

    result = set_active_engine.fn(engine="qe", installation_id="nonexistent")
    assert result["status"] == "error"
    assert result["error_type"] == "set_active_failed"
