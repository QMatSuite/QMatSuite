"""VASP path resolution.

Resolves the path to the VASP binary following priority:
1. Environment variable QMATS_VASP_STD_BIN
2. Managed app-data: <app_data_dir>/engines/vasp/*/bin/vasp_std
3. System PATH: vasp_std in PATH
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from shutil import which


def _get_registry_vasp_bin(variant: str) -> Optional[Path]:
    """Resolve VASP binary from active engines.json installation."""
    try:
        from quantumvitas.core.engines.engine_registry import resolve_active_binary

        preferred = f"vasp_{variant}"
        resolved = resolve_active_binary("vasp", binary_name=preferred)
        if resolved and resolved.is_file():
            return resolved
    except Exception:
        return None
    return None


def _get_repo_root() -> Optional[Path]:
    """Best-effort repo root lookup (test seam friendly)."""
    try:
        from quantumvitas.core.paths import get_repo_root

        return get_repo_root()
    except Exception:
        return None


def _get_managed_vasp_root() -> Optional[Path]:
    """Return managed VASP root under app data with repo override support."""
    # If a repo root is explicitly available (or monkeypatched in tests),
    # honor it and do not fall back to user app-data paths.
    repo_root = _get_repo_root()
    if repo_root is not None:
        return repo_root / ".qmatsuite" / "engines" / "vasp"

    try:
        from quantumvitas.core.paths import home_engines_dir

        return home_engines_dir() / "vasp"
    except Exception:
        return None


def resolve_vasp_bin(variant: str = "std") -> Path:
    """
    Resolve VASP binary path.
    
    Resolution order:
    1. Environment variable QMATS_VASP_{VARIANT}_BIN (e.g., QMATS_VASP_STD_BIN)
    2. Managed app-data: <app_data_dir>/engines/vasp/*/bin/vasp_{variant}
    3. System PATH: vasp_{variant} in PATH
    
    Args:
        variant: VASP variant ("std", "gam", "ncl"). Default "std".
    
    Returns:
        Path to VASP binary
    
    Raises:
        RuntimeError: If VASP cannot be found
    """
    registry_bin = _get_registry_vasp_bin(variant)
    if registry_bin is not None:
        return registry_bin

    # 1. Check environment variable
    env_var = f"QMATS_VASP_{variant.upper()}_BIN"
    env_bin = os.environ.get(env_var)
    if env_bin:
        bin_path = Path(env_bin)
        if bin_path.exists() and bin_path.is_file():
            return bin_path
        raise RuntimeError(f"{env_var} points to invalid path: {env_bin}")
    
    # 2. Check managed app-data location
    checked_locations = []
    managed_vasp = _get_managed_vasp_root()
    if managed_vasp is not None:
        checked_locations.append(str(managed_vasp))
        if managed_vasp.exists():
            # Look for version directories (e.g., vasp.6.5.0)
            for version_dir in sorted(managed_vasp.iterdir(), reverse=True):
                if version_dir.is_dir() and version_dir.name.startswith("vasp."):
                    bin_path = version_dir / "bin" / f"vasp_{variant}"
                    if bin_path.exists() and bin_path.is_file():
                        return bin_path

    # 3. Check system PATH
    bin_name = f"vasp_{variant}"
    path_bin = which(bin_name)
    if path_bin:
        return Path(path_bin)
    
    raise RuntimeError(
        f"VASP ({variant}) not found. Checked:\n"
        f"  - Environment variable {env_var} (not set)\n"
        f"  - Project root: {', '.join(checked_locations) if checked_locations else 'N/A'}\n"
        f"  - System PATH: {bin_name}\n"
        f"Install VASP or set {env_var} to the vasp_{variant} binary path."
    )


def get_potcar_dir(potcar_type: str = "PBE") -> Path:
    """
    Resolve POTCAR library directory.
    
    Args:
        potcar_type: POTCAR type ("PBE" or "LDA"). Default "PBE".
    
    Returns:
        Path to POTCAR directory (e.g., <app_data_dir>/engines/vasp/potpaw_PBE.64/)
    
    Raises:
        RuntimeError: If POTCAR directory cannot be found
    """
    managed_vasp = _get_managed_vasp_root()
    if managed_vasp is not None:
        potcar_dir = managed_vasp / f"potpaw_{potcar_type}.64"
        if potcar_dir.exists() and potcar_dir.is_dir():
            return potcar_dir

    raise RuntimeError(
        f"POTCAR directory not found: potpaw_{potcar_type}.64\n"
        f"Expected location: <app_data_dir>/engines/vasp/potpaw_{potcar_type}.64/"
    )
