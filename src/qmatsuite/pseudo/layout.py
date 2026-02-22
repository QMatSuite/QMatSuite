"""Shared helpers for the three-level pseudo-library layout.

Layout on disk::

    <libraries_root>/<Library>/<variant>/<version>/head.json
                                                  /*.UPF

Every function that needs to discover or locate installed libraries
MUST call helpers from this module instead of open-coding the walk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Optional


@dataclass(frozen=True)
class InstalledLibrary:
    """Snapshot of one installed library variant/version."""

    install_dir: Path
    library_key: str
    variant: str
    version: str
    head: dict = field(repr=False)


def iter_installed_libraries(
    libraries_root: Path,
) -> Iterator[InstalledLibrary]:
    """Yield every installed library found under *libraries_root*.

    Walks ``<libraries_root>/<dir_name>/<variant>/<version>/``
    and yields an :class:`InstalledLibrary` for each directory that
    contains a valid ``head.json``.
    """
    if not libraries_root.is_dir():
        return

    for lib_dir in sorted(libraries_root.iterdir()):
        if not lib_dir.is_dir():
            continue
        for variant_dir in sorted(lib_dir.iterdir()):
            if not variant_dir.is_dir():
                continue
            for version_dir in sorted(variant_dir.iterdir()):
                if not version_dir.is_dir():
                    continue
                head_path = version_dir / "head.json"
                if not head_path.exists():
                    continue
                try:
                    head = json.loads(head_path.read_text())
                    yield InstalledLibrary(
                        install_dir=version_dir,
                        library_key=head.get("library_key", lib_dir.name),
                        variant=head.get("variant", variant_dir.name),
                        version=head.get("version", version_dir.name),
                        head=head,
                    )
                except (json.JSONDecodeError, KeyError, OSError):
                    continue


def find_installed_library(
    libraries_root: Path,
    library_key: str,
    variant: str,
    version: str,
) -> Optional[InstalledLibrary]:
    """Return the first library matching *library_key/variant/version*, or ``None``."""
    lk = library_key.lower()
    for lib in iter_installed_libraries(libraries_root):
        if lib.library_key.lower() == lk and lib.variant == variant and lib.version == version:
            return lib
    return None


def find_upf_in_libraries(
    libraries_root: Path,
    filename: str,
) -> Optional[Path]:
    """Find a UPF file by exact *filename* across all installed libraries."""
    for lib in iter_installed_libraries(libraries_root):
        upf_path = lib.install_dir / filename
        if upf_path.is_file():
            return upf_path
    return None


def find_upf_in_libraries_casefold(
    libraries_root: Path,
    filename: str,
) -> Optional[Path]:
    """Like :func:`find_upf_in_libraries` but with case-insensitive fallback."""
    target_lower = filename.lower()
    for lib in iter_installed_libraries(libraries_root):
        # Exact match first
        exact = lib.install_dir / filename
        if exact.is_file():
            return exact
        # Case-insensitive fallback
        for f in lib.install_dir.iterdir():
            if f.name.lower() == target_lower and f.is_file():
                return f
    return None
