"""CP2K output parser bundle.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import CP2KBandsProvider
from .convergence import CP2KConvergenceProvider
from .dos import CP2KDOSProvider
from .field3d import CP2KField3DProvider
from .output import CP2KDigest, CP2KOutputParser
from .trajectory import CP2KTrajectoryParser

__all__ = [
    "CP2KBandsProvider",
    "CP2KConvergenceProvider",
    "CP2KDOSProvider",
    "CP2KField3DProvider",
    "CP2KDigest",
    "CP2KOutputParser",
    "CP2KTrajectoryParser",
]
