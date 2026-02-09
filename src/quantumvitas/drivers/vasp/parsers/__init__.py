"""VASP analysis parsers.

Importing this package triggers parser registration via @register_parser.
"""

from .bands import VASPBandsProvider
from .output import VASPDigest, VASPOutputParser

__all__ = ["VASPDigest", "VASPOutputParser", "VASPBandsProvider"]
