"""VASP path resolution.

Resolves the path to the VASP binary following priority:
1. Environment variable QMATS_VASP_STD_BIN
2. Project root: .qmatsuite/engines/vasp/*/bin/vasp_std
3. System PATH: vasp_std in PATH
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from shutil import which


def resolve_vasp_bin(variant: str = "std") -> Path:
    """
    Resolve VASP binary path.
    
    Resolution order:
    1. Environment variable QMATS_VASP_{VARIANT}_BIN (e.g., QMATS_VASP_STD_BIN)
    2. Project root: .qmatsuite/engines/vasp/*/bin/vasp_{variant}
    3. System PATH: vasp_{variant} in PATH
    
    Args:
        variant: VASP variant ("std", "gam", "ncl"). Default "std".
    
    Returns:
        Path to VASP binary
    
    Raises:
        RuntimeError: If VASP cannot be found
    """
    # 1. Check environment variable
    env_var = f"QMATS_VASP_{variant.upper()}_BIN"
    env_bin = os.environ.get(env_var)
    if env_bin:
        bin_path = Path(env_bin)
        if bin_path.exists() and bin_path.is_file():
            return bin_path
        raise RuntimeError(f"{env_var} points to invalid path: {env_bin}")
    
    # 2. Check project root (repo-relative)
    checked_locations = []
    try:
        import quantumvitas
        _pkg_path = Path(quantumvitas.__file__).parent
        # Go up from src/quantumvitas to repo root
        _repo_root = _pkg_path.parent.parent
        _repo_vasp = _repo_root / ".qmatsuite" / "engines" / "vasp"
        checked_locations.append(str(_repo_vasp))
        
        if _repo_vasp.exists():
            # Look for version directories (e.g., vasp.6.5.0)
            for version_dir in sorted(_repo_vasp.iterdir(), reverse=True):
                if version_dir.is_dir() and version_dir.name.startswith("vasp."):
                    bin_path = version_dir / "bin" / f"vasp_{variant}"
                    if bin_path.exists() and bin_path.is_file():
                        return bin_path
    except Exception:
        pass
    
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
        Path to POTCAR directory (e.g., .qmatsuite/engines/vasp/potpaw_PBE.64/)
    
    Raises:
        RuntimeError: If POTCAR directory cannot be found
    """
    # Check project root (repo-relative)
    try:
        import quantumvitas
        _pkg_path = Path(quantumvitas.__file__).parent
        _repo_root = _pkg_path.parent.parent
        _potcar_dir = _repo_root / ".qmatsuite" / "engines" / "vasp" / f"potpaw_{potcar_type}.64"
        
        if _potcar_dir.exists() and _potcar_dir.is_dir():
            return _potcar_dir
    except Exception:
        pass
    
    raise RuntimeError(
        f"POTCAR directory not found: potpaw_{potcar_type}.64\n"
        f"Expected location: .qmatsuite/engines/vasp/potpaw_{potcar_type}.64/"
    )

