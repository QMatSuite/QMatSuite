"""LAMMPS force-field potential staging utility.

Finds and copies potential files (EAM, MEAM, Tersoff, SW, ReaxFF, etc.)
referenced in a LAMMPS input script into the working directory.
Stdlib only — no kernel imports.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_default_potential_root() -> Optional[Path]:
    """Return the default LAMMPS potential library root, or None.

    Search order:
      1. ``LAMMPS_POTENTIALS`` environment variable
      2. ``<repo_root>/.qmatsuite/engines/lammps/potentials/`` (via repo root detection)
      3. Walked up from CWD
      4. Homebrew share location (macOS)
    """
    # Check env var first
    env_path = os.environ.get("LAMMPS_POTENTIALS")
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            return p

    # Repo-root via centralized detection
    try:
        from quantumvitas.core.engines.discovery import _find_repo_root
        repo_root = _find_repo_root()
        if repo_root:
            candidate = repo_root / ".qmatsuite" / "engines" / "lammps" / "potentials"
            if candidate.is_dir():
                return candidate
    except ImportError:
        pass

    # Walk up from CWD
    current = Path.cwd().resolve()
    for _ in range(20):
        candidate = current / ".qmatsuite" / "engines" / "lammps" / "potentials"
        if candidate.is_dir():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent

    # Homebrew location (macOS)
    brew_path = Path("/opt/homebrew/share/lammps/potentials")
    if brew_path.is_dir():
        return brew_path

    return None


def extract_potential_refs(params: Dict[str, Any]) -> List[str]:
    """Extract potential file references from parsed LAMMPS parameters.

    Scans pair_coeff entries for filenames (entries containing '.' that
    are not purely numeric). Also checks for common potential-referencing
    commands in the _commands stream.

    Returns:
        List of potential filenames referenced in the input.
    """
    refs: list[str] = []
    seen: set[str] = set()

    # From pair_coeff entries: pair_coeff * * filename.eam Si O
    for pc in params.get("pair_coeff", []):
        tokens = pc.split()
        for tok in tokens:
            if _looks_like_potential_file(tok) and tok not in seen:
                refs.append(tok)
                seen.add(tok)

    # From _commands stream: look for common potential-referencing commands
    for entry in params.get("_commands", []):
        cmd = entry.get("cmd", "")
        args = entry.get("args", [])

        # pair_coeff already handled above
        if cmd == "pair_coeff":
            continue

        # Commands that take a potential file argument
        if cmd in ("pair_style", "bond_coeff", "angle_coeff"):
            for tok in args:
                if _looks_like_potential_file(tok) and tok not in seen:
                    refs.append(tok)
                    seen.add(tok)

    return refs


def _looks_like_potential_file(token: str) -> bool:
    """Heuristic: does this token look like a potential filename?"""
    # Must contain a dot (file extension)
    if "." not in token:
        return False
    # Skip purely numeric tokens like "1.0" or "2.5"
    try:
        float(token)
        return False
    except ValueError:
        pass
    # Skip LAMMPS special tokens
    if token in ("*", "NULL"):
        return False
    # Common potential file extensions
    known_ext = {
        ".eam", ".alloy", ".fs", ".tersoff", ".sw", ".meam",
        ".reax", ".reaxff", ".snap", ".snapcoeff", ".snapparam",
        ".pod", ".table", ".morse", ".buck", ".born",
        ".lib", ".para", ".ffield", ".dat",
    }
    for ext in known_ext:
        if token.endswith(ext):
            return True
    # Heuristic: if basename has no spaces and path-like structure
    return "/" in token or token.count(".") >= 1 and len(token) > 4


def stage_potentials(
    potential_refs: List[str],
    target_dir: Path,
    potential_root: Optional[Path] = None,
) -> List[Path]:
    """Copy referenced potential files into the target directory.

    Args:
        potential_refs: List of potential filenames to stage.
        target_dir: Working directory where potentials should be placed.
        potential_root: Root directory of the potential library.
            If None, uses ``get_default_potential_root()``.

    Returns:
        List of paths to staged potential files.

    Raises:
        FileNotFoundError: If a referenced potential is not found
            in the target directory or the potential library.
    """
    if potential_root is None:
        potential_root = get_default_potential_root()

    staged: list[Path] = []
    target_dir = Path(target_dir)

    for ref in potential_refs:
        # Strip any path prefix — we only care about the basename
        basename = Path(ref).name
        target_file = target_dir / basename

        # Already in place?
        if target_file.exists():
            staged.append(target_file)
            continue

        # Search in potential library
        if potential_root is not None:
            source = potential_root / basename
            if source.exists():
                shutil.copy2(source, target_file)
                staged.append(target_file)
                continue

            # Try recursive search
            matches = list(potential_root.rglob(basename))
            if matches:
                shutil.copy2(matches[0], target_file)
                staged.append(target_file)
                continue

        raise FileNotFoundError(
            f"LAMMPS potential file '{ref}' not found. "
            f"Searched: {target_dir}"
            + (f", {potential_root}" if potential_root else "")
        )

    return staged
