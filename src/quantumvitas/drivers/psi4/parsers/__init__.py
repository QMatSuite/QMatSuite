"""Psi4 analysis parsers.

Importing this package triggers parser registration via @register_parser.
"""

from .trajectory import Psi4TrajectoryParser

__all__ = [
    "Psi4TrajectoryParser",
]
