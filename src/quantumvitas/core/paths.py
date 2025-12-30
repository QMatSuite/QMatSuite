"""
QMatSuite path utilities.

This module provides centralized path resolution for QMatSuite data directories
according to CONSTITUTION_ZH.md section 9.

All paths are relative to the repository root in dev/CI stage.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache for repo root to avoid repeated lookups
_repo_root_cache: Optional[Path] = None


def get_repo_root() -> Path:
    """
    Get the QMatSuite repository root directory.
    
    The repo root is identified by the presence of:
    - pyproject.toml
    - src/quantumvitas/
    
    Returns:
        Path to repository root
        
    Raises:
        RuntimeError: If repository root cannot be found
    """
    global _repo_root_cache
    
    if _repo_root_cache is not None:
        return _repo_root_cache
    
    # Start from this file and walk up
    current = Path(__file__).parent
    while current != current.parent:
        if (current / "pyproject.toml").exists() and (current / "src" / "quantumvitas").exists():
            _repo_root_cache = current.resolve()
            return _repo_root_cache
        current = current.parent
    
    raise RuntimeError(
        "Could not find QMatSuite repository root. "
        "Expected to find pyproject.toml and src/quantumvitas/ in parent directories."
    )


def get_qmatsuite_home_root() -> Path:
    """
    Get the QMatSuite home root directory (.qmatsuite/).
    
    This is the persistent, migratable, reproducible assets directory.
    
    Returns:
        Path to .qmatsuite/ directory (created if needed)
    """
    root = get_repo_root()
    home = root / ".qmatsuite"
    home.mkdir(parents=True, exist_ok=True)
    return home


def get_qmatsuite_tmp_root() -> Path:
    """
    Get the QMatSuite temporary root directory (.tmp/).
    
    This is the scratch directory that can be deleted anytime.
    
    Returns:
        Path to .tmp/ directory (created if needed)
    """
    root = get_repo_root()
    tmp = root / ".tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    return tmp


# Home directory helpers (persistent assets)
def home_config_dir() -> Path:
    """Get .qmatsuite/config/ directory."""
    home = get_qmatsuite_home_root()
    config_dir = home / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def home_engines_dir() -> Path:
    """Get .qmatsuite/engines/ directory."""
    home = get_qmatsuite_home_root()
    engines_dir = home / "engines"
    engines_dir.mkdir(parents=True, exist_ok=True)
    return engines_dir


def home_seeds_dir() -> Path:
    """Get .qmatsuite/seeds/ directory."""
    home = get_qmatsuite_home_root()
    seeds_dir = home / "seeds"
    seeds_dir.mkdir(parents=True, exist_ok=True)
    return seeds_dir


def home_libraries_dir() -> Path:
    """Get .qmatsuite/libraries/ directory."""
    home = get_qmatsuite_home_root()
    libraries_dir = home / "libraries"
    libraries_dir.mkdir(parents=True, exist_ok=True)
    return libraries_dir


def home_logs_dir() -> Path:
    """Get .qmatsuite/logs/ directory."""
    home = get_qmatsuite_home_root()
    logs_dir = home / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


# QE-specific subdirectories
def home_qe_engines_dir() -> Path:
    """Get .qmatsuite/engines/qe/ directory."""
    engines = home_engines_dir()
    qe_dir = engines / "qe"
    qe_dir.mkdir(parents=True, exist_ok=True)
    return qe_dir


def home_qe_seeds_dir() -> Path:
    """Get .qmatsuite/seeds/qe/ directory."""
    seeds = home_seeds_dir()
    qe_dir = seeds / "qe"
    qe_dir.mkdir(parents=True, exist_ok=True)
    return qe_dir


def home_pseudo_libraries_dir() -> Path:
    """Get .qmatsuite/libraries/pseudo/ directory."""
    libraries = home_libraries_dir()
    pseudo_dir = libraries / "pseudo"
    pseudo_dir.mkdir(parents=True, exist_ok=True)
    return pseudo_dir


def home_pseudo_seeds_dir() -> Path:
    """Get .qmatsuite/seeds/pseudo/ directory."""
    seeds = home_seeds_dir()
    pseudo_dir = seeds / "pseudo"
    pseudo_dir.mkdir(parents=True, exist_ok=True)
    return pseudo_dir


# Temporary directory helpers (scratch space)
def tmp_runs_dir() -> Path:
    """Get .tmp/runs/ directory."""
    tmp = get_qmatsuite_tmp_root()
    runs_dir = tmp / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


def tmp_downloads_dir() -> Path:
    """Get .tmp/downloads/ directory."""
    tmp = get_qmatsuite_tmp_root()
    downloads_dir = tmp / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return downloads_dir


def tmp_unpack_dir() -> Path:
    """Get .tmp/unpack/ directory."""
    tmp = get_qmatsuite_tmp_root()
    unpack_dir = tmp / "unpack"
    unpack_dir.mkdir(parents=True, exist_ok=True)
    return unpack_dir


def tmp_probe_dir() -> Path:
    """Get .tmp/probe/ directory."""
    tmp = get_qmatsuite_tmp_root()
    probe_dir = tmp / "probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    return probe_dir


def tmp_locks_dir() -> Path:
    """Get .tmp/locks/ directory."""
    tmp = get_qmatsuite_tmp_root()
    locks_dir = tmp / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    return locks_dir


def get_settings_json_path() -> Path:
    """Get path to .qmatsuite/config/settings.json."""
    return home_config_dir() / "settings.json"

