"""Tests for path resolution modes in qmatsuite.core.paths."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import qmatsuite.core.paths as paths


def _reset_repo_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset module-level repo discovery cache between tests."""
    monkeypatch.setattr(paths, "_repo_root_cache", None)
    monkeypatch.setattr(paths, "_repo_root_checked", False)


def test_get_app_data_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """QMATSUITE_HOME should take highest precedence."""
    _reset_repo_cache(monkeypatch)
    custom_home = tmp_path / "custom-home"

    monkeypatch.setattr(paths, "_try_find_repo_root", lambda: None)
    monkeypatch.setenv("QMATSUITE_HOME", str(custom_home))
    monkeypatch.delenv("QMATSUITE_ELECTRON", raising=False)

    assert paths.get_app_data_dir() == custom_home
    assert custom_home.is_dir()


def test_get_app_data_dir_dev_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Dev mode should resolve to <repo>/.qmatsuite."""
    _reset_repo_cache(monkeypatch)
    fake_repo = tmp_path / "repo"

    monkeypatch.setattr(paths, "_try_find_repo_root", lambda: fake_repo)
    monkeypatch.delenv("QMATSUITE_HOME", raising=False)
    monkeypatch.delenv("QMATSUITE_ELECTRON", raising=False)

    resolved = paths.get_app_data_dir()
    assert resolved == fake_repo / ".qmatsuite"
    assert resolved.is_dir()


def test_get_app_data_dir_electron_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Electron mode should use platform-specific app-data paths."""
    _reset_repo_cache(monkeypatch)
    fake_home = tmp_path / "home"

    monkeypatch.setattr(paths, "_try_find_repo_root", lambda: None)
    monkeypatch.delenv("QMATSUITE_HOME", raising=False)
    monkeypatch.setenv("QMATSUITE_ELECTRON", "1")
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))

    resolved = paths.get_app_data_dir()
    if os.name == "nt":
        expected = Path(os.environ["LOCALAPPDATA"]) / "QMatSuite"
    elif paths.sys.platform == "darwin":
        expected = fake_home / "Library" / "Application Support" / "QMatSuite"
    else:
        expected = Path(os.environ["XDG_DATA_HOME"]) / "qmatsuite"

    assert resolved == expected
    assert resolved.is_dir()


def test_get_app_data_dir_pip_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Without env/repo/electron, fallback should be ~/.qmatsuite."""
    _reset_repo_cache(monkeypatch)
    fake_home = tmp_path / "home"

    monkeypatch.setattr(paths, "_try_find_repo_root", lambda: None)
    monkeypatch.delenv("QMATSUITE_HOME", raising=False)
    monkeypatch.delenv("QMATSUITE_ELECTRON", raising=False)
    monkeypatch.setenv("HOME", str(fake_home))

    resolved = paths.get_app_data_dir()
    assert resolved == fake_home / ".qmatsuite"
    assert resolved.is_dir()


def test_get_cache_dir_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """QMATSUITE_CACHE should override all cache path modes."""
    _reset_repo_cache(monkeypatch)
    custom_cache = tmp_path / "custom-cache"

    monkeypatch.setattr(paths, "_try_find_repo_root", lambda: None)
    monkeypatch.setenv("QMATSUITE_CACHE", str(custom_cache))

    resolved = paths.get_cache_dir()
    assert resolved == custom_cache
    assert resolved.is_dir()


def test_derived_dirs_are_app_data_subdirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Derived helpers should all resolve under get_app_data_dir()."""
    _reset_repo_cache(monkeypatch)
    fake_repo = tmp_path / "repo"

    monkeypatch.setattr(paths, "_try_find_repo_root", lambda: fake_repo)
    monkeypatch.delenv("QMATSUITE_HOME", raising=False)
    monkeypatch.delenv("QMATSUITE_ELECTRON", raising=False)

    app_data = paths.get_app_data_dir()
    assert paths.home_config_dir() == app_data / "config"
    assert paths.home_engines_dir() == app_data / "engines"
    assert paths.home_pseudo_libraries_dir() == app_data / "libraries" / "pseudo"
    assert paths.home_pseudo_seeds_dir() == app_data / "seeds" / "pseudo"
