"""GPAW driver bundle.

This package provides the GPAW engine driver for QMatSuite.
It handles periodic and molecular DFT calculations using GPAW
with PW, FD, and LCAO modes.
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import GPAWDriver
from . import parsers  # noqa: F401, E402

# Register driver at import time
DriverRegistry.register(GPAWDriver())

__all__ = ["GPAWDriver"]
