"""CP2K driver bundle.

This package provides the CP2K engine driver for QuantumVitas.
It handles all CP2K calculations including DFT, MD, and
property calculations.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import CP2KDriver

# Register driver at import time
DriverRegistry.register(CP2KDriver())

__all__ = ["CP2KDriver"]

