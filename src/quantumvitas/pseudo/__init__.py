"""Pseudopotential library management — registry + download pipeline.

Public API::

    from quantumvitas.pseudo import PseudoRegistry, download_and_install

    registry = PseudoRegistry()
    info = registry.resolve("sssp", variant="precision", version="1.3.0")

    result = download_and_install(library="sssp", variant="precision")
"""

from quantumvitas.pseudo.layout import (
    InstalledLibrary,
    find_installed_library,
    find_upf_in_libraries,
    find_upf_in_libraries_casefold,
    iter_installed_libraries,
)
from quantumvitas.pseudo.pipeline import download_and_install
from quantumvitas.pseudo.registry import (
    ArchiveInfo,
    PseudoRegistry,
    archive_install_relpath,
    resolve_element_from_index,
)

__all__ = [
    "ArchiveInfo",
    "InstalledLibrary",
    "PseudoRegistry",
    "archive_install_relpath",
    "download_and_install",
    "find_installed_library",
    "find_upf_in_libraries",
    "find_upf_in_libraries_casefold",
    "iter_installed_libraries",
    "resolve_element_from_index",
]
