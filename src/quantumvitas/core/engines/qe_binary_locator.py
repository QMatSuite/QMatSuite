"""Backward-compatibility re-export for qe_binary_locator (moved to drivers/qe/engine/)."""

from quantumvitas.drivers.qe.engine.qe_binary_locator import (
    locate_qe_executable,
    locate_pw2wannier90,
)

__all__ = ["locate_qe_executable", "locate_pw2wannier90"]

