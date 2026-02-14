"""QMCPACK driver bundle.

This package provides the QMCPACK engine driver for QuantumVitas.
It handles Quantum Monte Carlo calculations including VMC, DMC,
and wavefunction optimization.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import QMCPACKDriver

# Register driver at import time
DriverRegistry.register(QMCPACKDriver())

# Import parsers to trigger @register_parser registration
from . import parsers  # noqa: F401, E402

__all__ = ["QMCPACKDriver"]
