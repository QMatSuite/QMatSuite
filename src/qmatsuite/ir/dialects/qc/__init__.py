"""
IR QC Dialect (Quantum Chemistry with Atomic Orbitals).

This dialect represents quantum chemistry calculations with atomic orbitals (AO)
and molecular systems (MOL). Keys use PySCF-like names for QC atomic knobs.

This dialect uses Python native types (True/False for bools, not .true./.false. strings).
"""

from qmatsuite.ir.dialects.qc import parameters

__all__ = ["parameters"]

