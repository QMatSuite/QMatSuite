"""Siesta output parser bundle.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import SiestaBandsProvider
from .convergence import SiestaConvergenceProvider
from .dos import SiestaDOSProvider
from .field3d import SiestaField3DProvider
from .output import SiestaDigest, SiestaOutputParser
from .trajectory import SiestaTrajectoryParser

__all__ = [
    "SiestaBandsProvider",
    "SiestaConvergenceProvider",
    "SiestaDOSProvider",
    "SiestaField3DProvider",
    "SiestaDigest",
    "SiestaOutputParser",
    "SiestaTrajectoryParser",
]
