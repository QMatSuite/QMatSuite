"""Tests for API-level engine registry helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from qmatsuite.api.engines import list_engines
from qmatsuite.core.engines.engine_meta import ENGINE_META
from qmatsuite.core.engines.engine_registry import EngineRegistry


def _make_executable(path: Path, text: str = "echo ok") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{text}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_api_list_engines_all_false_when_no_registry_and_no_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("QMATSUITE_HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.setattr(
        "qmatsuite.api.engines._engine_installed_via_fallback",
        lambda _engine: False,
    )

    items = list_engines()
    assert len(items) == len(ENGINE_META)
    assert all(item["installed"] is False for item in items)


def test_api_list_engines_registry_active_qe_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    qe_bin = home / "engines" / "qe" / "bundled-7.5" / "bin"
    _make_executable(qe_bin / "pw.x")

    monkeypatch.setenv("QMATSUITE_HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.setattr(
        "qmatsuite.api.engines._engine_installed_via_fallback",
        lambda _engine: False,
    )

    registry = EngineRegistry()
    registry.add_installation(
        "qe",
        {
            "id": "bundled-7.5",
            "source": "bundled",
            "path": str(qe_bin),
            "required_binaries": ["pw.x"],
            "env_vars": {},
        },
    )
    registry.set_active("qe", "bundled-7.5")

    items = {item["engine"]: item for item in list_engines()}
    assert items["qe"]["installed"] is True
    assert items["qe"]["active_installation_id"] == "bundled-7.5"
    assert items["vasp"]["installed"] is False


def test_api_list_engines_installed_only_filters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    qe_bin = home / "engines" / "qe" / "bundled-7.5" / "bin"
    _make_executable(qe_bin / "pw.x")

    monkeypatch.setenv("QMATSUITE_HOME", str(home))
    monkeypatch.setenv("PATH", str(tmp_path / "empty-path"))
    monkeypatch.setattr(
        "qmatsuite.api.engines._engine_installed_via_fallback",
        lambda _engine: False,
    )

    registry = EngineRegistry()
    registry.add_installation(
        "qe",
        {
            "id": "bundled-7.5",
            "source": "bundled",
            "path": str(qe_bin),
            "required_binaries": ["pw.x"],
            "env_vars": {},
        },
    )
    registry.set_active("qe", "bundled-7.5")

    items = list_engines(installed_only=True)
    assert len(items) == 1
    assert items[0]["engine"] == "qe"
    assert items[0]["installed"] is True


def test_api_list_engines_system_path_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    _make_executable(bin_dir / "xtb")

    monkeypatch.setenv("QMATSUITE_HOME", str(home))
    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setattr(
        "qmatsuite.api.engines._check_python_import_current",
        lambda _module: False,
    )

    items = {item["engine"]: item for item in list_engines()}
    assert items["xtb"]["installed"] is True
