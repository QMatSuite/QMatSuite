"""
Shim module that re-exports QE input data structures, parser, and generator
from the new ``quantumvitas.io`` package.
"""

from quantumvitas.io.generator.qe_generator import QEInputGenerator
from quantumvitas.io.model import QECard, QECardType, QEInput, QEModule, QENamelist
from quantumvitas.io.parser.qe_parser import QEInputParser

__all__ = [
    "QEModule",
    "QECardType",
    "QENamelist",
    "QECard",
    "QEInput",
    "QEInputParser",
    "QEInputGenerator",
]

