"""ABINIT driver bundle.

This package provides the ABINIT plane-wave DFT engine driver
for QuantumVitas. It handles ground state SCF, NSCF, and relaxation
calculations.

ABINIT is similar to Quantum ESPRESSO but with unique features like
multi-dataset mode and comprehensive DFPT support.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import AbinitDriver
from . import parsers  # noqa: F401, E402

# Register driver at import time
DriverRegistry.register(AbinitDriver())

__all__ = ["AbinitDriver"]
