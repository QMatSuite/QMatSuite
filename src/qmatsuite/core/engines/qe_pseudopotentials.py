"""Backward-compatibility re-export for qe_pseudopotentials (moved to drivers/qe/engine/)."""

from qmatsuite.drivers.qe.engine.qe_pseudopotentials import (
    download_pseudopotential,
    PseudoManager,
    _find_qmatsuite_root,
)

__all__ = ["download_pseudopotential", "PseudoManager", "_find_qmatsuite_root"]

