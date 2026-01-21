"""Wannier90 driver bundle.

This package provides the Wannier90 engine driver for QuantumVitas.
It handles Wannier90 calculations for constructing maximally
localized Wannier functions from DFT output.

Note: The w90_preproc step is registered with the DFT engine
(QE, VASP) that executes it, not with this driver.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import W90Driver

# Register driver at import time
DriverRegistry.register(W90Driver())

__all__ = ["W90Driver"]

