"""ABINIT output parser bundle.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import ABINITBandsProvider
from .dos import ABINITDOSProvider
from .output import ABINITDigest, ABINITOutputParser

__all__ = [
    "ABINITBandsProvider",
    "ABINITDOSProvider",
    "ABINITDigest",
    "ABINITOutputParser",
]
