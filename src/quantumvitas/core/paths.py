"""
QMatSuite path utilities.

This module provides centralized path resolution for QMatSuite data directories
across development, pip-installed, and Electron-bundled environments.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache for repo root lookup to avoid repeated filesystem walks
_repo_root_cache: Optional[Path] = None
_repo_root_checked = False


def _ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) if it does not exist."""
    resolved = path.expanduser()
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _try_find_repo_root() -> Optional[Path]:
    """Best-effort repo root discovery for dev mode."""
    global _repo_root_cache
    global _repo_root_checked

    if _repo_root_checked:
        return _repo_root_cache

    current = Path(__file__).resolve().parent
    for _ in range(12):
        if (current / "pyproject.toml").exists() and (current / "src" / "quantumvitas").exists():
            _repo_root_cache = current.resolve()
            _repo_root_checked = True
            return _repo_root_cache
        parent = current.parent
        if parent == current:
            break
        current = parent

    _repo_root_cache = None
    _repo_root_checked = True
    return None


def get_repo_root() -> Optional[Path]:
    """
    Get the QMatSuite repository root directory in dev mode.

    Returns:
        Path to repository root when running from a source checkout,
        otherwise ``None``.
    """
    return _try_find_repo_root()


def _is_electron_bundle() -> bool:
    """Return True when running inside the Electron-distributed runtime."""
    return os.environ.get("QMATSUITE_ELECTRON") == "1"


def _electron_app_data_dir() -> Path:
    """Resolve platform app-data directory for Electron distribution."""
    if sys.platform == "darwin":
        return _ensure_dir(Path.home() / "Library" / "Application Support" / "QMatSuite")
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return _ensure_dir(Path(local_app_data) / "QMatSuite")

    xdg_data_home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return _ensure_dir(Path(xdg_data_home) / "qmatsuite")


def _electron_cache_dir() -> Path:
    """Resolve platform cache directory for Electron distribution."""
    if sys.platform == "darwin":
        return _ensure_dir(Path.home() / "Library" / "Caches" / "QMatSuite")
    if sys.platform == "win32":
        local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        return _ensure_dir(Path(local_app_data) / "QMatSuite" / "cache")

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    return _ensure_dir(Path(xdg_cache_home) / "qmatsuite")


def get_app_data_dir() -> Path:
    """
    Resolve the QMatSuite app data directory.

    Resolution order:
    1. ``QMATSUITE_HOME``
    2. Dev mode (repo checkout): ``<repo_root>/.qmatsuite``
    3. Electron mode (``QMATSUITE_ELECTRON=1``): platform app-data directory
    4. Fallback: ``~/.qmatsuite``
    """
    env_home = os.environ.get("QMATSUITE_HOME")
    if env_home:
        return _ensure_dir(Path(env_home))

    repo_root = _try_find_repo_root()
    if repo_root is not None:
        return _ensure_dir(repo_root / ".qmatsuite")

    if _is_electron_bundle():
        return _electron_app_data_dir()

    return _ensure_dir(Path.home() / ".qmatsuite")


def get_cache_dir() -> Path:
    """
    Resolve the QMatSuite cache/scratch directory.

    Resolution order:
    1. ``QMATSUITE_CACHE``
    2. Dev mode (repo checkout): ``<repo_root>/.tmp``
    3. Electron mode (``QMATSUITE_ELECTRON=1``): platform cache directory
    4. Fallback: ``<app_data_dir>/.tmp``
    """
    env_cache = os.environ.get("QMATSUITE_CACHE")
    if env_cache:
        return _ensure_dir(Path(env_cache))

    repo_root = _try_find_repo_root()
    if repo_root is not None:
        return _ensure_dir(repo_root / ".tmp")

    if _is_electron_bundle():
        return _electron_cache_dir()

    return _ensure_dir(get_app_data_dir() / ".tmp")


def get_tmp_dir() -> Path:
    """Backward-compatible alias for cache/scratch root."""
    return get_cache_dir()


def get_qmatsuite_home_root() -> Path:
    """Backward-compatible alias for app data root."""
    return get_app_data_dir()


def get_qmatsuite_tmp_root() -> Path:
    """Backward-compatible alias for cache/scratch root."""
    return get_cache_dir()


# Home directory helpers (persistent assets)
def home_config_dir() -> Path:
    """Get app-data config directory."""
    return _ensure_dir(get_app_data_dir() / "config")


def home_engines_dir() -> Path:
    """Get app-data engines directory."""
    return _ensure_dir(get_app_data_dir() / "engines")


def home_seeds_dir() -> Path:
    """Get app-data seeds directory."""
    return _ensure_dir(get_app_data_dir() / "seeds")


def home_libraries_dir() -> Path:
    """Get app-data libraries directory."""
    return _ensure_dir(get_app_data_dir() / "libraries")


def home_logs_dir() -> Path:
    """Get app-data logs directory."""
    return _ensure_dir(get_app_data_dir() / "logs")


# QE-specific subdirectories
def home_qe_engines_dir() -> Path:
    """Get app-data QE engines directory."""
    return _ensure_dir(home_engines_dir() / "qe")


def home_qe_seeds_dir() -> Path:
    """Get app-data QE seeds directory."""
    return _ensure_dir(home_seeds_dir() / "qe")


def home_pseudo_libraries_dir() -> Path:
    """Get app-data pseudo libraries directory."""
    return _ensure_dir(home_libraries_dir() / "pseudo")


def home_pseudo_seeds_dir() -> Path:
    """Get app-data pseudo seeds directory."""
    return _ensure_dir(home_seeds_dir() / "pseudo")


# Temporary directory helpers (scratch space)
def tmp_runs_dir() -> Path:
    """Get cache runs directory."""
    return _ensure_dir(get_cache_dir() / "runs")


def tmp_downloads_dir() -> Path:
    """Get cache downloads directory."""
    return _ensure_dir(get_cache_dir() / "downloads")


def tmp_unpack_dir() -> Path:
    """Get cache unpack directory."""
    return _ensure_dir(get_cache_dir() / "unpack")


def tmp_probe_dir() -> Path:
    """Get cache probe directory."""
    return _ensure_dir(get_cache_dir() / "probe")


def tmp_locks_dir() -> Path:
    """Get cache locks directory."""
    return _ensure_dir(get_cache_dir() / "locks")


def get_settings_json_path() -> Path:
    """Get path to settings.json in app-data config directory."""
    return home_config_dir() / "settings.json"
