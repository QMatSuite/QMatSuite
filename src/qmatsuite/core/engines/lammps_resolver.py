"""LAMMPS binary path resolution.

Resolves the path to the LAMMPS binary following priority:
1. Environment variable QMATS_LAMMPS_BIN
2. Homebrew: /opt/homebrew/opt/lammps/bin/lmp_{variant}
3. Linuxbrew: /home/linuxbrew/.linuxbrew/opt/lammps/bin/lmp_{variant}
4. apt: /usr/bin/lmp or /usr/bin/lmp_mpi
5. Conda: $CONDA_PREFIX/bin/lmp
6. PATH: lmp_{variant}, lmp_mpi, lmp_serial, lmp
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from shutil import which


def _get_registry_lammps_bin(variant: str) -> Path | None:
    """Resolve LAMMPS executable from active engines.json installation."""
    try:
        from qmatsuite.core.engines.engine_registry import resolve_active_binary

        preferred = "lmp_mpi" if variant == "mpi" else "lmp"
        resolved = resolve_active_binary("lammps", binary_name=preferred)
        if resolved and resolved.is_file():
            return resolved
    except Exception:
        return None
    return None


def resolve_lammps_bin(variant: str = "serial") -> Path:
    """
    Resolve LAMMPS binary path.
    
    Search order:
    1. QMATS_LAMMPS_BIN environment variable
    2. Homebrew: /opt/homebrew/opt/lammps/bin/lmp_{variant}
    3. Linuxbrew: /home/linuxbrew/.linuxbrew/opt/lammps/bin/lmp_{variant}
    4. apt: /usr/bin/lmp or /usr/bin/lmp_mpi
    5. Conda: $CONDA_PREFIX/bin/lmp
    6. PATH: lmp_{variant}, lmp_mpi, lmp_serial, lmp
    
    Args:
        variant: LAMMPS variant ("serial", "mpi"). Default "serial".
    
    Returns:
        Path to LAMMPS binary
    
    Raises:
        FileNotFoundError: No LAMMPS binary found
    """
    registry_bin = _get_registry_lammps_bin(variant)
    if registry_bin is not None:
        return registry_bin

    # 1. Check environment variable
    env_bin = os.environ.get("QMATS_LAMMPS_BIN")
    if env_bin:
        bin_path = Path(env_bin)
        if bin_path.exists() and bin_path.is_file():
            return bin_path
        raise FileNotFoundError(f"QMATS_LAMMPS_BIN points to invalid path: {env_bin}")
    
    # 2. Check Homebrew (macOS)
    brew_prefixes = [
        Path("/opt/homebrew/opt/lammps"),  # Apple Silicon
        Path("/usr/local/opt/lammps"),     # Intel Mac
    ]
    for brew_prefix in brew_prefixes:
        if brew_prefix.exists():
            bin_name = f"lmp_{variant}" if variant != "serial" else "lmp_serial"
            bin_path = brew_prefix / "bin" / bin_name
            if bin_path.exists() and bin_path.is_file():
                return bin_path
            # Also try lmp_mpi if variant is mpi
            if variant == "mpi":
                bin_path = brew_prefix / "bin" / "lmp_mpi"
                if bin_path.exists() and bin_path.is_file():
                    return bin_path
    
    # 3. Check Linuxbrew
    linuxbrew_prefix = Path("/home/linuxbrew/.linuxbrew/opt/lammps")
    if linuxbrew_prefix.exists():
        bin_name = f"lmp_{variant}" if variant != "serial" else "lmp_serial"
        bin_path = linuxbrew_prefix / "bin" / bin_name
        if bin_path.exists() and bin_path.is_file():
            return bin_path
    
    # 4. Check apt (Ubuntu/Debian)
    apt_paths = [
        Path("/usr/bin/lmp"),
        Path("/usr/bin/lmp_mpi"),
    ]
    for apt_path in apt_paths:
        if apt_path.exists() and apt_path.is_file():
            return apt_path
    
    # 5. Check Conda
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        conda_bin = Path(conda_prefix) / "bin" / "lmp"
        if conda_bin.exists() and conda_bin.is_file():
            return conda_bin
    
    # 6. Check PATH
    path_names = []
    if variant == "mpi":
        path_names = ["lmp_mpi", "lmp"]
    else:
        path_names = ["lmp_serial", "lmp"]
    
    for bin_name in path_names:
        path_bin = which(bin_name)
        if path_bin:
            return Path(path_bin)
    
    # Not found
    checked_locations = [
        f"Environment variable QMATS_LAMMPS_BIN (not set)",
        f"Homebrew: /opt/homebrew/opt/lammps/bin/lmp_{variant}",
        f"Linuxbrew: /home/linuxbrew/.linuxbrew/opt/lammps/bin/lmp_{variant}",
        f"apt: /usr/bin/lmp or /usr/bin/lmp_mpi",
        f"Conda: $CONDA_PREFIX/bin/lmp",
        f"PATH: {', '.join(path_names)}",
    ]
    
    raise FileNotFoundError(
        f"LAMMPS ({variant}) not found. Checked:\n"
        + "\n".join(f"  - {loc}" for loc in checked_locations) +
        f"\nInstall LAMMPS or set QMATS_LAMMPS_BIN to the lmp binary path."
    )
