"""GPAW output parser bundle.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import GPAWBandsProvider
from .dos import GPAWDOSProvider

__all__ = [
    "GPAWBandsProvider",
    "GPAWDOSProvider",
]
