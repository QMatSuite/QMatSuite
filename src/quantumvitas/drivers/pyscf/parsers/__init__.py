"""PySCF analysis parsers.

Importing this package triggers parser registration via @register_parser.
"""

from .field3d import PySCFField3DProvider
from .trajectory import PySCFTrajectoryParser

__all__ = [
    "PySCFField3DProvider",
    "PySCFTrajectoryParser",
]
