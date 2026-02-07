"""Yambo driver bundle.

This package provides the Yambo many-body perturbation theory engine driver
for QuantumVitas. It handles GW, BSE, and optical property calculations
using wavefunctions from upstream DFT engines (Quantum ESPRESSO via p2y).
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import YamboDriver

# Register driver at import time
DriverRegistry.register(YamboDriver())

# Trigger parser registration (YamboOutputParser -> registry)
from . import parsers  # noqa: F401, E402

__all__ = ["YamboDriver"]
