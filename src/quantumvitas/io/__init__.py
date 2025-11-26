"""
I/O layer: QE models, parsers, generators, pseudo management.
"""

from .model import QEModule, QECardType, QENamelist, QECard, QEInput

__all__ = [
    "QEModule",
    "QECardType",
    "QENamelist",
    "QECard",
    "QEInput",
]
"""I/O modules for reading and writing data files."""

from .structure_io import read_structure, write_structure, detect_format

__all__ = [
    "read_structure",
    "write_structure",
    "detect_format",
]

