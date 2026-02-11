"""ABINIT output parser bundle.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import ABINITBandsProvider
from .convergence import ABINITConvergenceProvider
from .dos import ABINITDOSProvider
from .field3d import ABINITField3DProvider
from .output import ABINITDigest, ABINITOutputParser
from .trajectory import ABINITTrajectoryParser

__all__ = [
    "ABINITBandsProvider",
    "ABINITConvergenceProvider",
    "ABINITDOSProvider",
    "ABINITField3DProvider",
    "ABINITDigest",
    "ABINITOutputParser",
    "ABINITTrajectoryParser",
]
