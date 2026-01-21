"""PySCF driver bundle.

This package provides the PySCF engine driver for QuantumVitas.
It handles all PySCF quantum chemistry calculations including
HF, DFT, post-HF, and multiconfigurational methods.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import PySCFDriver

# Register driver at import time
DriverRegistry.register(PySCFDriver())

__all__ = ["PySCFDriver"]

