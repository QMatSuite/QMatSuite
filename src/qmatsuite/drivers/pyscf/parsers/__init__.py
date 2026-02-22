"""PySCF analysis parsers.

Importing this package triggers parser registration via @register_parser.
"""

from .convergence import PySCFConvergenceProvider
from .field3d import PySCFField3DProvider
from .trajectory import PySCFTrajectoryParser

__all__ = [
    "PySCFConvergenceProvider",
    "PySCFField3DProvider",
    "PySCFTrajectoryParser",
]
