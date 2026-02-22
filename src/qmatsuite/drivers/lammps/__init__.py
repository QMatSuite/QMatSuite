"""LAMMPS driver bundle.

This package provides the LAMMPS engine driver for QMatSuite.
It handles all LAMMPS molecular dynamics simulations including
energy minimization, various ensembles, and restart handling.
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import LAMMPSDriver

# Register driver at import time
DriverRegistry.register(LAMMPSDriver())

# Trigger parser registration (LAMMPSOutputParser -> registry)
from . import parsers  # noqa: F401, E402

__all__ = ["LAMMPSDriver"]

