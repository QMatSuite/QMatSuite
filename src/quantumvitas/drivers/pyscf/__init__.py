"""PySCF driver bundle.

This package provides the PySCF engine driver for QuantumVitas.
It handles all PySCF quantum chemistry calculations including
HF, DFT, post-HF, and multiconfigurational methods.
"""

from quantumvitas.core.driver_registry import DriverRegistry
from .driver import PySCFDriver

# Register driver at import time
DriverRegistry.register(PySCFDriver())

# Import parsers to trigger @register_parser registration
from . import parsers as _parsers  # noqa: F401, E402

__all__ = ["PySCFDriver"]

