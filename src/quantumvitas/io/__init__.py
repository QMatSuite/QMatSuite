"""
I/O layer: QE models, parsers, generators, pseudo management.
"""

# Backward-compatibility re-exports for QE I/O (moved to drivers/qe/io/)
from quantumvitas.drivers.qe.io.model import QEModule, QECardType, QENamelist, QECard, QEInput
from quantumvitas.drivers.qe.io.parser import QEInputParser
from quantumvitas.drivers.qe.io.generator import QEInputGenerator
from quantumvitas.drivers.qe.io.structure_io import structure_from_qe_input

# Non-QE I/O functions (still in io/structure_io.py)
from .structure_io import (
    read_structure,
    write_structure,
    detect_format,
)

__all__ = [
    "QEModule",
    "QECardType",
    "QENamelist",
    "QECard",
    "QEInput",
    "QEInputParser",
    "QEInputGenerator",
    "read_structure",
    "write_structure",
    "detect_format",
    "structure_from_qe_input",
]