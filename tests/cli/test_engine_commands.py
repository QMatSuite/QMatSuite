"""CLI tests for `qms engine` commands."""

from __future__ import annotations

from typer.testing import CliRunner

from qmatsuite.cli.main import app


runner = CliRunner()


def test_engine_list_command(monkeypatch):
    monkeypatch.setattr(
        "qmatsuite.api.engines.list_engines",
        lambda installed_only=False: [
            {
                "engine": "qe",
                "installed": True,
                "active_source": "bundled",
                "active_installation_id": "bundled-7.5",
            },
            {
                "engine": "vasp",
                "installed": False,
                "active_source": None,
                "active_installation_id": None,
            },
        ],
    )

    result = runner.invoke(app, ["engine", "list"])
    assert result.exit_code == 0
    assert "qe" in result.output
    assert "vasp" in result.output


def test_engine_install_command(monkeypatch):
    monkeypatch.setattr(
        "qmatsuite.api.engines.install_engine",
        lambda engine_family, version=None, source="auto": {
            "engine": engine_family,
            "source": source,
            "installation": {
                "id": "conda-6.7.1",
                "path": "/tmp/xtb/bin",
                "version": "6.7.1",
            },
        },
    )

    result = runner.invoke(app, ["engine", "install", "xtb", "--version", "6.7.1"])
    assert result.exit_code == 0
    assert "Installed xtb" in result.output
    assert "conda-6.7.1" in result.output


def test_engine_uninstall_defaults_to_active(monkeypatch):
    monkeypatch.setattr(
        "qmatsuite.api.engines.get_active_engine",
        lambda _engine: {"id": "conda-6.7.1"},
    )
    monkeypatch.setattr(
        "qmatsuite.api.engines.uninstall_engine",
        lambda engine_family, installation_id: {
            "engine": engine_family,
            "installation_id": installation_id,
            "removed": True,
        },
    )

    result = runner.invoke(app, ["engine", "uninstall", "xtb"])
    assert result.exit_code == 0
    assert "conda-6.7.1" in result.output


def test_engine_verify_failure(monkeypatch):
    monkeypatch.setattr("qmatsuite.api.engines.verify_engine", lambda _engine: (False, "missing"))

    result = runner.invoke(app, ["engine", "verify", "xtb"])
    assert result.exit_code == 1
    assert "missing" in result.output
