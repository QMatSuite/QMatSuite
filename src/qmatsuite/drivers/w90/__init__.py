"""Wannier90 driver bundle.

This package provides the Wannier90 engine driver for QMatSuite.
It handles Wannier90 calculations for constructing maximally
localized Wannier functions from DFT output.

Note: The wannierprep step is registered with the W90 engine.
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import W90Driver
from . import parsers  # noqa: F401, E402

# Register driver at import time
DriverRegistry.register(W90Driver())

__all__ = ["W90Driver"]
