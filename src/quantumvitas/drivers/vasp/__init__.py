"""VASP driver bundle.

This package provides the VASP engine driver for QuantumVitas.
It handles all VASP calculations including SCF, relaxation, MD,
band structure, DOS, and various property calculations.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import VASPDriver

# Register driver at import time
DriverRegistry.register(VASPDriver())

__all__ = ["VASPDriver"]

