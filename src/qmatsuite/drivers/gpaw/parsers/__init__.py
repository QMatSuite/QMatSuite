"""GPAW output parser bundle.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import GPAWBandsProvider
from .convergence import GPAWConvergenceProvider
from .dos import GPAWDOSProvider
from .field3d import GPAWField3DProvider
from .trajectory import GPAWTrajectoryParser

__all__ = [
    "GPAWBandsProvider",
    "GPAWConvergenceProvider",
    "GPAWDOSProvider",
    "GPAWField3DProvider",
    "GPAWTrajectoryParser",
]
