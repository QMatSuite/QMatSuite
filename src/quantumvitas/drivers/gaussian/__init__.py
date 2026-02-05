"""Gaussian engine driver.

This package provides the Gaussian quantum chemistry engine driver.
Gaussian handles HF, DFT, MP2, CCSD, TDDFT, geometry optimization,
and frequency calculations.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import GaussianDriver

# Register the driver
DriverRegistry.register(GaussianDriver())
