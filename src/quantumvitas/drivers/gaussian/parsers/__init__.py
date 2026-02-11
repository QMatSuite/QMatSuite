"""Gaussian output parsers.

Importing this package triggers registration of GaussianOutputParser
with the parser registry.
"""

from .output import GaussianDigest, GaussianOutputParser
from .trajectory import GaussianTrajectoryParser

__all__ = ["GaussianDigest", "GaussianOutputParser", "GaussianTrajectoryParser"]
