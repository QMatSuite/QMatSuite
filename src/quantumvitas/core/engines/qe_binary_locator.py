"""
Helper functions for locating QE binaries via engine discovery.

This module provides utilities for finding QE executables using the same
engine resolution logic used by the rest of the codebase.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from .qe_resolver import resolve_qe_bin_dir


def locate_qe_executable(executable_name: str) -> Optional[Path]:
    """
    Locate a QE executable using engine discovery.
    
    Uses the same QE bin directory resolution as the rest of the codebase
    (two-state model: external via settings, or internal from .qmatsuite/engines/qe).
    
    Args:
        executable_name: Name of executable (e.g., "pw.x", "pw2wannier90.x")
        
    Returns:
        Path to executable if found and executable, None otherwise
        
    Note:
        Does not raise exceptions if QE is not configured. Returns None instead.
        This allows tests to conditionally skip rather than fail when QE is absent.
    """
    try:
        bin_dir = resolve_qe_bin_dir()
    except RuntimeError:
        # QE not configured - return None instead of raising
        return None
    
    exe_path = bin_dir / executable_name
    
    # Check if executable exists and is executable
    if exe_path.exists() and exe_path.is_file() and os.access(exe_path, os.X_OK):
        return exe_path
    
    # Also check for .exe variant on Windows
    if os.name == "nt":
        exe_path_exe = bin_dir / f"{executable_name}.exe"
        if exe_path_exe.exists() and exe_path_exe.is_file() and os.access(exe_path_exe, os.X_OK):
            return exe_path_exe
    
    return None


def locate_pw2wannier90() -> Optional[Path]:
    """
    Locate pw2wannier90.x executable via QE engine discovery.
    
    Returns:
        Path to pw2wannier90.x if found, None otherwise
        
    Example:
        >>> pw2w = locate_pw2wannier90()
        >>> if pw2w is None:
        ...     pytest.skip("pw2wannier90.x not found via QE engine discovery")
    """
    return locate_qe_executable("pw2wannier90.x")

