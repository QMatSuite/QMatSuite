"""QMCPACK output parsers.

Importing this module triggers parser registration via @register_parser.
"""

from .output import QMCPACKDigest, QMCPACKOutputParser

__all__ = ["QMCPACKDigest", "QMCPACKOutputParser"]
