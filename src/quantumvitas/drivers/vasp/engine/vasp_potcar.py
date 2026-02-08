"""VASP POTCAR staging utility.

Finds and concatenates per-element POTCAR files from a POTCAR library
directory (e.g., potpaw_PBE.64/) to produce a combined POTCAR for a
VASP calculation. Stdlib only — no kernel imports.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


# Mapping from functional name to library directory name
POTCAR_LIBRARY_DIRS: Dict[str, str] = {
    "PBE": "potpaw_PBE.64",
    "LDA": "potpaw_LDA.64",
}


def get_default_potcar_root() -> Optional[Path]:
    """Return the default POTCAR root directory, or None if not found.

    Search order:
        1. ``VASP_PP_PATH`` environment variable
        2. Project-local ``.qmatsuite/engines/vasp/`` (via centralized repo root)
        3. Project-local ``.qmatsuite/engines/vasp/`` (walked up from CWD)
    """
    # Check env var first
    env_path = os.environ.get("VASP_PP_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            return p

    # Project-local via centralized repo root detection
    # (handles test environments where CWD is a tmpdir)
    try:
        from quantumvitas.core.engines.discovery import _find_repo_root
        repo_root = _find_repo_root()
        if repo_root:
            candidate = repo_root / ".qmatsuite" / "engines" / "vasp"
            if candidate.is_dir():
                return candidate
    except ImportError:
        pass

    # Project-local: walk up from CWD
    current = Path.cwd().resolve()
    for _ in range(20):
        candidate = current / ".qmatsuite" / "engines" / "vasp"
        if candidate.is_dir():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def stage_potcar(
    species: List[str],
    target_dir: Path,
    functional: str = "PBE",
    potcar_overrides: Optional[Dict[str, str]] = None,
    vasp_potcar_root: Optional[Path] = None,
) -> Path:
    """Concatenate per-element POTCARs into a single POTCAR file.

    Args:
        species: Ordered list of unique species (e.g., ["Si"], ["Ti", "O"]).
        target_dir: Directory to write the combined POTCAR to.
        functional: Functional key ("PBE" or "LDA").
        potcar_overrides: Optional mapping from element to variant
            (e.g., ``{"Fe": "Fe_pv"}``). If not specified, the bare
            element name is used as the directory name.
        vasp_potcar_root: Root directory containing potpaw_* dirs.
            Falls back to ``get_default_potcar_root()``.

    Returns:
        Path to the written POTCAR file.

    Raises:
        FileNotFoundError: If a species POTCAR cannot be found.
        ValueError: If the functional is not recognized.
    """
    if functional not in POTCAR_LIBRARY_DIRS:
        raise ValueError(
            f"Unknown functional {functional!r}. "
            f"Available: {sorted(POTCAR_LIBRARY_DIRS)}"
        )

    root = vasp_potcar_root or get_default_potcar_root()
    if root is None:
        raise FileNotFoundError(
            "No POTCAR library found. Set VASP_PP_PATH or place POTCARs "
            "in <repo_root>/.qmatsuite/engines/vasp/"
        )

    lib_dir = root / POTCAR_LIBRARY_DIRS[functional]
    if not lib_dir.is_dir():
        raise FileNotFoundError(
            f"POTCAR library directory not found: {lib_dir}"
        )

    overrides = potcar_overrides or {}
    target_dir.mkdir(parents=True, exist_ok=True)
    potcar_path = target_dir / "POTCAR"

    with open(potcar_path, "w", encoding="utf-8") as out_fh:
        for element in species:
            variant = overrides.get(element, element)
            element_potcar = lib_dir / variant / "POTCAR"
            if not element_potcar.is_file():
                raise FileNotFoundError(
                    f"POTCAR not found for {element} "
                    f"(variant={variant!r}): {element_potcar}"
                )
            with open(element_potcar, "r", encoding="utf-8") as in_fh:
                out_fh.write(in_fh.read())

    return potcar_path


def list_available_potcars(
    functional: str = "PBE",
    vasp_potcar_root: Optional[Path] = None,
) -> List[str]:
    """List available element/variant directories in the POTCAR library.

    Args:
        functional: Functional key ("PBE" or "LDA").
        vasp_potcar_root: Root directory containing potpaw_* dirs.

    Returns:
        Sorted list of available element/variant names.
    """
    if functional not in POTCAR_LIBRARY_DIRS:
        return []

    root = vasp_potcar_root or get_default_potcar_root()
    if root is None:
        return []

    lib_dir = root / POTCAR_LIBRARY_DIRS[functional]
    if not lib_dir.is_dir():
        return []

    return sorted(
        d.name for d in lib_dir.iterdir()
        if d.is_dir() and (d / "POTCAR").is_file()
    )
