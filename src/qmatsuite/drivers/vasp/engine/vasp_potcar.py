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


def _format_path_for_error(path: Path) -> str:
    """Format a path for error messages using app-data/repo-relative paths when possible."""
    # Prefer app-data-relative paths (works for dev, pip, and Electron modes).
    try:
        from qmatsuite.core.paths import get_app_data_dir

        app_data_dir = get_app_data_dir()
        try:
            rel_path = path.resolve().relative_to(app_data_dir.resolve())
            return str(Path(".qmatsuite") / rel_path)
        except (ValueError, RuntimeError):
            pass
    except ImportError:
        pass

    # Fall back to repo-root-relative paths when available.
    try:
        from qmatsuite.core.engines.discovery import _find_repo_root

        repo_root = _find_repo_root()
        if repo_root is not None:
            try:
                rel_path = path.resolve().relative_to(repo_root.resolve())
                return str(rel_path)
            except (ValueError, RuntimeError):
                pass
    except ImportError:
        pass
    
    # Last resort: return just the path name or a generic message
    if path.name:
        return f".../{path.name}"
    return "<path>"


def get_default_potcar_root() -> Optional[Path]:
    """Return the default POTCAR root directory, or None if not found.

    Search order:
        1. ``VASP_PP_PATH`` environment variable
        2. Managed app-data ``<app_data_dir>/engines/vasp/``
        3. Project-local ``.qmatsuite/engines/vasp/`` (walked up from CWD)
    """
    # Check env var first
    env_path = os.environ.get("VASP_PP_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            return p

    # Managed app-data location (dev mode resolves to <repo>/.qmatsuite).
    try:
        from qmatsuite.core.paths import home_engines_dir

        candidate = home_engines_dir() / "vasp"
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
            "in <app_data_dir>/engines/vasp/"
        )

    lib_dir = root / POTCAR_LIBRARY_DIRS[functional]
    if not lib_dir.is_dir():
        rel_path = _format_path_for_error(lib_dir)
        raise FileNotFoundError(
            f"POTCAR library directory not found: {rel_path}"
        )

    overrides = potcar_overrides or {}
    target_dir.mkdir(parents=True, exist_ok=True)
    potcar_path = target_dir / "POTCAR"

    with open(potcar_path, "w", encoding="utf-8") as out_fh:
        for element in species:
            variant = overrides.get(element, element)
            element_potcar = lib_dir / variant / "POTCAR"
            if not element_potcar.is_file():
                rel_path = _format_path_for_error(element_potcar)
                raise FileNotFoundError(
                    f"POTCAR not found for {element} "
                    f"(variant={variant!r}): {rel_path}"
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
