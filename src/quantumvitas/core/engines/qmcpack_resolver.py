"""QMCPACK binary path resolution.

Resolves the path to the QMCPACK binary following priority:
1. Environment variable QMATS_QMCPACK_BIN
2. Spack: $(spack location -i qmcpack)/bin/qmcpack
3. Conda: $CONDA_PREFIX/bin/qmcpack
4. System paths: /usr/local/bin/qmcpack, /usr/bin/qmcpack
5. PATH: qmcpack
"""
from __future__ import annotations

import os
from pathlib import Path
from shutil import which


def resolve_qmcpack_bin() -> Path:
    """
    Resolve QMCPACK binary path.

    Search order:
    1. QMATS_QMCPACK_BIN environment variable
    2. Conda: $CONDA_PREFIX/bin/qmcpack
    3. System paths: /usr/local/bin/qmcpack, /usr/bin/qmcpack
    4. PATH: qmcpack

    Returns:
        Path to QMCPACK binary

    Raises:
        FileNotFoundError: No QMCPACK binary found
    """
    # 1. Check environment variable
    env_bin = os.environ.get("QMATS_QMCPACK_BIN")
    if env_bin:
        bin_path = Path(env_bin)
        if bin_path.exists() and bin_path.is_file():
            return bin_path
        raise FileNotFoundError(f"QMATS_QMCPACK_BIN points to invalid path: {env_bin}")

    # 2. Check Conda
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        conda_bin = Path(conda_prefix) / "bin" / "qmcpack"
        if conda_bin.exists() and conda_bin.is_file():
            return conda_bin

    # 3. Check system paths
    system_paths = [
        Path("/usr/local/bin/qmcpack"),
        Path("/usr/bin/qmcpack"),
        Path("/opt/homebrew/bin/qmcpack"),
    ]
    for sys_path in system_paths:
        if sys_path.exists() and sys_path.is_file():
            return sys_path

    # 4. Check PATH
    path_bin = which("qmcpack")
    if path_bin:
        return Path(path_bin)

    # Not found
    checked_locations = [
        "Environment variable QMATS_QMCPACK_BIN (not set)",
        f"Conda: $CONDA_PREFIX/bin/qmcpack",
        "System: /usr/local/bin/qmcpack, /usr/bin/qmcpack",
        "PATH: qmcpack",
    ]

    raise FileNotFoundError(
        f"QMCPACK not found. Checked:\n"
        + "\n".join(f"  - {loc}" for loc in checked_locations)
        + f"\nInstall QMCPACK or set QMATS_QMCPACK_BIN to the qmcpack binary path."
    )
