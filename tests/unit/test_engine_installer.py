"""Unit tests for core.engines.engine_installer."""

from __future__ import annotations

from pathlib import Path

import pytest

from quantumvitas.core.engines import engine_installer
from quantumvitas.core.engines.engine_registry import EngineRegistry


def _make_executable(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\n{text}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_install_engine_conda_creates_env_and_registers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"

    def fake_create_env(env_name: str, packages: list[str], channels: list[str], app_data_dir: Path) -> Path:
        assert env_name == "xtb-6.7.1"
        assert "xtb=6.7.1" in packages
        assert channels == ["conda-forge"]
        env_dir = app_data_dir / "micromamba" / "envs" / env_name
        _make_executable(env_dir / "bin" / "xtb", "echo 'xtb version 6.7.1'")
        return env_dir

    monkeypatch.setattr(engine_installer, "create_env", fake_create_env)

    installation = engine_installer.install_engine_conda("xtb", version="6.7.1", app_data_dir=home)
    assert installation["source"] == "micromamba"
    assert installation["conda_env"] == "xtb-6.7.1"

    registry = EngineRegistry(registry_path=home / "config" / "engines.json")
    active = registry.get_active("xtb")
    assert active is not None
    assert active["source"] == "micromamba"


def test_install_engine_conda_verification_failure_cleans_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    removed: list[str] = []

    def fake_create_env(env_name: str, packages: list[str], channels: list[str], app_data_dir: Path) -> Path:
        env_dir = app_data_dir / "micromamba" / "envs" / env_name
        env_dir.mkdir(parents=True, exist_ok=True)
        return env_dir

    def fake_remove_env(env_name: str, app_data_dir: Path) -> None:
        removed.append(env_name)

    monkeypatch.setattr(engine_installer, "create_env", fake_create_env)
    monkeypatch.setattr(engine_installer, "remove_env", fake_remove_env)

    with pytest.raises(RuntimeError, match="No required executable"):
        engine_installer.install_engine_conda("xtb", version="6.7.1", app_data_dir=home)

    assert removed == ["xtb-6.7.1"]


def test_install_engine_conda_sets_active_if_first(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"

    def fake_create_env(env_name: str, packages: list[str], channels: list[str], app_data_dir: Path) -> Path:
        env_dir = app_data_dir / "micromamba" / "envs" / env_name
        _make_executable(env_dir / "bin" / "xtb", "echo 'xtb version 6.7.1'")
        return env_dir

    monkeypatch.setattr(engine_installer, "create_env", fake_create_env)

    installation = engine_installer.install_engine_conda("xtb", version="6.7.1", app_data_dir=home)
    registry = EngineRegistry(registry_path=home / "config" / "engines.json")
    assert registry.get_active("xtb") is not None
    active = registry.get_active("xtb")
    assert active is not None
    assert active["source"] == installation["source"]
    assert active["conda_env"] == installation["conda_env"]


def test_uninstall_engine_removes_env_and_deregisters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    removed: list[str] = []

    registry = EngineRegistry(registry_path=home / "config" / "engines.json")
    registry.add_installation(
        "xtb",
        {
            "id": "conda-6.7.1",
            "source": "micromamba",
            "version": "6.7.1",
            "path": str(home / "micromamba" / "envs" / "xtb-6.7.1" / "bin"),
            "conda_env": "xtb-6.7.1",
            "required_binaries": ["xtb"],
            "env_vars": {},
        },
    )
    registry.set_active("xtb", "conda-6.7.1")

    monkeypatch.setattr(engine_installer, "remove_env", lambda env_name, _app_data_dir: removed.append(env_name))

    engine_installer.uninstall_engine("xtb", "conda-6.7.1", app_data_dir=home)

    assert removed == ["xtb-6.7.1"]
    updated = EngineRegistry(registry_path=home / "config" / "engines.json")
    assert updated.list_installations("xtb") == []


def test_python_engine_install_adds_python_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "home"
    captured_packages: list[str] = []

    def fake_create_env(env_name: str, packages: list[str], channels: list[str], app_data_dir: Path) -> Path:
        captured_packages.extend(packages)
        env_dir = app_data_dir / "micromamba" / "envs" / env_name
        (env_dir / "bin").mkdir(parents=True, exist_ok=True)
        (env_dir / "bin" / "python").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        return env_dir

    monkeypatch.setattr(engine_installer, "create_env", fake_create_env)
    monkeypatch.setattr(engine_installer, "_verify_python_engine", lambda _py, _mod: "2.7.0")

    installation = engine_installer.install_engine_conda("pyscf", version="2.7", app_data_dir=home)

    assert "python=3.12" in captured_packages
    assert "pyscf=2.7" in captured_packages
    assert installation["source"] == "micromamba"
    assert installation.get("python_executable")


def test_list_installable_engines_flags_manual_only() -> None:
    items = {row["engine"]: row for row in engine_installer.list_installable_engines()}
    assert items["xtb"]["manual_only"] is False
    assert items["vasp"]["manual_only"] is True
