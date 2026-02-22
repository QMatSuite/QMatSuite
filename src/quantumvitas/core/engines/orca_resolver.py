"""ORCA path resolution.

Resolves the path to the ORCA binary following priority:
1. Environment variable QMATSUITE_ORCA_BIN
2. Managed engines under <app_data>/engines/orca/
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


# Known bundled ORCA versions (ordered by preference - newest first)
BUNDLED_VERSIONS = [
    "orca_6_1_1_macosx_arm64_openmpi411",
    "orca_6_1_0_macosx_arm64_openmpi411",
    "orca_6_0_0_macosx_arm64_openmpi411",
]


def _bundled_orca_bases() -> list[Path]:
    """Return candidate managed ORCA roots in search priority order."""
    bases: list[Path] = []

    # Primary: managed app-data engines root (dev + distribution aware).
    try:
        from quantumvitas.core.paths import home_engines_dir

        managed = home_engines_dir() / "orca"
        if managed.exists():
            bases.append(managed)
    except Exception:
        pass

    # Legacy fallback: repo-local .qmatsuite/engines/orca.
    try:
        from quantumvitas.core.engines.discovery import _find_repo_root

        repo_root = _find_repo_root()
        if repo_root:
            repo_orca = repo_root / ".qmatsuite" / "engines" / "orca"
            if repo_orca.exists() and repo_orca not in bases:
                bases.append(repo_orca)
    except Exception:
        pass

    return bases


def resolve_orca_bin() -> Path:
    """
    Resolve ORCA binary path.

    Resolution order:
    1. QMATSUITE_ORCA_BIN environment variable
    2. Managed ORCA in <app_data>/engines/orca/

    Returns:
        Path to ORCA binary

    Raises:
        RuntimeError: If ORCA cannot be found
    """
    # 1. Check environment variable
    env_bin = os.environ.get("QMATSUITE_ORCA_BIN")
    if env_bin:
        bin_path = Path(env_bin)
        if bin_path.exists() and bin_path.is_file():
            return bin_path
        raise RuntimeError(f"QMATSUITE_ORCA_BIN points to invalid path: {env_bin}")

    # 2. Check bundled locations (multiple bases)
    checked_locations = []
    for bundled_base in _bundled_orca_bases():
        checked_locations.append(str(bundled_base))

        # First check known versions
        for version_dir in BUNDLED_VERSIONS:
            orca_dir = bundled_base / version_dir
            if orca_dir.exists():
                orca_binary = orca_dir / "orca"
                if orca_binary.exists() and orca_binary.is_file():
                    return orca_binary

        # Then try to find any ORCA installation
        if bundled_base.exists():
            for subdir in sorted(bundled_base.iterdir(), reverse=True):
                if subdir.is_dir() and subdir.name.startswith("orca_"):
                    orca_binary = subdir / "orca"
                    if orca_binary.exists() and orca_binary.is_file():
                        return orca_binary

    raise RuntimeError(
        f"ORCA not found. Checked:\n"
        f"  - Environment variable QMATSUITE_ORCA_BIN (not set)\n"
        f"  - Bundled locations: {', '.join(checked_locations)}\n"
        f"Install ORCA or set QMATSUITE_ORCA_BIN to the orca binary path."
    )


def resolve_orca_bin_dir() -> Path:
    """
    Resolve ORCA installation directory.

    Returns:
        Path to directory containing ORCA binary and helper executables

    Raises:
        RuntimeError: If ORCA cannot be found
    """
    orca_bin = resolve_orca_bin()
    return orca_bin.parent


def get_orca_version(orca_bin: Optional[Path] = None) -> Optional[str]:
    """
    Get ORCA version string.

    Args:
        orca_bin: Path to ORCA binary (uses default resolution if not provided)

    Returns:
        Version string or None if cannot be determined
    """
    import subprocess

    if orca_bin is None:
        try:
            orca_bin = resolve_orca_bin()
        except RuntimeError:
            return None

    try:
        # ORCA prints version info when run without arguments
        result = subprocess.run(
            [str(orca_bin)],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout + result.stderr
        # Look for version line
        for line in output.split('\n'):
            if 'ORCA' in line and ('Version' in line or any(c.isdigit() for c in line)):
                return line.strip()
        return None
    except Exception:
        return None


def validate_orca_bin(orca_bin: Path) -> tuple[bool, str]:
    """
    Validate ORCA binary.

    Args:
        orca_bin: Path to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if not orca_bin.exists():
        return False, f"ORCA binary not found: {orca_bin}"

    if not orca_bin.is_file():
        return False, f"ORCA path is not a file: {orca_bin}"

    # Check if executable
    if not os.access(orca_bin, os.X_OK):
        return False, f"ORCA binary is not executable: {orca_bin}"

    return True, "OK"
