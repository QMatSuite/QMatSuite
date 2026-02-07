"""QMCPACK binary path resolution.

Resolves the path to the QMCPACK binary following priority:
1. Environment variable QMATS_QMCPACK_BIN
2. .qmatsuite/engines/qmcpack/*/bin/qmcpack (home and cwd)
3. Conda: $CONDA_PREFIX/bin/qmcpack
4. System paths: /usr/local/bin/qmcpack, /usr/bin/qmcpack
5. PATH: qmcpack
"""
from __future__ import annotations

import os
from pathlib import Path
from shutil import which


def _search_qmatsuite_engines(binary_name: str, engine_subdir: str) -> Path | None:
    """Search .qmatsuite/engines/<engine_subdir>/*/bin/<binary_name>."""
    search_roots = []

    # Project-local via centralized repo root detection
    try:
        from quantumvitas.core.engines.discovery import _find_repo_root
        repo_root = _find_repo_root()
        if repo_root:
            search_roots.append(repo_root / ".qmatsuite" / "engines" / engine_subdir)
    except ImportError:
        pass

    # CWD-relative
    cwd_candidate = Path.cwd() / ".qmatsuite" / "engines" / engine_subdir
    if cwd_candidate not in search_roots:
        search_roots.append(cwd_candidate)

    # Home directory
    home_candidate = Path.home() / ".qmatsuite" / "engines" / engine_subdir
    if home_candidate not in search_roots:
        search_roots.append(home_candidate)

    for root in search_roots:
        if root.is_dir():
            for candidate in sorted(root.iterdir(), reverse=True):
                bin_path = candidate / "bin" / binary_name
                if bin_path.is_file():
                    return bin_path
    return None


def resolve_qmcpack_bin() -> Path:
    """
    Resolve QMCPACK binary path.

    Search order:
    1. QMATS_QMCPACK_BIN environment variable
    2. .qmatsuite/engines/qmcpack/*/bin/qmcpack (home and cwd)
    3. Conda: $CONDA_PREFIX/bin/qmcpack
    4. System paths: /usr/local/bin/qmcpack, /usr/bin/qmcpack
    5. PATH: qmcpack

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

    # 2. Check .qmatsuite/engines/
    engines_bin = _search_qmatsuite_engines("qmcpack", "qmcpack")
    if engines_bin:
        return engines_bin

    # 3. Check Conda
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        conda_bin = Path(conda_prefix) / "bin" / "qmcpack"
        if conda_bin.exists() and conda_bin.is_file():
            return conda_bin

    # 4. Check system paths
    system_paths = [
        Path("/usr/local/bin/qmcpack"),
        Path("/usr/bin/qmcpack"),
        Path("/opt/homebrew/bin/qmcpack"),
    ]
    for sys_path in system_paths:
        if sys_path.exists() and sys_path.is_file():
            return sys_path

    # 5. Check PATH
    path_bin = which("qmcpack")
    if path_bin:
        return Path(path_bin)

    # Not found
    checked_locations = [
        "Environment variable QMATS_QMCPACK_BIN (not set)",
        ".qmatsuite/engines/qmcpack/*/bin/qmcpack",
        f"Conda: $CONDA_PREFIX/bin/qmcpack",
        "System: /usr/local/bin/qmcpack, /usr/bin/qmcpack",
        "PATH: qmcpack",
    ]

    raise FileNotFoundError(
        f"QMCPACK not found. Checked:\n"
        + "\n".join(f"  - {loc}" for loc in checked_locations)
        + f"\nInstall QMCPACK or set QMATS_QMCPACK_BIN to the qmcpack binary path."
    )


def resolve_pw2qmcpack_bin() -> Path:
    """
    Resolve pw2qmcpack.x binary path.

    Search order:
    1. QMATS_PW2QMCPACK_BIN environment variable
    2. .qmatsuite/engines/qe/*/bin/pw2qmcpack.x (home and cwd)
    3. Same directory as QE pw.x (via resolve_qe_bin_dir)
    4. PATH: pw2qmcpack.x

    Returns:
        Path to pw2qmcpack.x binary

    Raises:
        FileNotFoundError: No pw2qmcpack.x binary found
    """
    # 1. Check environment variable
    env_bin = os.environ.get("QMATS_PW2QMCPACK_BIN")
    if env_bin:
        bin_path = Path(env_bin)
        if bin_path.exists() and bin_path.is_file():
            return bin_path
        raise FileNotFoundError(f"QMATS_PW2QMCPACK_BIN points to invalid path: {env_bin}")

    # 2. Check .qmatsuite/engines/qe/*/bin/
    engines_bin = _search_qmatsuite_engines("pw2qmcpack.x", "qe")
    if engines_bin:
        return engines_bin

    # 3. Check alongside QE pw.x
    try:
        from quantumvitas.core.engines.qe_resolver import resolve_qe_bin_dir
        qe_bin_dir = resolve_qe_bin_dir()
        pw2q = qe_bin_dir / "pw2qmcpack.x"
        if pw2q.is_file():
            return pw2q
    except (ImportError, FileNotFoundError):
        pass

    # 4. Check PATH
    path_bin = which("pw2qmcpack.x")
    if path_bin:
        return Path(path_bin)

    checked_locations = [
        "Environment variable QMATS_PW2QMCPACK_BIN (not set)",
        ".qmatsuite/engines/qe/*/bin/pw2qmcpack.x",
        "Alongside QE pw.x",
        "PATH: pw2qmcpack.x",
    ]

    raise FileNotFoundError(
        f"pw2qmcpack.x not found. Checked:\n"
        + "\n".join(f"  - {loc}" for loc in checked_locations)
        + f"\nBuild pw2qmcpack or set QMATS_PW2QMCPACK_BIN to the binary path."
    )
