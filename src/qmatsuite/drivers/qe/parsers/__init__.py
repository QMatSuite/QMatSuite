"""QE analysis parsers.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import QEBandsProvider
from .convergence import QEConvergenceProvider
from .dos import QEDOSProvider
from .field3d import QEField3DProvider
from .neb_trajectory import QENEBTrajectoryProvider
from .output import QEOutputParser, QESCFDigest
from .trajectory import QETrajectoryParser

__all__ = [
    "QEBandsProvider",
    "QEConvergenceProvider",
    "QEDOSProvider",
    "QEField3DProvider",
    "QENEBTrajectoryProvider",
    "QEOutputParser",
    "QESCFDigest",
    "QETrajectoryParser",
]
