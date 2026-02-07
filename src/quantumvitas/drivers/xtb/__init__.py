"""xTB driver bundle.

This package provides the xTB semi-empirical engine driver for QuantumVitas.
It handles molecular geometry optimization using GFN0/1/2-xTB methods.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import XTBDriver

# Register driver at import time
DriverRegistry.register(XTBDriver())

# Trigger parser registration (XTBOutputParser -> registry)
from . import parsers  # noqa: F401, E402

__all__ = ["XTBDriver"]
