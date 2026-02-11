"""PySCF analysis parsers.

Importing this package triggers parser registration via @register_parser.
"""

from .trajectory import PySCFTrajectoryParser

__all__ = [
    "PySCFTrajectoryParser",
]
