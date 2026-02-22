"""Psi4 engine driver bundle.

Registers the Psi4 driver with the DriverRegistry at import time.
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import Psi4Driver

DriverRegistry.register(Psi4Driver())

# Import parsers to trigger @register_parser registration
from . import parsers as _parsers  # noqa: F401, E402
