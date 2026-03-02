"""MACE driver bundle.

This package provides the MACE ML interatomic potential engine driver for QMatSuite.
MACE uses ASE Calculator objects for computing energy/forces/stress with
pre-trained neural network potentials (foundation models or custom-trained).
"""

from qmatsuite.core.driver_registry import DriverRegistry
from .driver import MACEDriver

# Register driver at import time
DriverRegistry.register(MACEDriver())

# Trigger parser registration (MACEOutputParser, MACETrajectoryParser -> registry)
from . import parsers  # noqa: F401, E402

__all__ = ["MACEDriver"]
