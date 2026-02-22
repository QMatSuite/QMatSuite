"""Gaussian engine driver.

This package provides the Gaussian quantum chemistry engine driver.
Gaussian handles HF, DFT, MP2, CCSD, TDDFT, geometry optimization,
and frequency calculations.
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import GaussianDriver

# Register driver at import time
DriverRegistry.register(GaussianDriver())

# Trigger parser registration (GaussianOutputParser -> registry)
from . import parsers  # noqa: F401, E402

__all__ = ["GaussianDriver"]
