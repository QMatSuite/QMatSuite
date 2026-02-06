"""LAMMPS output parsers.

Importing this package triggers registration of LAMMPSOutputParser
with the parser registry.
"""

from .output import LAMMPSDigest, LAMMPSOutputParser

__all__ = ["LAMMPSDigest", "LAMMPSOutputParser"]
