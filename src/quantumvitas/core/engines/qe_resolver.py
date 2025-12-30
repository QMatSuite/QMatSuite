"""
QE Engine Resolution (Two-State Model).

This module provides the single entrypoint for QE bin directory resolution.
Two-state model:
1. If settings.qe.bin_dir is set: use that external QE bin directory
2. If settings.qe.bin_dir is null: auto-select internal QE from .qmatsuite/engines/qe/**/bin
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from ..paths import get_repo_root, home_qe_engines_dir
from quantumvitas.core.settings import load_settings

logger = logging.getLogger(__name__)


def validate_qe_bin_dir(bin_dir: Path) -> None:
    """
    Validate that a QE bin directory contains pw executable.
    
    Args:
        bin_dir: Path to QE bin directory
        
    Raises:
        RuntimeError: If bin_dir is invalid or missing pw executable
    """
    if not bin_dir.exists():
        raise RuntimeError(
            f"QE bin directory does not exist: {bin_dir}\n"
            f"This setting is machine-specific. Please set a valid QE bin directory in Settings or choose internal QE."
        )
    
    if not bin_dir.is_dir():
        raise RuntimeError(
            f"QE bin directory is not a directory: {bin_dir}\n"
            f"This setting is machine-specific. Please set a valid QE bin directory in Settings or choose internal QE."
        )
    
    # Check for pw executable (pw.x or pw.x.exe)
    pw_x = bin_dir / "pw.x"
    pw_exe = bin_dir / "pw.x.exe"
    
    if not pw_x.exists() and not pw_exe.exists():
        raise RuntimeError(
            f"QE bin directory is invalid or missing pw executable: {bin_dir}\n"
            f"Expected to find pw.x or pw.x.exe in this directory.\n"
            f"This setting is machine-specific. Please set a valid QE bin directory in Settings or choose internal QE."
        )


def find_internal_qe_bin_dir() -> Optional[Path]:
    """
    Find internal QE bin directory by auto-selecting from .qmatsuite/engines/qe/**/bin.
    
    Selection rule (deterministic):
    1. Find all directories matching .qmatsuite/engines/qe/**/bin that contain pw* (pw.x or pw.x.exe)
    2. Primary sort: by parent engine folder mtime (most recent first)
       - If META.json exists in parent folder, use created_at/version from it if available
    3. Secondary sort (tie-break): lexicographically highest full path
    
    Returns:
        Path to selected internal QE bin directory, or None if none found
    """
    repo_root = get_repo_root()
    engines_base = home_qe_engines_dir()
    
    if not engines_base.exists():
        return None
    
    candidates: list[tuple[Path, float, str]] = []  # (bin_dir, sort_key, tie_break_path)
    
    # Find all bin directories with pw executable
    for engine_dir in engines_base.rglob("bin"):
        if not engine_dir.is_dir():
            continue
        
        # Check for pw executable
        pw_x = engine_dir / "pw.x"
        pw_exe = engine_dir / "pw.x.exe"
        
        if not pw_x.exists() and not pw_exe.exists():
            continue
        
        # Get parent engine folder
        parent_engine = engine_dir.parent
        
        # Primary sort key: mtime of parent engine folder
        try:
            mtime = parent_engine.stat().st_mtime
        except OSError:
            mtime = 0.0
        
        # Check for META.json in parent folder
        meta_json = parent_engine / "META.json"
        if meta_json.exists():
            try:
                import json
                with open(meta_json, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    # Prefer created_at timestamp if available
                    if "created_at" in meta:
                        try:
                            from datetime import datetime
                            created_at = datetime.fromisoformat(meta["created_at"])
                            mtime = created_at.timestamp()
                        except (ValueError, TypeError):
                            pass
                    # Or version string for tie-breaking
                    elif "version" in meta:
                        # Use version as secondary sort (higher version = more recent)
                        pass
            except Exception:
                # Ignore META.json parsing errors, fall back to mtime
                pass
        
        # Tie-break: lexicographically highest full path
        tie_break = str(engine_dir.resolve())
        
        candidates.append((engine_dir, mtime, tie_break))
    
    if not candidates:
        return None
    
    # Sort: primary by mtime (descending), secondary by path (descending)
    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
    
    selected = candidates[0][0]
    logger.debug(f"Selected internal QE bin directory: {selected} (from {len(candidates)} candidates)")
    
    return selected


def resolve_qe_bin_dir(settings=None) -> Path:
    """
    Resolve QE bin directory using two-state model.
    
    Args:
        settings: Optional QMatSuiteSettings instance (loads if None)
        
    Returns:
        Path to QE bin directory
        
    Raises:
        RuntimeError: If no valid QE bin directory can be resolved
    """
    if settings is None:
        settings = load_settings()
    
    # State 1: External QE (settings.qe.bin_dir is set)
    if settings.qe.bin_dir:
        bin_dir = Path(settings.qe.bin_dir).resolve()
        validate_qe_bin_dir(bin_dir)
        logger.debug(f"Using external QE bin directory: {bin_dir}")
        return bin_dir
    
    # State 2: Internal QE (auto-select from .qmatsuite/engines/qe/**/bin)
    internal_bin_dir = find_internal_qe_bin_dir()
    if internal_bin_dir:
        logger.debug(f"Using internal QE bin directory: {internal_bin_dir}")
        return internal_bin_dir
    
    # No QE found
    raise RuntimeError(
        "No internal QE found under .qmatsuite/engines/qe/**/bin.\n"
        "Install internal QE or set qe.bin_dir to an external QE bin directory in Settings."
    )

