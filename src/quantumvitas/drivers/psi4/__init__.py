"""Psi4 engine driver bundle.

Registers the Psi4 driver with the DriverRegistry at import time.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import Psi4Driver

DriverRegistry.register(Psi4Driver())
