"""Siesta output parser bundle.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import SiestaBandsProvider
from .dos import SiestaDOSProvider
from .output import SiestaDigest, SiestaOutputParser

__all__ = [
    "SiestaBandsProvider",
    "SiestaDOSProvider",
    "SiestaDigest",
    "SiestaOutputParser",
]
