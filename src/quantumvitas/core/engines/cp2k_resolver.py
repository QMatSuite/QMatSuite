"""CP2K binary resolver."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def find_cp2k_executable() -> Optional[Path]:
    """
    Find CP2K executable.

    Search order:
    1. CP2K_EXECUTABLE environment variable
    2. cp2k.ssmp in PATH
    3. cp2k in PATH (fallback)
    4. Homebrew location: /opt/homebrew/bin/cp2k.ssmp

    Returns:
        Path to executable, or None if not found.
    """
    # 1. Environment variable
    env_path = os.environ.get("CP2K_EXECUTABLE")
    if env_path:
        p = Path(env_path)
        if p.exists() and os.access(p, os.X_OK):
            return p

    # 2. Check PATH for all CP2K binary flavors (in preference order)
    for flavor in ("cp2k.psmp", "cp2k.popt", "cp2k.ssmp", "cp2k.sopt", "cp2k"):
        found = shutil.which(flavor)
        if found:
            return Path(found)

    # 3. Homebrew default paths
    for flavor in ("cp2k.psmp", "cp2k.ssmp", "cp2k"):
        homebrew = Path(f"/opt/homebrew/bin/{flavor}")
        if homebrew.exists():
            return homebrew

    return None


def get_cp2k_version(executable: Path) -> Optional[str]:
    """Get CP2K version string."""
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Parse version from output
        for line in result.stdout.split("\n"):
            if "CP2K version" in line:
                return line.strip()
        return result.stdout.split("\n")[0] if result.stdout else None
    except Exception:
        return None


def get_cp2k_data_dir() -> Optional[Path]:
    """
    Get CP2K data directory.

    Search order:
    1. CP2K_DATA_DIR environment variable
    2. Homebrew location: /opt/homebrew/share/cp2k/data
    3. Standard Linux location: /usr/share/cp2k/data
    
    Returns:
        Path to data directory, or None if not found.
    """
    env_dir = os.environ.get("CP2K_DATA_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p

    # Try Homebrew location (macOS)
    homebrew = Path("/opt/homebrew/share/cp2k/data")
    if homebrew.is_dir():
        return homebrew
    
    # Try standard Linux location
    linux_std = Path("/usr/share/cp2k/data")
    if linux_std.is_dir():
        return linux_std

    return None

