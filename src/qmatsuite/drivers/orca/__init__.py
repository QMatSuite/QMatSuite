"""ORCA driver bundle.

This package provides the ORCA engine driver for QMatSuite.
It handles all ORCA quantum chemistry calculations including
SCF, optimization, frequencies, and correlated methods.
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import ORCADriver
from . import parsers  # noqa: F401, E402

# Register driver at import time
DriverRegistry.register(ORCADriver())

__all__ = ["ORCADriver"]
