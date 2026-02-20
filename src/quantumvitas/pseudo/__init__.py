"""Pseudopotential library management — registry + download pipeline.

Public API::

    from quantumvitas.pseudo import PseudoRegistry, download_and_install

    registry = PseudoRegistry()
    info = registry.resolve("sssp", variant="precision", version="1.3.0")

    result = download_and_install(library="sssp", variant="precision")
"""

from quantumvitas.pseudo.pipeline import download_and_install
from quantumvitas.pseudo.registry import (
    ArchiveInfo,
    PseudoRegistry,
    archive_install_relpath,
    resolve_element_from_index,
)

__all__ = [
    "ArchiveInfo",
    "PseudoRegistry",
    "archive_install_relpath",
    "download_and_install",
    "resolve_element_from_index",
]
