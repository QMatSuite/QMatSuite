"""GPAW driver bundle.

This package provides the GPAW engine driver for QuantumVitas.
It handles periodic and molecular DFT calculations using GPAW
with PW, FD, and LCAO modes.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import GPAWDriver

# Register driver at import time
DriverRegistry.register(GPAWDriver())

__all__ = ["GPAWDriver"]
