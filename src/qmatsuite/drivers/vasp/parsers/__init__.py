"""VASP analysis parsers.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import VASPBandsProvider
from .convergence import VASPConvergenceProvider
from .dos import VASPDOSProvider
from .field3d import VASPField3DProvider
from .output import VASPDigest, VASPOutputParser
from .trajectory import VASPTrajectoryProvider

__all__ = [
    "VASPBandsProvider",
    "VASPConvergenceProvider",
    "VASPDOSProvider",
    "VASPDigest",
    "VASPField3DProvider",
    "VASPOutputParser",
    "VASPTrajectoryProvider",
]
