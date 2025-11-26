"""
Re-export the new PseudoManager implementation.
"""

from quantumvitas.core.engines.qe_pseudopotentials import (
    PseudoManager,
    ensure_pseudopotentials,
)

__all__ = ["PseudoManager", "ensure_pseudopotentials"]

