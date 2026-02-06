"""Wannier90 output parsers.

Importing this package triggers registration of W90OutputParser
with the parser registry.
"""

from .output import W90Digest, W90OutputParser

__all__ = ["W90Digest", "W90OutputParser"]
